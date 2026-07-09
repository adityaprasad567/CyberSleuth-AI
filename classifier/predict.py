"""
Loads the fine-tuned classifier and predicts crime type for new complaint text.

Usage:
    python predict.py --text "Someone took money from my account using a fake UPI link"
"""
import argparse
import sys

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

sys.path.append("../data")
from taxonomy import CATEGORIES


def load_model(model_dir):
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForSequenceClassification.from_pretrained(model_dir)
    model.eval()
    return tokenizer, model


def predict(text, tokenizer, model, top_k=3):
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=128)
    with torch.no_grad():
        logits = model(**inputs).logits
    probs = torch.softmax(logits, dim=-1)[0]
    top_probs, top_ids = torch.topk(probs, k=min(top_k, probs.shape[0]))

    results = []
    for prob, idx in zip(top_probs.tolist(), top_ids.tolist()):
        label = model.config.id2label[idx]
        legal_tags = CATEGORIES.get(label, {}).get("legal_tags", [])
        results.append({"label": label, "confidence": round(prob, 4), "legal_tags": legal_tags})
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", required=True)
    parser.add_argument("--model_dir", default="./crime_classifier")
    parser.add_argument("--top_k", type=int, default=3)
    args = parser.parse_args()

    tokenizer, model = load_model(args.model_dir)
    results = predict(args.text, tokenizer, model, top_k=args.top_k)

    print(f"\nInput: {args.text}\n")
    for r in results:
        print(f"  {r['label']:20s} conf={r['confidence']:.2%}  legal_tags={r['legal_tags']}")
