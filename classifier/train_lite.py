# """
# Lightweight classifier training - TF-IDF + Logistic Regression via
# scikit-learn, no torch/transformers/GPU needed.

# Why this instead of the DistilBERT classifier (train.py):
# - With only ~150 training rows, a fine-tuned transformer has very little
#   signal to learn from anyway (see the 19% confidence / majority-class
#   collapse issue we hit). A simple linear model on TF-IDF features is not
#   meaningfully less accurate at this data scale, and is dramatically
#   smaller/faster: no torch (100s of MB - GBs with CUDA deps), no GPU, no
#   training loop - fits in under a second.
# - Total install size for this path (scikit-learn + numpy + scipy, no torch/
#   transformers/datasets/evaluate/accelerate) is roughly 100-150MB, vs
#   multiple GB for the transformer stack.

# Usage:
#     python train_lite.py
# Reads data/train.csv + data/val.csv (val is folded into training here, since
# with this little data held-out validation isn't very informative anyway -
# data/test.csv is still used for a final honest accuracy check).
# Saves to classifier/crime_classifier_lite/model.joblib
# """
# import csv
# import os

# import joblib
# from sklearn.feature_extraction.text import TfidfVectorizer
# from sklearn.linear_model import LogisticRegression
# from sklearn.pipeline import Pipeline
# from sklearn.metrics import classification_report

# DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
# MODEL_DIR = os.path.join(os.path.dirname(__file__), "crime_classifier_lite")


# def _read_csv(path):
#     texts, labels = [], []
#     with open(path, encoding="utf-8") as f:
#         for row in csv.DictReader(f):
#             texts.append(row["text"])
#             labels.append(row["label"])
#     return texts, labels


# def main():
#     train_texts, train_labels = _read_csv(os.path.join(DATA_DIR, "train.csv"))
#     val_path = os.path.join(DATA_DIR, "val.csv")
#     if os.path.exists(val_path):
#         v_texts, v_labels = _read_csv(val_path)
#         train_texts += v_texts
#         train_labels += v_labels

#     pipeline = Pipeline([
#         ("tfidf", TfidfVectorizer(
#             ngram_range=(1, 2), min_df=1, max_features=5000, sublinear_tf=True,
#         )),
#         ("clf", LogisticRegression(
#             max_iter=2000, class_weight="balanced", C=2.0,
#         )),
#     ])
#     pipeline.fit(train_texts, train_labels)

#     os.makedirs(MODEL_DIR, exist_ok=True)
#     joblib.dump(pipeline, os.path.join(MODEL_DIR, "model.joblib"))
#     print(f"Saved model to {MODEL_DIR}/model.joblib")

#     test_path = os.path.join(DATA_DIR, "test.csv")
#     if os.path.exists(test_path):
#         test_texts, test_labels = _read_csv(test_path)
#         preds = pipeline.predict(test_texts)
#         print("\n--- Held-out test set performance ---")
#         print(classification_report(test_labels, preds, zero_division=0))


# if __name__ == "__main__":
#     main()

"""
Lightweight classifier training - TF-IDF + Logistic Regression via
scikit-learn, no torch/transformers/GPU needed.

Why this instead of the DistilBERT classifier (train.py):
- With ~450 training rows across 51 classes, a fine-tuned transformer has very little
  signal to learn from anyway. A simple linear model on TF-IDF features is not
  meaningfully less accurate at this data scale, and is dramatically
  smaller/faster: no torch (100s of MB - GBs with CUDA deps), no GPU, no
  training loop - fits in under a second.
- Total install size for this path (scikit-learn + numpy + scipy, no torch/
  transformers/datasets/evaluate/accelerate) is roughly 100-150MB, vs
  multiple GB for the transformer stack.

Usage:
    python train_lite.py
Reads data/train.csv + data/val.csv (val is folded into training here).
Saves to classifier/crime_classifier_lite/model.joblib
"""
import csv
import os

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MODEL_DIR = os.path.join(os.path.dirname(__file__), "crime_classifier_lite")


def _read_csv(path):
    texts, labels = [], []
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            texts.append(row["text"])
            labels.append(row["label"])
    return texts, labels


def main():
    print("Loading 51-class training data...")
    train_texts, train_labels = _read_csv(os.path.join(DATA_DIR, "train.csv"))
    
    val_path = os.path.join(DATA_DIR, "val.csv")
    if os.path.exists(val_path):
        v_texts, v_labels = _read_csv(val_path)
        train_texts += v_texts
        train_labels += v_labels

    print(f"Training TF-IDF Logistic Regression pipeline on {len(train_texts)} samples...")
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            ngram_range=(1, 2), min_df=1, max_features=5000, sublinear_tf=True,
        )),
        ("clf", LogisticRegression(
            max_iter=2000, class_weight="balanced", C=2.0,
        )),
    ])
    pipeline.fit(train_texts, train_labels)

    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(pipeline, os.path.join(MODEL_DIR, "model.joblib"))
    print(f"✅ Saved model to {MODEL_DIR}/model.joblib")

    # Fallback logic to grab the newly extended test set if available
    test_path = os.path.join(DATA_DIR, "test_extended.csv")
    if not os.path.exists(test_path):
        test_path = os.path.join(DATA_DIR, "test.csv")

    if os.path.exists(test_path):
        print(f"\nEvaluating on {os.path.basename(test_path)}...")
        test_texts, test_labels = _read_csv(test_path)
        preds = pipeline.predict(test_texts)
        print("\n--- Held-out test set performance ---")
        print(classification_report(test_labels, preds, zero_division=0))


if __name__ == "__main__":
    main()