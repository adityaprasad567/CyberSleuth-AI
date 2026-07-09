"""
Retrieval layer for the legal knowledge base.

Retrieval is scoped in two stages, which is the key design choice that keeps
this accurate at small scale and cheap at large scale:

  1. Filter: only chunks whose `tags` overlap with the crime type's
     `legal_tags` (from taxonomy.py) are considered at all.
  2. Rank: within that filtered set, rank by embedding similarity to the
     user's actual complaint text, so the most relevant 2-3 sections surface
     first even within a matching category.

This avoids retrieving semantically similar but legally wrong sections
(e.g. a general fraud section when a more specific one applies).
"""
import json
import os
import pickle

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


class LegalRetriever:
    def __init__(self, index_dir="./index"):
        self.index = faiss.read_index(os.path.join(index_dir, "legal_kb.index"))
        with open(os.path.join(index_dir, "chunk_metadata.pkl"), "rb") as f:
            self.chunks = pickle.load(f)
        with open(os.path.join(index_dir, "model_name.txt")) as f:
            model_name = f.read().strip()
        self.model = SentenceTransformer(model_name)

        # Precompute per-chunk embeddings lookup by rebuilding from index
        # (faiss IndexFlatIP doesn't expose vectors directly, so we keep a
        # parallel embedding matrix built at index time is best practice -
        # for simplicity here we just re-embed titles+text once at load)
        texts = [f"{c['title']}. {c['text']}" for c in self.chunks]
        self.embeddings = self.model.encode(texts, normalize_embeddings=True)

    def retrieve(self, query_text: str, legal_tags: list, top_k: int = 4, incident_date=None):
        """
        query_text: the user's raw complaint text
        legal_tags: tags from taxonomy.py for the classified crime type
        incident_date: optional datetime.date - if provided, filters out the
            wrong BNS/IPC regime chunk (BNS applies from 1 July 2024 onward)
        """
        # Stage 1: filter by tag overlap
        candidate_idx = [
            i for i, c in enumerate(self.chunks)
            if set(c.get("tags", [])) & set(legal_tags)
        ]

        if incident_date is not None:
            from datetime import date
            bns_cutoff = date(2024, 7, 1)
            filtered = []
            for i in candidate_idx:
                regime = self.chunks[i].get("regime", "")
                is_legacy_ipc = "before 1 July 2024" in regime or "IPC" in regime and "BNS" not in regime
                is_bns = "BNS" in regime
                if incident_date < bns_cutoff and is_bns and not is_legacy_ipc:
                    continue
                if incident_date >= bns_cutoff and is_legacy_ipc:
                    continue
                filtered.append(i)
            if filtered:  # only apply if it doesn't wipe out everything
                candidate_idx = filtered

        if not candidate_idx:
            # fall back to full corpus if no tag match (shouldn't normally happen)
            candidate_idx = list(range(len(self.chunks)))

        # Stage 2: rank candidates by cosine similarity to the query
        query_emb = self.model.encode([query_text], normalize_embeddings=True)[0]
        sims = self.embeddings[candidate_idx] @ query_emb
        ranked = sorted(zip(candidate_idx, sims), key=lambda x: -x[1])[:top_k]

        results = []
        for idx, score in ranked:
            chunk = self.chunks[idx]
            results.append({
                "id": chunk["id"],
                "title": chunk["title"],
                "text": chunk["text"],
                "regime": chunk.get("regime", ""),
                "score": round(float(score), 4),
            })
        return results


if __name__ == "__main__":
    import sys
    sys.path.append("../data")
    from taxonomy import CATEGORIES

    retriever = LegalRetriever()
    query = "Someone took money from my bank account using a fake UPI link"
    tags = CATEGORIES["upi_fraud"]["legal_tags"]
    for r in retriever.retrieve(query, tags):
        print(f"[{r['score']}] {r['title']} ({r['regime']})")
