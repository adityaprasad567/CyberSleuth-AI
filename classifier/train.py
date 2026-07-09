# """
# Fine-tunes a transformer for cybercrime crime-type classification.

# Run in Colab (free GPU) or locally with a GPU. Requires internet access to
# download the base model and dataset (this script itself has no network
# dependency beyond that).

# Usage:
#     python train.py --model_name distilbert-base-uncased --epochs 4

# For Hindi/Bengali support later, swap model_name for:
#     ai4bharat/indic-bert
# or a multilingual model like:
#     bert-base-multilingual-cased

# Install deps first:
#     pip install transformers datasets scikit-learn torch accelerate --break-system-packages
# """
# import argparse
# import numpy as np
# import evaluate
# from datasets import load_dataset
# from sklearn.metrics import classification_report
# from transformers import (
#     AutoTokenizer,
#     AutoModelForSequenceClassification,
#     TrainingArguments,
#     Trainer,
#     DataCollatorWithPadding,
# )

# import sys
# sys.path.append("../data")
# from taxonomy import LABELS

# LABEL2ID = {label: i for i, label in enumerate(LABELS)}
# ID2LABEL = {i: label for i, label in enumerate(LABELS)}


# def main():
#     parser = argparse.ArgumentParser()
#     parser.add_argument("--model_name", default="distilbert-base-uncased")
#     parser.add_argument("--train_file", default="../data/train.csv")
#     parser.add_argument("--val_file", default="../data/val.csv")
#     parser.add_argument("--test_file", default="../data/test.csv")
#     parser.add_argument("--epochs", type=int, default=4)
#     parser.add_argument("--batch_size", type=int, default=16)
#     parser.add_argument("--lr", type=float, default=2e-5)
#     parser.add_argument("--output_dir", default="./crime_classifier")
#     args = parser.parse_args()

#     raw = load_dataset(
#         "csv",
#         data_files={"train": args.train_file, "validation": args.val_file, "test": args.test_file},
#     )

#     def encode_labels(example):
#         example["label"] = LABEL2ID[example["label"]]
#         return example

#     raw = raw.map(encode_labels)

#     tokenizer = AutoTokenizer.from_pretrained(args.model_name)

#     def tokenize(batch):
#         return tokenizer(batch["text"], truncation=True, max_length=128)

#     tokenized = raw.map(tokenize, batched=True)
#     data_collator = DataCollatorWithPadding(tokenizer=tokenizer)

#     model = AutoModelForSequenceClassification.from_pretrained(
#         args.model_name,
#         num_labels=len(LABELS),
#         id2label=ID2LABEL,
#         label2id=LABEL2ID,
#     )

#     accuracy = evaluate.load("accuracy")
#     f1 = evaluate.load("f1")

#     def compute_metrics(eval_pred):
#         logits, labels = eval_pred
#         preds = np.argmax(logits, axis=-1)
#         return {
#             "accuracy": accuracy.compute(predictions=preds, references=labels)["accuracy"],
#             "f1_macro": f1.compute(predictions=preds, references=labels, average="macro")["f1"],
#         }

#     training_args = TrainingArguments(
#         output_dir=args.output_dir,
#         learning_rate=args.lr,
#         per_device_train_batch_size=args.batch_size,
#         per_device_eval_batch_size=args.batch_size,
#         num_train_epochs=args.epochs,
#         weight_decay=0.01,
#         eval_strategy="epoch",
#         save_strategy="epoch",
#         load_best_model_at_end=True,
#         metric_for_best_model="f1_macro",
#         logging_steps=10,
#     )

#     trainer = Trainer(
#         model=model,
#         args=training_args,
#         train_dataset=tokenized["train"],
#         eval_dataset=tokenized["validation"],
#         tokenizer=tokenizer,
#         data_collator=data_collator,
#         compute_metrics=compute_metrics,
#     )

#     trainer.train()

#     # Final evaluation on held-out test set with per-class report
#     test_preds = trainer.predict(tokenized["test"])
#     y_pred = np.argmax(test_preds.predictions, axis=-1)
#     y_true = test_preds.label_ids

