"""
Feature 6: Government Complaint Draft.

Deliberately template-based rather than purely LLM-generated: a complaint
meant for submission to cybercrime.gov.in or a police station benefits from
a predictable, complete structure every time, and this way it works even if
the LLM reasoning layer (rag/llm_reasoning.py) is unavailable. It also means
this is fully testable offline, unlike the LLM-based draft.

The LLM-generated `draft_complaint` from /analyze (rag/llm_reasoning.py)
is a different, complementary thing: a quick first-person paragraph shown
immediately in the app. This module is the fuller, structured version meant
specifically for filing - used by /generate-report and /complaint-draft.
"""
from datetime import date, datetime


def build_complaint_draft(data: dict) -> str:
    """
    data keys (all optional except crime_type and user_text):
      crime_type: str
      user_text: str
      timeline: list of {time, event}   (from case_builder/timeline.py)
      victim_details: dict (name, phone, email, address)
      suspect_details: dict (name, phone, email, upi_id, bank_account)
      platform: str
      financial_loss: str
      applicable_law: list of {chunk_id, plain_language_summary}
      incident_datetime: str
    """
    victim = data.get("victim_details") or {}
    suspect = data.get("suspect_details") or {}
    timeline = data.get("timeline") or []
    applicable_law = data.get("applicable_law") or []
    crime_title = data.get("crime_type", "").replace("_", " ").title() or "Cybercrime Incident"

    lines = []
    lines.append("To,")
    lines.append("The Officer In-Charge,")
    lines.append("Cyber Crime Police Station / cybercrime.gov.in")
    lines.append("")
    lines.append(f"Subject: Complaint regarding {crime_title} resulting in loss/harm")
    lines.append("")
    lines.append("Respected Sir/Madam,")
    lines.append("")

    victim_name = victim.get("name") or "[Your Name]"
    victim_address = victim.get("address") or "[Your Address]"
    victim_phone = victim.get("phone") or "[Your Phone Number]"
    victim_email = victim.get("email") or "[Your Email]"

    lines.append(
        f"I, {victim_name}, residing at {victim_address}, wish to lodge a complaint "
        f"regarding a {crime_title.lower()} incident, details of which are set out below."
    )
    lines.append("")

    lines.append("Incident Description:")
    lines.append(data.get("user_text", "").strip() or "[Incident description not provided]")
    lines.append("")

    if timeline:
        lines.append("Chronology of Events:")
        for event in timeline:
            lines.append(f"  {event.get('time', '')} — {event.get('event', '')}")
        lines.append("")

    if data.get("platform"):
        lines.append(f"Platform Involved: {data['platform']}")
    if data.get("financial_loss"):
        lines.append(f"Financial Loss: {data['financial_loss']}")
    if data.get("incident_datetime"):
        lines.append(f"Date & Time of Incident: {data['incident_datetime']}")
    if any([data.get("platform"), data.get("financial_loss"), data.get("incident_datetime")]):
        lines.append("")

    if any(suspect.values()):
        lines.append("Suspect Details (if known):")
        if suspect.get("name"):
            lines.append(f"  Name: {suspect['name']}")
        if suspect.get("phone"):
            lines.append(f"  Phone: {suspect['phone']}")
        if suspect.get("email"):
            lines.append(f"  Email: {suspect['email']}")
        if suspect.get("upi_id"):
            lines.append(f"  UPI ID: {suspect['upi_id']}")
        if suspect.get("bank_account"):
            lines.append(f"  Bank Account: {suspect['bank_account']}")
        lines.append("")

    if applicable_law:
        lines.append("Relevant Legal Provisions (for reference):")
        for law in applicable_law:
            lines.append(f"  [{law.get('chunk_id', '')}] {law.get('plain_language_summary', '')}")
        lines.append("")

    lines.append(
        "I request you to kindly register my complaint, investigate the matter, and take "
        "appropriate action against the perpetrator(s) under the applicable provisions of law. "
        "I am attaching relevant evidence (screenshots, transaction records, chat exports, etc.) "
        "in support of this complaint."
    )
    lines.append("")
    lines.append("Thanking you,")
    lines.append(victim_name)
    lines.append(victim_phone)
    lines.append(victim_email)
    lines.append(datetime.now().strftime("%d %B %Y"))

    return "\n".join(lines)


if __name__ == "__main__":
    sample = {
        "crime_type": "upi_fraud",
        "user_text": "Someone took money from my bank account using a fake UPI link.",
        "timeline": [
            {"time": "09:15 AM", "event": "Received a phishing SMS with a fake UPI link."},
            {"time": "09:21 AM", "event": "Money was debited from my account."},
        ],
        "victim_details": {"name": "Ramesh Kumar", "phone": "9876500000"},
        "suspect_details": {"upi_id": "scammer@okhdfcbank"},
        "platform": "PhonePe",
        "financial_loss": "Rs 15,000",
        "applicable_law": [
            {"chunk_id": "it_act_66d", "plain_language_summary": "Covers cheating by personation using a computer resource."},
        ],
    }
    print(build_complaint_draft(sample))
