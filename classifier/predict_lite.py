"""
Lightweight predict interface - same output shape as classifier/predict.py's
predict(), backed by the TF-IDF + Logistic Regression pipeline trained by
train_lite.py instead of a DistilBERT checkpoint. No torch/transformers
import anywhere in this file.
"""
import os
import sys

import joblib

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "data"))
from taxonomy import CATEGORIES


def load_model(model_dir):
    """Returns (None, pipeline) to match load_model()'s (tokenizer, model)
    shape used elsewhere - there's no separate tokenizer here, TF-IDF is
    baked into the sklearn Pipeline itself."""
    pipeline = joblib.load(os.path.join(model_dir, "model.joblib"))
    return None, pipeline


def predict(text: str, _tokenizer, pipeline, top_k: int = 3) -> list:
    probs = pipeline.predict_proba([text])[0]
    labels = pipeline.classes_
    ranked = sorted(zip(labels, probs), key=lambda x: -x[1])[:top_k]
    return [
        {
            "label": label,
            "confidence": round(float(prob), 4),
            "legal_tags": CATEGORIES[label]["legal_tags"],
        }
        for label, prob in ranked
    ]


if __name__ == "__main__":
    tok, model = load_model(os.path.join(os.path.dirname(__file__), "crime_classifier_lite"))
    text = " ".join(sys.argv[1:]) or "Someone took money from my bank account using a fake UPI link"
    for r in predict(text, tok, model):
        print(f"{r['label']:20s} {r['confidence']:.2%}  tags={r['legal_tags']}")
