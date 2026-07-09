# """
# LLM reasoning layer: takes the classifier output + retrieved legal chunks
# and produces a structured, grounded response (plain-language law
# explanation, action steps, draft complaint).

# This is the layer where hallucination risk lives if not constrained - the
# system prompt below explicitly restricts the model to only cite retrieved
# chunk IDs, and instructs it to say "not covered in retrieved sources" rather
# than invent a section number. This constraint is worth measuring in your
# evaluation (see README "hallucination rate" comparison).

# Uses Google's Gemini API via the google-genai SDK (the current recommended
# SDK - the older google-generativeai package is deprecated as of 2026).
# Install:
#     pip install -U google-genai
# Set GEMINI_API_KEY as an environment variable (get a free key at
# https://aistudio.google.com/app/apikey).
# """
# import json
# import os
# import re
# import sys
# from pathlib import Path

# # So `from taxonomy import ...` inside generate_response_offline() works even
# # when this module is imported/run standalone (not just via backend/main.py,
# # which already adds this path itself before importing us).
# _data_dir = str(Path(__file__).parent.parent / "data")
# if _data_dir not in sys.path:
#     sys.path.append(_data_dir)

# SYSTEM_PROMPT = """You are a legal-information assistant helping a cybercrime victim in India understand their situation. You are NOT a lawyer and must not give a legal opinion on the merits of a case.

# STRICT RULES:
# 1. Only reference legal sections that appear in the RETRIEVED LEGAL CONTEXT provided below. Never invent, guess, or recall a section number from your own training - if the retrieved context doesn't cover something, say so explicitly rather than filling the gap.
# 2. When you reference a section, cite its chunk id exactly as given (e.g. "[it_act_66c]").
# 3. Explain the law in plain, non-legal language a stressed, non-expert victim can understand.
# 4. Always include time-sensitive procedural advice (e.g. calling 1930) if the retrieved context includes it.
# 5. Output valid JSON matching the schema given in the user message - no prose outside the JSON.
# """

# RESPONSE_SCHEMA_INSTRUCTIONS = """
# Respond with ONLY a JSON object with this exact structure:
# {
#   "crime_type_explanation": "1-2 sentence plain-language restatement of what happened",
#   "applicable_law": [
#     {"chunk_id": "...", "plain_language_summary": "..."}
#   ],
#   "regime_note": "note on whether BNS or IPC applies, if relevant, or empty string",
#   "immediate_actions": ["ordered list of what to do right now"],
#   "safety_recommendations": ["general safety hardening steps"],
#   "draft_complaint": "a formal complaint paragraph the user can copy-paste, written in first person, chronological, professional tone",
#   "uncovered_aspects": "anything the user described that the retrieved legal context does NOT address - empty string if none"
# }
# """

# # JSON schema passed to Gemini's response_schema config - this is what
# # actually enforces structured output (response_mime_type alone just asks
# # nicely; response_schema constrains generation).
# RESPONSE_JSON_SCHEMA = {
#     "type": "object",
#     "properties": {
#         "crime_type_explanation": {"type": "string"},
#         "applicable_law": {
#             "type": "array",
#             "items": {
#                 "type": "object",
#                 "properties": {
#                     "chunk_id": {"type": "string"},
#                     "plain_language_summary": {"type": "string"},
#                 },
#                 "required": ["chunk_id", "plain_language_summary"],
#             },
#         },
#         "regime_note": {"type": "string"},
#         "immediate_actions": {"type": "array", "items": {"type": "string"}},
#         "safety_recommendations": {"type": "array", "items": {"type": "string"}},
#         "draft_complaint": {"type": "string"},
#         "uncovered_aspects": {"type": "string"},
#     },
#     "required": [
#         "crime_type_explanation", "applicable_law", "regime_note",
#         "immediate_actions", "safety_recommendations", "draft_complaint", "uncovered_aspects",
#     ],
# }


# def build_user_message(user_text: str, crime_type: str, confidence: float, retrieved_chunks: list) -> str:
#     context_block = "\n\n".join(
#         f"[{c['id']}] {c['title']} ({c['regime']})\n{c['text']}"
#         for c in retrieved_chunks
#     )
#     return f"""VICTIM'S COMPLAINT:
# {user_text}

# CLASSIFIER OUTPUT:
# crime_type = {crime_type}
# confidence = {confidence}

# RETRIEVED LEGAL CONTEXT:
# {context_block}

# {RESPONSE_SCHEMA_INSTRUCTIONS}
# """