#     print("\n=== Test set classification report ===")
#     print(classification_report(
#         y_true, y_pred, target_names=LABELS, zero_division=0
#     ))

#     trainer.save_model(args.output_dir)
#     tokenizer.save_pretrained(args.output_dir)
#     print(f"\nModel saved to {args.output_dir}")


# if __name__ == "__main__":
#     main()

import argparse
import sys

import evaluate
import numpy as np
from datasets import load_dataset, Value
from sklearn.metrics import classification_report
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
    DataCollatorWithPadding,
)

sys.path.append("../data")
from taxonomy import LABELS

LABEL2ID = {label: i for i, label in enumerate(LABELS)}
ID2LABEL = {i: label for i, label in enumerate(LABELS)}


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--model_name", default="distilbert-base-uncased")
    parser.add_argument("--train_file", default="../data/train.csv")
    parser.add_argument("--val_file", default="../data/val.csv")
    parser.add_argument("--test_file", default="../data/test.csv")
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--output_dir", default="./crime_classifier")

    args = parser.parse_args()

    # -----------------------------
    # Load Dataset
    # -----------------------------
    raw = load_dataset(
        "csv",
        data_files={
            "train": args.train_file,
            "validation": args.val_file,
            "test": args.test_file,
        },
    )

    print("\n========== BEFORE ENCODING ==========")
    print(raw["train"][0])
    print(raw["train"].features)

    # -----------------------------
    # Encode Labels
    # -----------------------------
    def encode_labels(example):
        return {
            "text": example["text"],
            "label": LABEL2ID[example["label"]],
        }

    raw = raw.map(encode_labels)

    print("\n========== AFTER ENCODING ==========")
    print(raw["train"][0])
    print(raw["train"].features)

    raw = raw.cast_column("label", Value("int64"))

    print("\n========== AFTER CAST ==========")
    print(raw["train"][0])
    print(raw["train"].features)

    # -----------------------------
    # Tokenizer
    # -----------------------------
    tokenizer = AutoTokenizer.from_pretrained(args.model_name)

    def tokenize(batch):
        return tokenizer(
            batch["text"],
            truncation=True,
            max_length=128,
        )

    tokenized = raw.map(
        tokenize,
        batched=True,
        remove_columns=["text"],
    )

    print("\n========== TOKENIZED ==========")
    print(tokenized["train"].column_names)
    print(tokenized["train"].features)
    print(tokenized["train"][0])

    data_collator = DataCollatorWithPadding(tokenizer=tokenizer)

    # -----------------------------
    # Model
    # -----------------------------
    model = AutoModelForSequenceClassification.from_pretrained(
        args.model_name,
        num_labels=len(LABELS),
        id2label=ID2LABEL,
        label2id=LABEL2ID,
    )

    accuracy = evaluate.load("accuracy")
    f1 = evaluate.load("f1")

    def compute_metrics(eval_pred):
        logits, labels = eval_pred
        preds = np.argmax(logits, axis=-1)

        return {
            "accuracy": accuracy.compute(
                predictions=preds,
                references=labels,
            )["accuracy"],
            "f1_macro": f1.compute(
                predictions=preds,
                references=labels,
                average="macro",
            )["f1"],
        }

    training_args = TrainingArguments(
        output_dir=args.output_dir,
        learning_rate=args.lr,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        num_train_epochs=args.epochs,
        weight_decay=0.01,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1_macro",
        logging_steps=10,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized["train"],
        eval_dataset=tokenized["validation"],
        processing_class=tokenizer,
        # tokenizer=tokenizer,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
    )

    trainer.train()

    test_preds = trainer.predict(tokenized["test"])

    y_pred = np.argmax(test_preds.predictions, axis=-1)
    y_true = test_preds.label_ids

    print("\n========== TEST REPORT ==========")
    print(
        classification_report(
            y_true,
            y_pred,
            target_names=LABELS,
            zero_division=0,
        )
    )

    trainer.save_model(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)

    print(f"\nModel saved to {args.output_dir}")


if __name__ == "__main__":
    main()