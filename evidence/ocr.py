"""
Feature 13: OCR pipeline for evidence images.

Extracts readable text from uploaded screenshots/photos/scanned documents so
it can flow through the EXACT same path as manually-typed complaint text:

    Image -> OCR -> extracted text -> existing extraction.py (entities)
          -> existing classifier (classify(), unmodified) -> crime prediction

This module only produces plain text. It never touches the classifier or
the regex entity patterns in extraction.py - those consume this module's
output exactly as if a user had typed it into the complaint text box.

Two backends, chosen via OCR_BACKEND env var (same pattern as
CLASSIFIER_BACKEND / RETRIEVER_BACKEND elsewhere in this app):
  - OCR_BACKEND=easyocr   (default) - deep-learning OCR, best accuracy on
    noisy phone screenshots/photos, no system dependency beyond the pip
    package. First call downloads ~64MB of model weights (cached afterward
    under ~/.EasyOCR) - expect a one-time delay on first request.
  - OCR_BACKEND=tesseract - pytesseract, needs the `tesseract-ocr` system
    binary installed separately. Lighter/faster cold start, slightly lower
    accuracy on low-quality images.

Install:
    pip install easyocr pillow --break-system-packages
    # OR, for the tesseract backend instead:
    pip install pytesseract pillow --break-system-packages
    # + system package: apt-get install tesseract-ocr   (Linux)
    #                    brew install tesseract           (Mac)
    #                    choco install tesseract          (Windows)
"""
import io
import os

from PIL import Image

OCR_BACKEND = os.environ.get("OCR_BACKEND", "easyocr").lower()

SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}

MAX_DIMENSION = 2200               # downscale anything larger - keeps OCR fast & memory-bounded
MAX_INPUT_BYTES = 15 * 1024 * 1024  # refuse absurdly large uploads outright (before even decoding)

_reader = None  # EasyOCR Reader singleton - loading the model is expensive (~seconds); do it once per process


def is_supported_image(file_type: str) -> bool:
    """True for any image/* content-type - matches the JPG/JPEG/PNG/WEBP
    support required, while staying permissive about the exact subtype
    string different browsers/OSes send."""
    ft = (file_type or "").lower()
    return ft in SUPPORTED_IMAGE_TYPES or ft.startswith("image/")


def _get_easyocr_reader():
    """Lazy singleton - EasyOCR's Reader() call loads model weights from
    disk/network, so we only want to pay that cost once, not per-request."""
    global _reader
    if _reader is None:
        import easyocr
        _reader = easyocr.Reader(["en"], gpu=False)
    return _reader


def _preprocess_image(file_path: str) -> bytes:
    """
    Loads the image, normalizes color mode, and downsizes if larger than
    MAX_DIMENSION on its longest side. Phone-camera photos can be
    4000x3000+ and several MB - OCR accuracy plateaus well below that
    resolution, so this keeps processing fast and memory-bounded without
    hurting recognition quality. Always re-encodes as JPEG for a
    consistent, compressed input to the OCR backend.
    """
    img = Image.open(file_path)
    img = img.convert("RGB")  # normalizes PNG alpha channels, WEBP, CMYK, etc. to something OCR libs expect

    w, h = img.size
    longest = max(w, h)
    if longest > MAX_DIMENSION:
        scale = MAX_DIMENSION / longest
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def _ocr_easyocr(image_bytes: bytes) -> str:
    import numpy as np
    reader = _get_easyocr_reader()
    img = Image.open(io.BytesIO(image_bytes))
    # paragraph=True groups nearby text boxes into reading-order blocks,
    # which is what gives us "preserve line breaks where possible" - each
    # block becomes one line in the output instead of one line per detected
    # word/fragment.
    results = reader.readtext(np.array(img), detail=1, paragraph=True)
    lines = [text.strip() for _, text in results if text and text.strip()]
    return "\n".join(lines)


def _ocr_tesseract(image_bytes: bytes) -> str:
    import pytesseract
    img = Image.open(io.BytesIO(image_bytes))
    text = pytesseract.image_to_string(img)
    # Tesseract emits a lot of stray blank lines around detected blocks;
    # collapse those while keeping genuine single line breaks intact.
    lines = [ln.strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def extract_text_from_image(file_path: str, file_type: str = "") -> str:
    """
    Main entry point, called from backend/main.py's /evidence/upload.

    Returns extracted text, or "" if nothing readable was found, the file
    isn't a supported image type, or the image couldn't be processed.
    NEVER raises - a corrupt/unreadable image must degrade gracefully to
    "no text found", not crash the upload endpoint. Decorative graphics
    (logos, icons, plain photos with no text) simply produce "" here,
    which the caller reports as "No readable text detected...".
    """
    if not is_supported_image(file_type):
        return ""
    try:
        if os.path.getsize(file_path) > MAX_INPUT_BYTES:
            return ""
        image_bytes = _preprocess_image(file_path)
    except Exception:
        return ""

    try:
        if OCR_BACKEND == "tesseract":
            return _ocr_tesseract(image_bytes)
        return _ocr_easyocr(image_bytes)
    except Exception:
        # OCR backend failed to load/run (first-run model download blocked,
        # corrupt image bytes, unsupported color mode, etc.) - degrade to
        # "no text found" rather than 500ing the whole upload request.
        return ""
