"""
LangGraph orchestration for the classify -> retrieve -> reason pipeline.

This models backend/main.py's `_run_pipeline()` as an explicit state graph
instead of a straight-line function call. Same three stages, same
classify()/retriever.retrieve()/generate_response() functions the rest of
the codebase already uses - this file adds orchestration, not new business
logic, and reuses langchain_retriever.LegalKBRetriever for Stage 2 so
retrieval goes through LangChain's Document interface too.

Why a graph instead of the existing straight-line function:
  - "No legal context retrieved" is real branching behavior, not an edge
    case to swallow with an if/else buried in a longer function: per
    llm_reasoning.py's own SYSTEM_PROMPT ("say so explicitly rather than
    filling the gap"), grounding is the whole point of this system, so an
    empty retrieval should skip the LLM entirely rather than let it reason
    over nothing. Making that a separate node keeps the branch visible and
    independently testable instead of one more condition in a growing
    function.
  - Same reasoning for the low-confidence flag: it is computed once, in one
    place, and every downstream node reads it rather than re-deriving it.
  - If this pipeline later grows multi-turn behavior (follow-up questions
    on an existing complaint), LangGraph's checkpointing hooks in without
    restructuring the pipeline again.

Toggle via env var, same pattern as CLASSIFIER_BACKEND/RETRIEVER_BACKEND in
backend/main.py:
    PIPELINE_ENGINE=langgraph   (this file)
    PIPELINE_ENGINE=manual      (default - backend/main.py's straight-line _run_pipeline)
"""
from datetime import date
from typing import Any, Callable, Dict, List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from langchain_retriever import LegalKBRetriever


class PipelineState(TypedDict, total=False):
    text: str
    incident_date: Optional[date]
    classification_results: List[dict]
    top: dict
    retrieved: List[dict]
    llm_output: dict
    merged_safety: List[str]
    is_urgent: bool
    emergency_message: str
    low_confidence: bool


def build_pipeline_graph(
    classify_fn: Callable[..., list],
    retriever,
    generate_fn: Callable[..., dict],
    safety_recommendations: dict,
    urgent_categories: set,
    emergency_message: str,
    min_confidence_threshold: float,
):
    """
    classify_fn(text, top_k=3) -> [{"label","confidence","legal_tags"}, ...]
        Already bound to whichever CLASSIFIER_BACKEND is active - this graph
        doesn't care whether that's local/sklearn/gemini underneath.
    retriever: a rag.retrieve.LegalRetriever (or compatible) instance -
        wrapped here in LegalKBRetriever so Stage 2 runs through LangChain.
    generate_fn(user_text, crime_type, confidence, retrieved_chunks) -> dict
        Same generate_response() signature llm_reasoning.py already exposes.
    safety_recommendations / urgent_categories / emergency_message /
    min_confidence_threshold: the same taxonomy.py constants main.py
        already imports - passed in rather than re-imported so this module
        has no hidden dependency on data/taxonomy.py's exact location.
    """
    lc_retriever = LegalKBRetriever(legal_retriever=retriever)

    def classify_node(state: PipelineState) -> dict:
        results = classify_fn(state["text"], top_k=3)
        top = results[0]
        low_confidence = top["confidence"] < min_confidence_threshold
        return {"classification_results": results, "top": top, "low_confidence": low_confidence}

    def retrieve_node(state: PipelineState) -> dict:
        top = state["top"]
        scoped = lc_retriever.with_query_context(
            legal_tags=top["legal_tags"], incident_date=state.get("incident_date"), top_k=4
        )
        docs = scoped.invoke(state["text"])
        retrieved = [LegalKBRetriever.document_to_chunk(d) for d in docs]
        return {"retrieved": retrieved}

    def route_on_context(state: PipelineState) -> str:
        return "reason" if state["retrieved"] else "no_context_fallback"

    def reason_node(state: PipelineState) -> dict:
        top = state["top"]
        llm_output = generate_fn(
            user_text=state["text"],
            crime_type=top["label"],
            confidence=top["confidence"],
            retrieved_chunks=state["retrieved"],
        )
        return {"llm_output": llm_output}

    def no_context_fallback_node(state: PipelineState) -> dict:
        # No retrieved chunks -> no grounded legal context to reason over.
        # Skip the LLM call entirely instead of letting it invent a section
        # number, mirroring llm_reasoning.py's own hallucination-avoidance
        # rule for the "context doesn't cover this" case.
        top = state["top"]
        crime_title = top["label"].replace("_", " ").title()
        return {
            "llm_output": {
                "crime_type_explanation": f"This appears to be a case of {crime_title.lower()}.",
                "applicable_law": [],
                "regime_note": "",
                "immediate_actions": [
                    "Report the incident on the National Cybercrime Reporting Portal "
                    "(cybercrime.gov.in) or call the helpline 1930.",
                    "Preserve all evidence (screenshots, messages, transaction records) "
                    "before anything can be deleted.",
                ],
                "safety_recommendations": [],
                "draft_complaint": (
                    f"I am writing to report a {crime_title.lower()} incident. "
                    f"{state['text'].strip()}"
                ),
                "uncovered_aspects": (
                    "No matching legal sections were found in the knowledge base for "
                    "this category - the response above is general guidance only, not "
                    "grounded in a specific retrieved statute."
                ),
            }
        }

    def safety_merge_node(state: PipelineState) -> dict:
        top = state["top"]
        rule_based = safety_recommendations.get(top["label"], [])
        llm_safety = state["llm_output"].get("safety_recommendations", [])
        merged = list(dict.fromkeys(rule_based + llm_safety))  # preserves order, dedupes
        is_urgent = (top["label"] in urgent_categories) and not state["low_confidence"]
        return {
            "merged_safety": merged,
            "is_urgent": is_urgent,
            "emergency_message": emergency_message if is_urgent else "",
        }

    graph = StateGraph(PipelineState)
    graph.add_node("classify", classify_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("reason", reason_node)
    graph.add_node("no_context_fallback", no_context_fallback_node)
    graph.add_node("safety_merge", safety_merge_node)

    graph.add_edge(START, "classify")
    graph.add_edge("classify", "retrieve")
    graph.add_conditional_edges(
        "retrieve",
        route_on_context,
        {"reason": "reason", "no_context_fallback": "no_context_fallback"},
    )
    graph.add_edge("reason", "safety_merge")
    graph.add_edge("no_context_fallback", "safety_merge")
    graph.add_edge("safety_merge", END)

    return graph.compile()


def run_pipeline_langgraph(compiled_graph, text: str, incident_date=None) -> Dict[str, Any]:
    """Invoke the compiled graph and reshape output to match the manual
    `_run_pipeline()`'s return dict exactly, so main.py's callers (/analyze,
    /generate-report) don't need to know which engine produced it."""
    result = compiled_graph.invoke({"text": text, "incident_date": incident_date})
    return {
        "classification_results": result["classification_results"],
        "top": result["top"],
        "retrieved": result["retrieved"],
        "llm_output": result["llm_output"],
        "merged_safety": result["merged_safety"],
        "is_urgent": result["is_urgent"],
        "emergency_message": result["emergency_message"],
        "low_confidence": result["low_confidence"],
    }
