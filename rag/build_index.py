"""
Builds a FAISS vector index over the legal knowledge base chunks.

Requires internet + GPU/CPU with sentence-transformers installed - run this
locally or in Colab, not in a sandbox without network access.

Usage:
    python build_index.py --kb ../legal_kb/legal_chunks.json --out ./index

Install deps first:
    pip install sentence-transformers faiss-cpu --break-system-packages
"""
import argparse
import json
import os
import pickle

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--kb", default="../legal_kb/legal_chunks.json")
    parser.add_argument("--out", default="./index")
    parser.add_argument("--model_name", default="BAAI/bge-small-en-v1.5",
                         help="Swap for a multilingual model if you add Hindi/Bengali legal text")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)

    with open(args.kb, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    model = SentenceTransformer(args.model_name)

    texts = [f"{c['title']}. {c['text']}" for c in chunks]
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=True)
    embeddings = np.array(embeddings, dtype="float32")

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)  # inner product on normalized vectors = cosine similarity
    index.add(embeddings)

    faiss.write_index(index, os.path.join(args.out, "legal_kb.index"))

    with open(os.path.join(args.out, "chunk_metadata.pkl"), "wb") as f:
        pickle.dump(chunks, f)

    with open(os.path.join(args.out, "model_name.txt"), "w") as f:
        f.write(args.model_name)

    print(f"Indexed {len(chunks)} chunks into {args.out}")


if __name__ == "__main__":
    main()
