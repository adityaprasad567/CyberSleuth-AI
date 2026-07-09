"""
Generates a synthetic labeled dataset for crime-type classification.

This is a bootstrapping strategy: real labeled cybercrime complaint text is
hard to get in bulk, so we generate variations from templates + slot fillers,
then (recommended, not required to run this script) pass a sample through an
LLM paraphraser to add lexical diversity before fine-tuning.

Usage:
    python generate_dataset.py --out dataset.csv --per_template 40
"""
import argparse
import csv
import itertools
import random

from taxonomy import CATEGORIES, LABELS


def fill_template(template: str, slots: dict, rng: random.Random) -> str:
    text = template
    for slot_name in slots:
        if "{" + slot_name + "}" in text:
            text = text.replace("{" + slot_name + "}", rng.choice(slots[slot_name]))
    return text


def generate(per_template: int, seed: int = 42):
    rng = random.Random(seed)
    rows = []
    for label, spec in CATEGORIES.items():
        templates = spec["templates"]
        slots = spec["slots"]
        for template in templates:
            seen = set()
            attempts = 0
            count = 0
            # sample combinations without exact repeats where possible
            while count < per_template and attempts < per_template * 5:
                attempts += 1
                text = fill_template(template, slots, rng)
                if text in seen:
                    continue
                seen.add(text)
                rows.append({"text": text, "label": label})
                count += 1
    rng.shuffle(rows)
    return rows


def split(rows, train_frac=0.7, val_frac=0.15):
    n = len(rows)
    n_train = int(n * train_frac)
    n_val = int(n * val_frac)
    return rows[:n_train], rows[n_train:n_train + n_val], rows[n_train + n_val:]


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["text", "label"])
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out_dir", default=".")
    parser.add_argument("--per_template", type=int, default=40,
                         help="How many variations to generate per template")
    args = parser.parse_args()

    rows = generate(args.per_template)
    train, val, test = split(rows)

    write_csv(f"{args.out_dir}/train.csv", train)
    write_csv(f"{args.out_dir}/val.csv", val)
    write_csv(f"{args.out_dir}/test.csv", test)

    print(f"Total examples: {len(rows)}")
    print(f"Train: {len(train)}  Val: {len(val)}  Test: {len(test)}")
    print(f"Labels: {LABELS}")
