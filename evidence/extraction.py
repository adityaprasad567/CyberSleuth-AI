"""
Feature 3: AI Evidence Extraction.

Extracts structured entities from evidence text (OCR'd, pasted, or from
filenames/chat exports) and from images (QR codes). Regex-based extraction
is used instead of an LLM call here deliberately: it's deterministic,
free, instant, and auditable - appropriate for structured patterns like
phone numbers, UPI IDs, and IFSC codes that have a fixed shape. An LLM adds
no value (and adds hallucination risk) for this kind of pattern matching.

Optional: name extraction via spaCy NER is stubbed in but skipped gracefully
if spaCy isn't installed - see `extract_names()`.

Install:
    pip install opencv-python-headless --break-system-packages
    # optional, for name extraction:
    pip install spacy --break-system-packages && python -m spacy download en_core_web_sm
"""
import re

EMAIL_DOMAIN_SUFFIXES = (
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "protonmail.com",
    "icloud.com", "rediffmail.com", "live.com", "aol.com",
)

PATTERNS = {
    "phone_numbers": re.compile(r"(?<!\d)(?:\+91[\-\s]?|0)?[6-9]\d{9}(?!\d)"),
    "emails": re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),
    "urls": re.compile(r"https?://[^\s,)\]]+|www\.[^\s,)\]]+"),
    "ifsc_codes": re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b"),
    # UPI handle without a dot-based TLD, e.g. name@okhdfcbank, name@ybl, name@paytm
    "upi_ids_raw": re.compile(r"\b[a-zA-Z0-9.\-_]{2,256}@[a-zA-Z]{2,64}\b"),
    "dates": re.compile(r"\b\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\b|\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4}\b", re.IGNORECASE),
    "times": re.compile(r"\b\d{1,2}:\d{2}\s?(?:AM|PM|am|pm)?\b"),
    # long alphanumeric tokens with both letters and digits - candidate transaction/reference/wallet IDs
    "possible_transaction_ids": re.compile(r"\b(?=[A-Za-z0-9]{10,22}\b)(?=[A-Za-z0-9]*\d)(?=[A-Za-z0-9]*[A-Za-z])[A-Za-z0-9]{10,22}\b"),
    # 9-18 digit numbers not matching phone pattern - candidate bank account numbers
    "possible_bank_accounts": re.compile(r"\b\d{9,18}\b"),
}


def extract_from_text(text: str) -> dict:
    if not text:
        return {}

    email_matches = list(PATTERNS["emails"].finditer(text))
    emails = [m.group() for m in email_matches]
    phones = PATTERNS["phone_numbers"].findall(text)

    # Scrub matched email spans before UPI matching, so "user@gmail.com" doesn't
    # also get picked up as the UPI candidate "user@gmail" from the same span.
    text_without_emails = text
    for m in sorted(email_matches, key=lambda m: m.start(), reverse=True):
        text_without_emails = text_without_emails[:m.start()] + " " * (m.end() - m.start()) + text_without_emails[m.end():]
    upi_ids = PATTERNS["upi_ids_raw"].findall(text_without_emails)

    # Bank accounts: digit runs that aren't actually phone numbers
    bank_candidates = PATTERNS["possible_bank_accounts"].findall(text)
    phone_digits = {re.sub(r"\D", "", p)[-10:] for p in phones}
    bank_accounts = [b for b in bank_candidates if b[-10:] not in phone_digits]

    ifsc_codes = sorted(set(PATTERNS["ifsc_codes"].findall(text)))

    # Transaction ID candidates: exclude anything already classified as an IFSC code
    txn_candidates = PATTERNS["possible_transaction_ids"].findall(text)
    txn_ids = [t for t in txn_candidates if t not in ifsc_codes]

    result = {
        "phone_numbers": sorted(set(phones)),
        "emails": sorted(set(emails)),
        "urls": sorted(set(PATTERNS["urls"].findall(text))),
        "upi_ids": sorted(set(upi_ids)),
        "ifsc_codes": ifsc_codes,
        "possible_bank_accounts": sorted(set(bank_accounts)),
        "possible_transaction_ids": sorted(set(txn_ids)),
        "dates": sorted(set(PATTERNS["dates"].findall(text))),
        "times": sorted(set(PATTERNS["times"].findall(text))),
    }
    return {k: v for k, v in result.items() if v}


def extract_names(text: str) -> list:
    """Optional NER-based name extraction. Returns [] if spaCy isn't installed
    rather than raising - name extraction from free text is a nice-to-have,
    not a blocker for the rest of the pipeline."""
    try:
        import spacy
        nlp = spacy.load("en_core_web_sm")
    except (ImportError, OSError):
        return []
    doc = nlp(text)
    return sorted({ent.text for ent in doc.ents if ent.label_ == "PERSON"})


def extract_qr_codes(image_path: str) -> list:
    """Decodes any QR codes present in an image using OpenCV (no external
    zbar system dependency needed, unlike pyzbar)."""
    import cv2
    img = cv2.imread(image_path)
    if img is None:
        return []
    detector = cv2.QRCodeDetector()
    retval, decoded_info, points, _ = detector.detectAndDecodeMulti(img)
    if not retval:
        return []
    return [text for text in decoded_info if text]


def extract_from_evidence_file(file_path: str, file_type: str, ocr_text: str = "") -> dict:
    """
    Main entry point used by the upload endpoint.
    file_type: mime-type-ish string, e.g. "image/png", "application/pdf", "text/plain"
    ocr_text: pre-extracted text if the caller already ran OCR/PDF-text-extraction
              upstream (Phase 2 doesn't include OCR itself - see README note)
    """
    entities = extract_from_text(ocr_text) if ocr_text else {}

    if file_type.startswith("image/"):
        qr_results = extract_qr_codes(file_path)
        if qr_results:
            entities["qr_code_contents"] = qr_results
            # QR codes often just encode a UPI payment URI - extract further
            for qr_text in qr_results:
                nested = extract_from_text(qr_text)
                for k, v in nested.items():
                    entities[k] = sorted(set(entities.get(k, []) + v))

    return entities
