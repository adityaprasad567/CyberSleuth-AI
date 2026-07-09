"""
Feature 8: Evidence Integrity.

Generates a SHA-256 hash for an uploaded file, computed in chunks so large
files (videos, PDFs) don't need to be loaded into memory at once.
"""
import hashlib


def compute_sha256(file_path: str, chunk_size: int = 8192) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python hashing.py <file_path>")
    else:
        print(compute_sha256(sys.argv[1]))
