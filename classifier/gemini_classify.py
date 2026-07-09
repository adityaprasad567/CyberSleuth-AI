"""
Gemini-based crime-type classifier - a drop-in replacement for predict.py's
load_model()/predict() when you don't want to ship/train the local DistilBERT
model. Same output shape as predict.predict(): a list of
{"label", "confidence", "legal_tags"} dicts, ranked highest confidence first.

Why you'd use this instead of the local model:
- No torch/transformers/model checkpoint to train or deploy (that's the
  "big file" problem - the local model + its deps easily add 1GB+ to a
  deployment image).
- With only ~150 synthetic training examples, the local model's accuracy is
  weak (see MIN_CONFIDENCE_THRESHOLD gating in taxonomy.py). Gemini already
  has strong general-purpose language understanding, so for a small demo/
  portfolio project this will likely classify real free-text complaints
  more reliably out of the box.

Trade-off: this makes a network call per request (latency + cost, though
Gemini's free tier is generous), and depends on GEMINI_API_KEY being set -
there's no offline fallback for classification specifically (unlike
llm_reasoning.py's generate_response_offline, which only offline-fallbacks
the *explanation* layer, not classification).

Toggle which classifier backend the backend uses via env var:
    CLASSIFIER_BACKEND=gemini   (this file)
    CLASSIFIER_BACKEND=local    (default - classifier/predict.py)
"""
import json
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "data"))
from taxonomy import LABELS, CATEGORIES

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "rankings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string", "enum": LABELS},
                    "confidence": {"type": "number"},
                },
                "required": ["label", "confidence"],
            },
        }
    },
    "required": ["rankings"],
}

SYSTEM_PROMPT = f"""You are a cybercrime complaint classifier for Indian cybercrime law.
Classify the complaint text into one of these categories: {", ".join(LABELS)}.

Return a ranked list of ALL {len(LABELS)} categories in the "rankings" field,
most likely first, each with a confidence score between 0 and 1 reflecting
your genuine certainty (they don't need to sum to 1 - if the text is vague,
gibberish, or doesn't clearly match any category, give LOW confidence scores
across the board rather than confidently picking one at random. Being honest
about uncertainty is more important than always naming a top category)."""


def classify_with_gemini(text: str, top_k: int = 3, model: str = "gemini-2.5-flash") -> list:
    """
    Returns the same shape as classifier/predict.py's predict():
    [{"label": str, "confidence": float, "legal_tags": [str, ...]}, ...]
    sorted by confidence descending, truncated to top_k.
    """
    from google import genai
    from google.genai import types

    client = genai.Client()  # reads GEMINI_API_KEY / GOOGLE_API_KEY from env

    response = client.models.generate_content(
        model=model,
        contents=f"Complaint text:\n{text}",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=RESPONSE_SCHEMA,
            temperature=0.1,
        ),
    )

    try:
        parsed = json.loads(response.text)
        rankings = parsed["rankings"]
    except (json.JSONDecodeError, KeyError, AttributeError):
        # Fail safe rather than crash the request - treat as fully uncertain.
        rankings = [{"label": label, "confidence": 1.0 / len(LABELS)} for label in LABELS]

    rankings = sorted(rankings, key=lambda r: -r["confidence"])[:top_k]
    return [
        {
            "label": r["label"],
            "confidence": round(float(r["confidence"]), 4),
            "legal_tags": CATEGORIES[r["label"]]["legal_tags"],
        }
        for r in rankings
    ]


if __name__ == "__main__":
    import sys as _sys
    text = " ".join(_sys.argv[1:]) or "Someone took money from my bank account using a fake UPI link"
    for r in classify_with_gemini(text):
        print(f"{r['label']:20s} {r['confidence']:.2%}  tags={r['legal_tags']}")