# def _first_sentence(text: str, max_len: int = 220) -> str:
#     """Trim a legal-chunk body down to a short excerpt without an LLM."""
#     text = " ".join(text.split())
#     match = re.split(r"(?<=[.;])\s", text, maxsplit=1)
#     summary = match[0] if match else text
#     if len(summary) > max_len:
#         summary = summary[:max_len].rsplit(" ", 1)[0] + "..."
#     return summary


# def generate_response_offline(user_text: str, crime_type: str, confidence: float,
#                                retrieved_chunks: list) -> dict:
#     """
#     Fully offline substitute for generate_response() - no API key, no
#     network call, no LLM. Builds the same JSON schema from the classifier
#     output, retrieved legal chunks, and the rule-based taxonomy data
#     (SAFETY_RECOMMENDATIONS / URGENT_CATEGORIES / EMERGENCY_MESSAGE, already
#     imported by backend/main.py for Features 9/10) so the app runs without
#     Gemini.

#     Trade-off: `applicable_law` summaries are truncated excerpts of the
#     retrieved chunk text rather than genuinely rewritten plain language, and
#     `draft_complaint` is a template paragraph rather than a context-aware
#     one. Good enough to develop/demo/test against; swap back to
#     generate_response() with a real key for the polished version.
#     """
#     from taxonomy import SAFETY_RECOMMENDATIONS, URGENT_CATEGORIES, EMERGENCY_MESSAGE

#     crime_title = crime_type.replace("_", " ").title()

#     applicable_law = [
#         {"chunk_id": c["id"], "plain_language_summary": _first_sentence(c["text"])}
#         for c in retrieved_chunks
#     ]

#     regimes = {c.get("regime", "") for c in retrieved_chunks}
#     if any("BNS" in r for r in regimes) and any("IPC" in r for r in regimes):
#         regime_note = (
#             "Both BNS (2023) and legacy IPC sections are shown above - which one applies "
#             "depends on whether the incident occurred before or after 1 July 2024."
#         )
#     else:
#         regime_note = ""

#     immediate_actions = [
#         "Report the incident on the National Cybercrime Reporting Portal (cybercrime.gov.in) or call the helpline 1930.",
#         "Preserve all evidence (screenshots, messages, transaction records) before anything can be deleted.",
#     ]
#     if crime_type in URGENT_CATEGORIES:
#         immediate_actions.insert(0, EMERGENCY_MESSAGE)

#     draft_complaint = (
#         f"I am writing to report a {crime_title.lower()} incident. {user_text.strip()} "
#         f"I am submitting this complaint so that appropriate action can be taken against "
#         f"those responsible and to seek assistance in recovering any loss incurred."
#     )

#     return {
#         "crime_type_explanation": f"This appears to be a case of {crime_title.lower()} (classifier confidence {confidence:.0%}).",
#         "applicable_law": applicable_law,
#         "regime_note": regime_note,
#         "immediate_actions": immediate_actions,
#         "safety_recommendations": SAFETY_RECOMMENDATIONS.get(crime_type, []),
#         "draft_complaint": draft_complaint,
#         "uncovered_aspects": (
#             "This response was generated in offline mode (no LLM) - law summaries are "
#             "excerpted directly from retrieved sources rather than rewritten in plain "
#             "language, and nuances not covered by an exact retrieved chunk are not addressed."
#         ),
#     }


# def generate_response(user_text: str, crime_type: str, confidence: float, retrieved_chunks: list,
#                        model: str = "gemini-2.5-flash") -> dict:
#     """
#     model defaults to gemini-2.5-flash - a good cost/quality balance for
#     this task. Gemini model names change fairly often; check
#     https://ai.google.dev/gemini-api/docs/models for the current lineup
#     if this one is retired by the time you run this.

#     If no GEMINI_API_KEY / GOOGLE_API_KEY is set, this transparently falls
#     back to generate_response_offline() instead of raising - so the backend
#     is runnable without any Gemini key. Set FORCE_OFFLINE_MODE=1 to skip the
#     Gemini attempt entirely even when a key is present.
#     """
#     has_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
#     if os.environ.get("FORCE_OFFLINE_MODE") == "1" or not has_key:
#         return generate_response_offline(user_text, crime_type, confidence, retrieved_chunks)

#     from google import genai
#     from google.genai import types

#     client = genai.Client()  # reads GEMINI_API_KEY (or GOOGLE_API_KEY) from env

