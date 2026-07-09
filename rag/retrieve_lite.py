# """
# Lightweight legal-chunk retriever - plain tag-overlap filtering, no
# embeddings/FAISS/sentence-transformers/torch at all.

# Why this is a reasonable substitute for LegalRetriever (retrieve.py) here:
# your legal_kb only has a handful of chunks total. The embedding-based
# "Stage 2: rank by similarity" step in the full retriever is mostly there to
# handle a corpus much larger than this - at 8 chunks, tag-filtering alone
# (Stage 1) already narrows things down to essentially the right answer, so
# the extra ranking step buys little accuracy for a lot of dependency weight
# (sentence-transformers alone pulls in torch, another several hundred MB+).

# Same public interface as LegalRetriever, so main.py doesn't need to change
# based on which one is active - see RETRIEVER_BACKEND in main.py.
# """
# import json
# import os
# from datetime import date


# class LiteLegalRetriever:
#     def __init__(self, index_dir="./index"):
#         # index_dir is accepted (and ignored) only so this drop-in matches
#         # LegalRetriever's constructor signature - this backend needs no
#         # prebuilt index at all, it reads the source JSON directly.
#         kb_path = os.path.join(os.path.dirname(__file__), "..", "legal_kb", "legal_chunks.json")
#         with open(kb_path, encoding="utf-8") as f:
#             self.chunks = json.load(f)

#     def retrieve(self, query_text: str, legal_tags: list, top_k: int = 4, incident_date=None):
#         candidate_idx = [
#             i for i, c in enumerate(self.chunks)
#             if set(c.get("tags", [])) & set(legal_tags)
#         ]

#         if incident_date is not None:
#             bns_cutoff = date(2024, 7, 1)
#             filtered = []
#             for i in candidate_idx:
#                 regime = self.chunks[i].get("regime", "")
#                 is_legacy_ipc = "before 1 July 2024" in regime or ("IPC" in regime and "BNS" not in regime)
#                 is_bns = "BNS" in regime
#                 if incident_date < bns_cutoff and is_bns and not is_legacy_ipc:
#                     continue
#                 if incident_date >= bns_cutoff and is_legacy_ipc:
#                     continue
#                 filtered.append(i)
#             if filtered:
#                 candidate_idx = filtered

#         if not candidate_idx:
#             candidate_idx = list(range(len(self.chunks)))

#         results = []
#         for idx in candidate_idx[:top_k]:
#             chunk = self.chunks[idx]
#             results.append({
#                 "id": chunk["id"],
#                 "title": chunk["title"],
#                 "text": chunk["text"],
#                 "regime": chunk.get("regime", ""),
#                 "score": 1.0,  # no similarity score to report - tag match only
#             })
#         return results


# if __name__ == "__main__":
#     import sys
#     sys.path.append("../data")
#     from taxonomy import CATEGORIES

#     retriever = LiteLegalRetriever()
#     query = "Someone took money from my bank account using a fake UPI link"
#     tags = CATEGORIES["upi_fraud"]["legal_tags"]
#     for r in retriever.retrieve(query, tags):
#         print(f"{r['title']} ({r['regime']})")

"""
Lightweight legal-chunk retriever - plain tag-overlap filtering, no
embeddings/FAISS/sentence-transformers/torch at all.

Why this is a reasonable substitute for LegalRetriever (retrieve.py) here:
your legal_kb only has a handful of chunks total. The embedding-based
"Stage 2: rank by similarity" step in the full retriever is mostly there to
handle a corpus much larger than this - at 8 chunks, tag-filtering alone
(Stage 1) already narrows things down to essentially the right answer, so
the extra ranking step buys little accuracy for a lot of dependency weight
(sentence-transformers alone pulls in torch, another several hundred MB+).

Same public interface as LegalRetriever, so main.py doesn't need to change
based on which one is active - see RETRIEVER_BACKEND in main.py.
"""
import json
import os
from datetime import date


class LiteLegalRetriever:
    def __init__(self, index_dir="./index"):
        # index_dir is accepted (and ignored) only so this drop-in matches
        # LegalRetriever's constructor signature - this backend needs no
        # prebuilt index at all, it reads the source JSON directly.
        kb_path = os.path.join(os.path.dirname(__file__), "..", "legal_kb", "legal_chunks.json")
        with open(kb_path, encoding="utf-8") as f:
            self.chunks = json.load(f)

    def retrieve(self, query_text: str, legal_tags: list, top_k: int = 4, incident_date=None):
        candidate_idx = [
            i for i, c in enumerate(self.chunks)
            if set(c.get("tags", [])) & set(legal_tags)
        ]

        if incident_date is not None:
            bns_cutoff = date(2024, 7, 1)
            filtered = []
            for i in candidate_idx:
                regime = self.chunks[i].get("regime", "")
                is_legacy_ipc = "before 1 July 2024" in regime or ("IPC" in regime and "BNS" not in regime)
                is_bns = "BNS" in regime
                if incident_date < bns_cutoff and is_bns and not is_legacy_ipc:
                    continue
                if incident_date >= bns_cutoff and is_legacy_ipc:
                    continue
                filtered.append(i)
            if filtered:
                candidate_idx = filtered

        if not candidate_idx:
            candidate_idx = list(range(len(self.chunks)))

        results = []
        for idx in candidate_idx[:top_k]:
            chunk = self.chunks[idx]
            results.append({
                "id": chunk["id"],
                "title": chunk["title"],
                "text": chunk["text"],
                "regime": chunk.get("regime", ""),
                "score": 1.0,  # no similarity score to report - tag match only
            })
        return results


if __name__ == "__main__":
    import sys
    sys.path.append("../data")
    from taxonomy import CATEGORIES

    retriever = LiteLegalRetriever()
    query = "Someone took money from my bank account using a fake UPI link"
    tags = CATEGORIES["upi_fraud"]["legal_tags"]
    for r in retriever.retrieve(query, tags):
        print(f"{r['title']} ({r['regime']})")