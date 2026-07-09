"""
Feature 5: Complaint Completeness Checker.

Rule-based (not LLM-based) deliberately: whether a transaction ID or bank
name is present is a factual yes/no that doesn't benefit from an LLM call,
and rule-based means this works instantly and identically every time.

Usage:
    from completeness import check_completeness
    result = check_completeness("upi_fraud", context)
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent / "data"))
from taxonomy import REQUIRED_FIELDS, FIELD_LABELS


def _check_field(key: str, context: dict) -> bool:
    entities = context.get("extracted_entities") or {}
    suspect = context.get("suspect_details") or {}

    if key == "description":
        return bool(context.get("description", "").strip())
    if key == "crime_type":
        return bool(context.get("crime_type"))
    if key == "evidence":
        return context.get("evidence_count", 0) > 0
    if key == "transaction_id":
        return bool(entities.get("possible_transaction_ids"))
    if key == "bank_name":
        return bool(context.get("platform")) or bool(entities.get("ifsc_codes"))
    if key == "financial_loss":
        return bool(context.get("financial_loss"))
    if key == "suspect_contact":
        return bool(
            suspect.get("phone") or suspect.get("upi_id")
            or entities.get("upi_ids") or entities.get("phone_numbers")
        )
    return False


def check_completeness(crime_type: str, context: dict) -> dict:
    """
    context expected keys (all optional except crime_type is used for lookup):
      description: str (the user's complaint text)
      evidence_count: int
      extracted_entities: dict (merged across evidence, from evidence/storage.py)
      platform: str
      financial_loss: str
      suspect_details: dict (phone, upi_id, ...)

    Returns:
      {
        "crime_type": ...,
        "fields": [{"key", "label", "present"}, ...],
        "missing_count": int,
        "is_complete": bool,
        "can_proceed": True   # user can always choose to continue regardless
      }
    """
    required = REQUIRED_FIELDS.get(crime_type, ["description", "crime_type", "evidence"])
    fields = [
        {"key": key, "label": FIELD_LABELS.get(key, key), "present": _check_field(key, context)}
        for key in required
    ]
    missing_count = sum(1 for f in fields if not f["present"])

    return {
        "crime_type": crime_type,
        "fields": fields,
        "missing_count": missing_count,
        "is_complete": missing_count == 0,
        "can_proceed": True,  # Feature 5: "allow users to continue if they choose"
    }


if __name__ == "__main__":
    import json
    sample_context = {
        "description": "Someone took money using a fake UPI link",
        "crime_type": "upi_fraud",
        "evidence_count": 1,
        "extracted_entities": {"upi_ids": ["scammer@okhdfcbank"]},
        "platform": "",
        "financial_loss": "",
        "suspect_details": {},
    }
    print(json.dumps(check_completeness("upi_fraud", sample_context), indent=2))