#     response = client.models.generate_content(
#         model=model,
#         contents=build_user_message(user_text, crime_type, confidence, retrieved_chunks),
#         config=types.GenerateContentConfig(
#             system_instruction=SYSTEM_PROMPT,
#             response_mime_type="application/json",
#             response_schema=RESPONSE_JSON_SCHEMA,
#             temperature=0.2,  # low temperature - this is a factual/legal task, not creative writing
#         ),
#     )

#     try:
#         return json.loads(response.text)
#     except (json.JSONDecodeError, AttributeError):
#         return {
#             "error": "Model did not return valid JSON",
#             "raw_output": getattr(response, "text", str(response)),
#         }


# if __name__ == "__main__":
#     # Example wiring (requires classifier + retriever to be built first)
#     sample_chunks = [
#         {"id": "it_act_66d", "title": "IT Act Section 66D", "text": "...", "regime": "IT Act 2000"},
#         {"id": "npci_dispute_process", "title": "NPCI Dispute Process", "text": "...", "regime": "RBI Circular"},
#     ]
#     result = generate_response(
#         user_text="Someone took money from my bank account using a fake UPI link",
#         crime_type="upi_fraud",
#         confidence=0.94,
#         retrieved_chunks=sample_chunks,
#     )
#     print(json.dumps(result, indent=2))

# rag/llm_reasoning.py







# import os
# import sys

# # Import both retrieval backends gracefully
# try:
#     from rag.retrieve import FAISSRetriever
# except ImportError:
#     FAISSRetriever = None  # Graceful fallback if FAISS/torch isn't installed

# from rag.retrieve_lite import LiteLegalRetriever

# class ComplaintReasoningEngine:
#     def __init__(self, index_dir="./index"):
#         # Read the environment variable (defaults to 'faiss')
#         self.backend_type = os.getenv("RETRIEVER_BACKEND", "faiss").lower()
        
#         print(f"Initializing RAG Engine with backend: {self.backend_type.upper()}")
        
#         if self.backend_type == "faiss" and FAISSRetriever is not None:
#             self.retriever = FAISSRetriever(index_dir=index_dir)
#         else:
#             if self.backend_type == "faiss":
#                 print("Warning: FAISS dependencies not found. Falling back to LITE backend.")
#             self.retriever = LiteLegalRetriever(index_dir=index_dir)

#     def construct_augmented_prompt(self, user_complaint: str, predicted_label: str, incident_date=None):
#         """Assembles the final context window for downstream LLM generation."""
        
#         # Both retrievers now share the exact same public interface!
#         rag_context = self.retriever.retrieve_context(
#             query_text=user_complaint, 
#             predicted_label=predicted_label,
#             top_k=3,
#             incident_date=incident_date
#         )
        
#         # Format the retrieved semantic chunks
#         legal_text = "\n".join([
#             f"- {item['title']} ({item.get('regime', 'General')}): {item['text']}" 
#             for item in rag_context.get("legal_chunks", [])
#         ])
        
#         # Format the deterministic safety rules
#         safety_text = "\n".join([
#             f"- {rec}" for rec in rag_context.get("safety_recommendations", [])
#         ])
        
#         augmented_prompt = f"""
# System Guardrails: You are drafting an official cybercrime case summary. 
# Strict compliance rule: Ground your legal reasoning ONLY in the verified legal chunks provided below.

# [USER COMPLAINT INGESTION]
# "{user_complaint}"

# [PREDICTED AI CATEGORY MATCH]: {predicted_label.upper()}
# [URGENCY TRIGGER STATUS]: {rag_context['is_urgent']}

# [VERIFIED LEGAL KNOWLEDGE BASE ({rag_context.get('execution_mode', 'FAISS_SEARCH')} RESULTS)]
# {legal_text if legal_text.strip() else "- No legal records matched."}

# [DETERMINISTIC EMERGENCY ACTION PLAN]
# {safety_text}

# Response Instruction Format: 
# 1. Write a professional case summary of the user's complaint.
# 2. Cite the specific laws from the verified legal knowledge base that apply to this text.
# 3. List the emergency action plan exactly as provided above.
# """
#         return augmented_prompt, rag_context

# if __name__ == "__main__":
#     # Force lite mode for a quick test
#     os.environ["RETRIEVER_BACKEND"] = "lite"
#     engine = ComplaintReasoningEngine(index_dir="../index")
    
#     prompt, context = engine.construct_augmented_prompt("Someone hacked my instagram", "social_media_hacking")
#     print(prompt)

