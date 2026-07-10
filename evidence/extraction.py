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
    ocr_text: pre-extracted text - now populated automatically by ocr.py for
              image uploads (see backend/main.py), or passed in directly by
              the caller for non-image evidence (e.g. pasted chat exports).
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


# --- Feature 13: OCR evidence summary (new, additive) ---
#
# Broader entity set specifically for the OCR pipeline's "Key Information" /
# evidence-summary JSON. Kept as a SEPARATE function from extract_from_text()
# above (used by /completeness-check, /generate-report's extracted_entities,
# and the PDF's "Extracted Information" section) so nothing already relying
# on that function's exact key set changes shape. This one returns the wider
# field list requested for per-image evidence summaries.

BANK_NAME_PATTERN = re.compile(
    r"\b(?:State Bank of India|SBI|HDFC Bank|HDFC|ICICI Bank|ICICI|Axis Bank|"
    r"Kotak Mahindra Bank|Kotak|Punjab National Bank|PNB|Bank of Baroda|BOB|"
    r"Canara Bank|Union Bank of India|Union Bank|IDBI Bank|IDBI|IndusInd Bank|"
    r"Yes Bank|Bank of India|BOI|Central Bank of India|Indian Bank|"
    r"Indian Overseas Bank|UCO Bank|Federal Bank|South Indian Bank|"
    r"RBL Bank|Standard Chartered|HSBC|Citibank|Paytm Payments Bank|"
    r"Airtel Payments Bank)\b",
    re.IGNORECASE,
)
AMOUNT_PATTERN = re.compile(r"(?:\u20b9|Rs\.?|INR)\s?[\d,]+(?:\.\d{1,2})?", re.IGNORECASE)
IP_ADDRESS_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
DEVICE_ID_PATTERN = re.compile(r"\b\d{15}\b")  # IMEI-length numbers
OTP_PATTERN = re.compile(
    r"\bOTP\b[^0-9]{0,15}(\d{4,8})|(\d{4,8})[^a-zA-Z0-9]{0,10}\bis\b[^a-zA-Z0-9]{0,5}\bOTP\b",
    re.IGNORECASE,
)
ORDER_ID_PATTERN = re.compile(r"\bOrder\s*(?:ID|No\.?|#)?\s*[:\-]?\s*([A-Za-z0-9\-]{5,24})", re.IGNORECASE)
REFERENCE_PATTERN = re.compile(r"\bRef(?:erence)?\s*(?:No\.?|#|ID)?\s*[:\-]?\s*([A-Za-z0-9\-]{5,24})", re.IGNORECASE)
WALLET_PATTERN = re.compile(r"\bWallet\s*(?:ID)?\s*[:\-]?\s*([A-Za-z0-9\-]{5,24})", re.IGNORECASE)
SOCIAL_HANDLE_PATTERN = re.compile(r"(?<![\w.])@([A-Za-z][A-Za-z0-9_.]{1,29})\b")


def _mask_account_number(number: str) -> str:
    """Masks all but the last 4 digits, e.g. '1234567890123' -> 'XXXXXXXXX0123'.
    Used only in the evidence-summary output - the unmasked value stays
    available in the regular extract_from_text() entities for internal use."""
    if len(number) <= 4:
        return number
    return ("X" * (len(number) - 4)) + number[-4:]


def build_evidence_summary(text: str) -> dict:
    """
    Builds the structured per-image evidence summary JSON:
      { phone_numbers, emails, upi_ids, transaction_ids, urls, bank_names,
        amounts, dates, times, social_handles, reference_numbers,
        wallet_ids, order_ids, otps, ip_addresses, device_ids,
        masked_account_numbers, summary }

    All values are lists (possibly empty) except `summary`, a one-line
    human-readable recap. Never raises - returns an all-empty shape for
    empty/unreadable input so the caller can always safely index into it.
    """
    empty = {
        "phone_numbers": [], "emails": [], "upi_ids": [], "transaction_ids": [],
        "urls": [], "bank_names": [], "amounts": [], "dates": [], "times": [],
        "social_handles": [], "reference_numbers": [], "wallet_ids": [],
        "order_ids": [], "otps": [], "ip_addresses": [], "device_ids": [],
        "masked_account_numbers": [], "summary": "",
    }
    if not text or not text.strip():
        return empty

    # Reuses the same well-tested core regexes (phones, emails, urls, upi,
    # dates, times, ifsc, txn ids, bank accounts) - not duplicated here.
    base = extract_from_text(text)

    otps = []
    for m in OTP_PATTERN.finditer(text):
        otps.append(m.group(1) or m.group(2))

    social_handles = sorted(set(SOCIAL_HANDLE_PATTERN.findall(text)) - set(base.get("upi_ids", [])))

    result = {
        "phone_numbers": base.get("phone_numbers", []),
        "emails": base.get("emails", []),
        "upi_ids": base.get("upi_ids", []),
        "transaction_ids": base.get("possible_transaction_ids", []),
        "urls": base.get("urls", []),
        "bank_names": sorted(set(BANK_NAME_PATTERN.findall(text))),
        "amounts": sorted(set(AMOUNT_PATTERN.findall(text))),
        "dates": base.get("dates", []),
        "times": base.get("times", []),
        "social_handles": [f"@{h}" for h in social_handles],
        "reference_numbers": sorted(set(REFERENCE_PATTERN.findall(text))),
        "wallet_ids": sorted(set(WALLET_PATTERN.findall(text))),
        "order_ids": sorted(set(ORDER_ID_PATTERN.findall(text))),
        "otps": sorted(set(o for o in otps if o)),
        "ip_addresses": sorted(set(IP_ADDRESS_PATTERN.findall(text))),
        "device_ids": sorted(set(DEVICE_ID_PATTERN.findall(text))),
        "masked_account_numbers": sorted({_mask_account_number(n) for n in base.get("possible_bank_accounts", [])}),
    }

    found_parts = []
    if result["bank_names"]:
        found_parts.append(f"{len(result['bank_names'])} bank name(s)")
    if result["amounts"]:
        found_parts.append(f"{len(result['amounts'])} amount(s)")
    if result["upi_ids"]:
        found_parts.append(f"{len(result['upi_ids'])} UPI ID(s)")
    if result["transaction_ids"]:
        found_parts.append(f"{len(result['transaction_ids'])} transaction ID(s)")
    if result["phone_numbers"]:
        found_parts.append(f"{len(result['phone_numbers'])} phone number(s)")
    if result["emails"]:
        found_parts.append(f"{len(result['emails'])} email(s)")
    result["summary"] = (
        "Detected " + ", ".join(found_parts) + " in the uploaded evidence."
        if found_parts else "No structured identifiers detected in the extracted text."
    )

    return result
