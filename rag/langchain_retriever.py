"""
LangChain-compatible wrapper around the existing two-stage legal retriever
(rag/retrieve.py's LegalRetriever - tag-filter, then embed-and-rank).

This does NOT reimplement retrieval. It wraps the existing, already-tested
LegalRetriever so the same tag-filter + cosine-rank behavior is exposed
through LangChain's BaseRetriever interface, so it can plug into any
LangChain/LangGraph pipeline that expects a retriever - while keeping the
domain-specific legal_tags filtering (Stage 1) that a generic
VectorStoreRetriever built straight from the FAISS index wouldn't know how
to do on its own for this corpus (see retrieve.py's module docstring for why
that stage matters: it avoids retrieving semantically similar but legally
wrong sections).

Usage:
    from retrieve import LegalRetriever
    from langchain_retriever import LegalKBRetriever

    base = LegalRetriever(index_dir="./index")
    lc_retriever = LegalKBRetriever(legal_retriever=base)

    # Stage 1's filter needs the classifier's legal_tags, which a bare
    # query string doesn't carry - so scope a copy per request before
    # invoking it, rather than passing tags through the query text itself:
    scoped = lc_retriever.with_query_context(legal_tags=[...], incident_date=...)
    docs = scoped.invoke("Someone took money from my account using a fake UPI link")
"""
from datetime import date
from typing import List, Optional

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import Field


class LegalKBRetriever(BaseRetriever):
    """LangChain BaseRetriever backed by rag.retrieve.LegalRetriever."""

    legal_retriever: object = Field(exclude=True)
    legal_tags: List[str] = Field(default_factory=list)
    incident_date: Optional[date] = None
    top_k: int = 4

    model_config = {"arbitrary_types_allowed": True}

    def with_query_context(
        self, legal_tags: List[str], incident_date: Optional[date] = None, top_k: int = 4
    ) -> "LegalKBRetriever":
        """Returns a copy of this retriever scoped to one query's classifier
        output. Call this once per request (after classification, before
        retrieval) rather than reusing a single instance across requests,
        since legal_tags differs per complaint."""
        return LegalKBRetriever(
            legal_retriever=self.legal_retriever,
            legal_tags=legal_tags,
            incident_date=incident_date,
            top_k=top_k,
        )

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        chunks = self.legal_retriever.retrieve(
            query_text=query,
            legal_tags=self.legal_tags,
            top_k=self.top_k,
            incident_date=self.incident_date,
        )
        return [
            Document(
                page_content=f"{c['title']}. {c['text']}",
                metadata={
                    "id": c["id"],
                    "title": c["title"],
                    "regime": c.get("regime", ""),
                    "score": c.get("score", 1.0),
                },
            )
            for c in chunks
        ]

    @staticmethod
    def document_to_chunk(doc: Document) -> dict:
        """Inverse of the mapping above - reshapes a Document back into the
        {"id","title","text","regime"} chunk dict that llm_reasoning.py's
        build_user_message() and every existing caller already expect, so
        swapping in this retriever doesn't ripple changes through the rest
        of the pipeline."""
        title = doc.metadata.get("title", "")
        text = doc.page_content
        if text.startswith(f"{title}. "):
            text = text[len(title) + 2 :]
        return {
            "id": doc.metadata.get("id", ""),
            "title": title,
            "text": text,
            "regime": doc.metadata.get("regime", ""),
            "score": doc.metadata.get("score", 1.0),
        }


if __name__ == "__main__":
    import sys

    sys.path.append("../data")
    from retrieve import LegalRetriever
    from taxonomy import CATEGORIES

    base = LegalRetriever()
    lc_retriever = LegalKBRetriever(legal_retriever=base)

    query = "Someone took money from my bank account using a fake UPI link"
    tags = CATEGORIES["upi_fraud"]["legal_tags"]
    scoped = lc_retriever.with_query_context(legal_tags=tags)
    for doc in scoped.invoke(query):
        print(f"[{doc.metadata['score']}] {doc.metadata['title']} ({doc.metadata['regime']})")