"""
LLM reasoning layer: takes the classifier output + retrieved legal chunks
and produces a structured, grounded response (plain-language law
explanation, action steps, draft complaint).

This is the layer where hallucination risk lives if not constrained - the
system prompt below explicitly restricts the model to only cite retrieved
chunk IDs, and instructs it to say "not covered in retrieved sources" rather
than invent a section number. This constraint is worth measuring in your
evaluation (see README "hallucination rate" comparison).

Uses Google's Gemini API via the google-genai SDK (the current recommended
SDK - the older google-generativeai package is deprecated as of 2026).
Install:
    pip install -U google-genai
Set GEMINI_API_KEY as an environment variable (get a free key at
https://aistudio.google.com/app/apikey).
"""
import json
import os
import re
import sys
from pathlib import Path

# So `from taxonomy import ...` inside generate_response_offline() works even
# when this module is imported/run standalone (not just via backend/main.py,
# which already adds this path itself before importing us).
_data_dir = str(Path(__file__).parent.parent / "data")
if _data_dir not in sys.path:
    sys.path.append(_data_dir)

SYSTEM_PROMPT = """You are a legal-information assistant helping a cybercrime victim in India understand their situation. You are NOT a lawyer and must not give a legal opinion on the merits of a case.

STRICT RULES:
1. Only reference legal sections that appear in the RETRIEVED LEGAL CONTEXT provided below. Never invent, guess, or recall a section number from your own training - if the retrieved context doesn't cover something, say so explicitly rather than filling the gap.
2. When you reference a section, cite its chunk id exactly as given (e.g. "[it_act_66c]").
3. Explain the law in plain, non-legal language a stressed, non-expert victim can understand.
4. Always include time-sensitive procedural advice (e.g. calling 1930) if the retrieved context includes it.
5. Output valid JSON matching the schema given in the user message - no prose outside the JSON.
"""

RESPONSE_SCHEMA_INSTRUCTIONS = """
Respond with ONLY a JSON object with this exact structure:
{
  "crime_type_explanation": "1-2 sentence plain-language restatement of what happened",
  "applicable_law": [
    {"chunk_id": "...", "plain_language_summary": "..."}
  ],
  "regime_note": "note on whether BNS or IPC applies, if relevant, or empty string",
  "immediate_actions": ["ordered list of what to do right now"],
  "safety_recommendations": ["general safety hardening steps"],
  "draft_complaint": "a formal complaint paragraph the user can copy-paste, written in first person, chronological, professional tone",
  "uncovered_aspects": "anything the user described that the retrieved legal context does NOT address - empty string if none"
}
"""

# JSON schema passed to Gemini's response_schema config - this is what
# actually enforces structured output (response_mime_type alone just asks
# nicely; response_schema constrains generation).
RESPONSE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "crime_type_explanation": {"type": "string"},
        "applicable_law": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "chunk_id": {"type": "string"},
                    "plain_language_summary": {"type": "string"},
                },
                "required": ["chunk_id", "plain_language_summary"],
            },
        },
        "regime_note": {"type": "string"},
        "immediate_actions": {"type": "array", "items": {"type": "string"}},
        "safety_recommendations": {"type": "array", "items": {"type": "string"}},
        "draft_complaint": {"type": "string"},
        "uncovered_aspects": {"type": "string"},
    },
    "required": [
        "crime_type_explanation", "applicable_law", "regime_note",
        "immediate_actions", "safety_recommendations", "draft_complaint", "uncovered_aspects",
    ],
}


def build_user_message(user_text: str, crime_type: str, confidence: float, retrieved_chunks: list) -> str:
    context_block = "\n\n".join(
        f"[{c['id']}] {c['title']} ({c['regime']})\n{c['text']}"
        for c in retrieved_chunks
    )
    return f"""VICTIM'S COMPLAINT:
{user_text}

CLASSIFIER OUTPUT:
crime_type = {crime_type}
confidence = {confidence}

RETRIEVED LEGAL CONTEXT:
{context_block}

{RESPONSE_SCHEMA_INSTRUCTIONS}
"""


def _first_sentence(text: str, max_len: int = 220) -> str:
    """Trim a legal-chunk body down to a short excerpt without an LLM."""
    text = " ".join(text.split())
    match = re.split(r"(?<=[.;])\s", text, maxsplit=1)
    summary = match[0] if match else text
    if len(summary) > max_len:
        summary = summary[:max_len].rsplit(" ", 1)[0] + "..."
    return summary


