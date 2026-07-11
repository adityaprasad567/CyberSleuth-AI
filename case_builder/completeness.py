"""
Feature 5: Complaint Completeness Checker
"""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.taxonomy import REQUIRED_FIELDS


FIELD_LABELS = {
    "description": "Complaint Description",
    "crime_type": "Crime Type",
    "evidence": "Evidence Uploaded",
    "suspect_contact": "Suspect Contact Details",
}


def _check_field(key: str, context: dict) -> bool:
    entities = context.get("extracted_entities", {})
    suspect = context.get("suspect_details", {})

    if key == "description":
        return bool(context.get("description", "").strip())

    if key == "crime_type":
        return bool(context.get("crime_type"))

    if key == "evidence":
        return context.get("evidence_count", 0) > 0

    if key == "suspect_contact":
        return bool(
            suspect.get("phone")
            or suspect.get("upi_id")
            or suspect.get("email")
            or entities.get("phone_numbers")
            or entities.get("upi_ids")
            or entities.get("emails")
            or entities.get("email_addresses")
        )

    return False


def check_completeness(crime_type: str, context: dict) -> dict:
    """
    Check whether the complaint contains all mandatory information.
    """

    required = REQUIRED_FIELDS.get(
        crime_type,
        ["description", "crime_type", "evidence"],
    )

    fields = []

    for key in required:
        fields.append(
            {
                "key": key,
                "label": FIELD_LABELS.get(key, key.replace("_", " ").title()),
                "present": _check_field(key, context),
            }
        )

    missing_count = sum(
        1 for field in fields if not field["present"]
    )

    return {
        "crime_type": crime_type,
        "fields": fields,
        "missing_count": missing_count,
        "is_complete": missing_count == 0,
        "can_proceed": True,
    }


if __name__ == "__main__":
    import json

    sample_context = {
        "description": "Someone cheated me using a fake UPI payment request.",
        "crime_type": "upi_fraud",
        "evidence_count": 2,
        "extracted_entities": {
            "upi_ids": ["fraud@okaxis"],
            "phone_numbers": ["9876543210"],
        },
        "suspect_details": {
            "phone": "9876543210",
        },
    }

    result = check_completeness("upi_fraud", sample_context)

    print(json.dumps(result, indent=4))
