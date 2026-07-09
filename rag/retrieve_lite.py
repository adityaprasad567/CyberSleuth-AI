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

Same public interface as FAISSRetriever, so main.py doesn't need to change
based on which one is active.
"""
import json
import os
import sys
from datetime import date

# Append parent directory to path to import the new 51-class taxonomy
# (Adjust 'data' below if your taxonomy is placed elsewhere)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from data.extended_taxonomy import CATEGORIES, SAFETY_RECOMMENDATIONS, URGENT_CATEGORIES
except ImportError:
    from extended_taxonomy import CATEGORIES, SAFETY_RECOMMENDATIONS, URGENT_CATEGORIES


class LiteLegalRetriever:
    def __init__(self, index_dir="./index"):
        # index_dir is accepted (and ignored) only so this drop-in matches
        # FAISSRetriever's constructor signature.
        kb_path = os.path.join(os.path.dirname(__file__), "..", "legal_kb", "legal_chunks.json")
        
        try:
            with open(kb_path, encoding="utf-8") as f:
                self.chunks = json.load(f)
        except FileNotFoundError:
            print(f"Warning: {kb_path} not found. Operating with empty fallback KB.")
            self.chunks = []

    def retrieve_context(self, query_text: str, predicted_label: str, top_k: int = 4, incident_date=None):
        """
        Public interface matching the FAISSRetriever.
        Notice query_text is accepted but ignored in favor of pure tag matching.
        """
        is_urgent = predicted_label in URGENT_CATEGORIES
        safety_recs = SAFETY_RECOMMENDATIONS.get(predicted_label, ["Report the incident on cybercrime.gov.in."])
        
        category_data = CATEGORIES.get(predicted_label, {})
        legal_tags = category_data.get("legal_tags", [])

        # Stage 1: Tag Overlap Filtering
        candidate_idx = [
            i for i, c in enumerate(self.chunks)
            if set(c.get("tags", [])) & set(legal_tags)
        ]

        # Stage 2: Temporal Filtering (BNS vs IPC)
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

        # Fallback if no tags match
        if not candidate_idx:
            candidate_idx = list(range(len(self.chunks)))

        # Assemble Results
        matched_legal_chunks = []
        for idx in candidate_idx[:top_k]:
            chunk = self.chunks[idx]
            matched_legal_chunks.append({
                "id": chunk.get("id", "N/A"),
                "title": chunk.get("title", "Legal Section"),
                "text": chunk.get("text", ""),
                "regime": chunk.get("regime", ""),
                "score": 1.0,  # tag match only
            })

        return {
            "label": predicted_label,
            "is_urgent": is_urgent,
            "safety_recommendations": safety_recs,
            "legal_chunks": matched_legal_chunks,
            "execution_mode": "lite_fallback"
        }


if __name__ == "__main__":
    retriever = LiteLegalRetriever()
    
    # Testing with a post-BNS cutoff date
    test_date = date(2024, 8, 15)
    
    print("--- Testing Lite Retrieval ---")
    res = retriever.retrieve_context(
        query_text="Someone took money from my bank account using a fake UPI link", 
        predicted_label="upi_fraud",
        incident_date=test_date
    )
    
    print(f"Predicted Label: {res['label']}")
    print(f"Urgent: {res['is_urgent']}")
    print(f"\nRetrieved Laws:")
    for chunk in res['legal_chunks']:
        print(f"- {chunk['title']} ({chunk.get('regime', 'Unknown Regime')})")