def generate_response_offline(user_text: str, crime_type: str, confidence: float,
                               retrieved_chunks: list) -> dict:
    """
    Fully offline substitute for generate_response() - no API key, no
    network call, no LLM. Builds the same JSON schema from the classifier
    output, retrieved legal chunks, and the rule-based taxonomy data
    (SAFETY_RECOMMENDATIONS / URGENT_CATEGORIES / EMERGENCY_MESSAGE, already
    imported by backend/main.py for Features 9/10) so the app runs without
    Gemini.

    Trade-off: `applicable_law` summaries are truncated excerpts of the
    retrieved chunk text rather than genuinely rewritten plain language, and
    `draft_complaint` is a template paragraph rather than a context-aware
    one. Good enough to develop/demo/test against; swap back to
    generate_response() with a real key for the polished version.
    """
    from taxonomy import SAFETY_RECOMMENDATIONS, URGENT_CATEGORIES, EMERGENCY_MESSAGE

    crime_title = crime_type.replace("_", " ").title()

    applicable_law = [
        {"chunk_id": c["id"], "plain_language_summary": _first_sentence(c["text"])}
        for c in retrieved_chunks
    ]

    regimes = {c.get("regime", "") for c in retrieved_chunks}
    if any("BNS" in r for r in regimes) and any("IPC" in r for r in regimes):
        regime_note = (
            "Both BNS (2023) and legacy IPC sections are shown above - which one applies "
            "depends on whether the incident occurred before or after 1 July 2024."
        )
    else:
        regime_note = ""

    immediate_actions = [
        "Report the incident on the National Cybercrime Reporting Portal (cybercrime.gov.in) or call the helpline 1930.",
        "Preserve all evidence (screenshots, messages, transaction records) before anything can be deleted.",
    ]
    if crime_type in URGENT_CATEGORIES:
        immediate_actions.insert(0, EMERGENCY_MESSAGE)

    draft_complaint = (
        f"I am writing to report a {crime_title.lower()} incident. {user_text.strip()} "
        f"I am submitting this complaint so that appropriate action can be taken against "
        f"those responsible and to seek assistance in recovering any loss incurred."
    )

    return {
        "crime_type_explanation": f"This appears to be a case of {crime_title.lower()} (classifier confidence {confidence:.0%}).",
        "applicable_law": applicable_law,
        "regime_note": regime_note,
        "immediate_actions": immediate_actions,
        "safety_recommendations": SAFETY_RECOMMENDATIONS.get(crime_type, []),
        "draft_complaint": draft_complaint,
        "uncovered_aspects": (
            "This response was generated in offline mode (no LLM) - law summaries are "
            "excerpted directly from retrieved sources rather than rewritten in plain "
            "language, and nuances not covered by an exact retrieved chunk are not addressed."
        ),
    }


def generate_response(user_text: str, crime_type: str, confidence: float, retrieved_chunks: list,
                       model: str = "gemini-2.5-flash") -> dict:
    """
    model defaults to gemini-2.5-flash - a good cost/quality balance for
    this task. Gemini model names change fairly often; check
    https://ai.google.dev/gemini-api/docs/models for the current lineup
    if this one is retired by the time you run this.

    If no GEMINI_API_KEY / GOOGLE_API_KEY is set, this transparently falls
    back to generate_response_offline() instead of raising - so the backend
    is runnable without any Gemini key. Set FORCE_OFFLINE_MODE=1 to skip the
    Gemini attempt entirely even when a key is present.
    """
    has_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if os.environ.get("FORCE_OFFLINE_MODE") == "1" or not has_key:
        return generate_response_offline(user_text, crime_type, confidence, retrieved_chunks)

    from google import genai
    from google.genai import types

    client = genai.Client()  # reads GEMINI_API_KEY (or GOOGLE_API_KEY) from env

    response = client.models.generate_content(
        model=model,
        contents=build_user_message(user_text, crime_type, confidence, retrieved_chunks),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=RESPONSE_JSON_SCHEMA,
            temperature=0.2,  # low temperature - this is a factual/legal task, not creative writing
        ),
    )

    try:
        return json.loads(response.text)
    except (json.JSONDecodeError, AttributeError):
        return {
            "error": "Model did not return valid JSON",
            "raw_output": getattr(response, "text", str(response)),
        }


if __name__ == "__main__":
    # Example wiring (requires classifier + retriever to be built first)
    sample_chunks = [
        {"id": "it_act_66d", "title": "IT Act Section 66D", "text": "...", "regime": "IT Act 2000"},
        {"id": "npci_dispute_process", "title": "NPCI Dispute Process", "text": "...", "regime": "RBI Circular"},
    ]
    result = generate_response(
        user_text="Someone took money from my bank account using a fake UPI link",
        crime_type="upi_fraud",
        confidence=0.94,
        retrieved_chunks=sample_chunks,
    )
    print(json.dumps(result, indent=2))