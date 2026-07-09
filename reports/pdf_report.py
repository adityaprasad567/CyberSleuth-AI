"""
Generates a professional PDF investigation report.

Designed to be forward-compatible with Phase 2 (evidence) and Phase 3
(timeline, completeness): every section is optional and only renders if the
corresponding data is present in `report_data`. Phase 2/3 can pass a richer
`report_data` dict later without any changes needed here.

Install:
    pip install reportlab --break-system-packages

Usage (see bottom of file for a runnable example):
    from pdf_report import build_pdf
    build_pdf(report_data, "report.pdf")
"""
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, ListFlowable, ListItem
)

styles = getSampleStyleSheet()
TITLE_STYLE = ParagraphStyle("TitleStyle", parent=styles["Title"], fontSize=18, spaceAfter=4)
SECTION_STYLE = ParagraphStyle("SectionStyle", parent=styles["Heading2"], fontSize=13,
                                spaceBefore=14, spaceAfter=6, textColor=colors.HexColor("#1a2b4a"))
BODY_STYLE = ParagraphStyle("BodyStyle", parent=styles["BodyText"], fontSize=10, leading=14)
META_STYLE = ParagraphStyle("MetaStyle", parent=styles["BodyText"], fontSize=9, textColor=colors.grey)
ALERT_STYLE = ParagraphStyle("AlertStyle", parent=styles["BodyText"], fontSize=10, leading=14,
                              textColor=colors.HexColor("#7a1212"), backColor=colors.HexColor("#fdecea"))


def _section(title, flow):
    flow.append(Paragraph(title, SECTION_STYLE))
    flow.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))


def _safe_text(s: str) -> str:
    """
    reportlab's Paragraph treats its content as mini-XML markup, not plain
    text: raw '&'/'<'/'>' break rendering, and raw '\\n' is NOT a line break
    (it's just collapsed whitespace) - that's why multi-paragraph text like
    the draft complaint or incident description was rendering as one
    run-on block with no spacing. This escapes special characters first,
    then converts real newlines to '<br/>' so paragraph breaks actually
    show up in the PDF.
    """
    if not s:
        return ""
    escaped = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return escaped.replace("\n\n", "<br/><br/>").replace("\n", "<br/>")


def _bullets(items, flow):
    flow.append(ListFlowable(
        [ListItem(Paragraph(_safe_text(str(i)), BODY_STYLE)) for i in items],
        bulletType="bullet", start="•", leftIndent=14,
    ))


def _kv_table(pairs, flow):
    """pairs: list of (label, value) tuples; skips entries where value is falsy."""
    rows = [(f"<b>{label}</b>", _safe_text(str(value))) for label, value in pairs if value]
    if not rows:
        return
    data = [[Paragraph(l, BODY_STYLE), Paragraph(v, BODY_STYLE)] for l, v in rows]
    table = Table(data, colWidths=[45 * mm, 120 * mm])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#eeeeee")),
    ]))
    flow.append(table)


def build_pdf(report_data: dict, output_path: str):
    """
    report_data expected keys (all optional except noted):
      crime_type (required), confidence (required), user_text (required)
      incident_datetime, platform, financial_loss
      victim_details: dict (name, phone, email, address) - only rendered if user opted to include it
      suspect_details: dict (name, phone, email, upi_id, bank_account)
      extracted_entities: dict of lists (phone_numbers, emails, urls, bank_details, upi_ids, transaction_ids, wallet_ids)
      device_info, ip_address
      evidence_list: list of dicts (filename, upload_time, file_type, sha256)
      timeline: list of dicts (time, event)   [Phase 3]
      applicable_law: list of dicts (chunk_id, plain_language_summary)
      immediate_actions: list of str
      safety_recommendations: list of str
      draft_complaint: str
      is_urgent: bool
      emergency_message: str
      privacy_mode: bool - if True, redacts fields in extracted_entities/victim_details/suspect_details before rendering
    """
    if report_data.get("privacy_mode"):
        report_data = _apply_privacy_redaction(dict(report_data))

    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        topMargin=20 * mm, bottomMargin=18 * mm, leftMargin=18 * mm, rightMargin=18 * mm,
    )
    flow = []

    flow.append(Paragraph("Cybercrime Incident Report", TITLE_STYLE))
    flow.append(Paragraph(
        f"Generated on {datetime.now().strftime('%d %B %Y, %I:%M %p')} — for informational and complaint-filing purposes only, not a legal document by itself.",
        META_STYLE,
    ))
    flow.append(Spacer(1, 10))

    if report_data.get("is_urgent"):
        flow.append(Paragraph(
            f"⚠ URGENT: {report_data.get('emergency_message', '')}", ALERT_STYLE,
        ))
        flow.append(Spacer(1, 10))

    _section("Complaint Summary", flow)
    _kv_table([
        ("Detected Crime Type", report_data.get("crime_type", "").replace("_", " ").title()),
        ("AI Confidence Score", f"{report_data.get('confidence', 0):.0%}"),
        ("Date & Time of Incident", report_data.get("incident_datetime", "")),
        ("Platform Involved", report_data.get("platform", "")),
        ("Financial Loss", report_data.get("financial_loss", "")),
    ], flow)
    if report_data.get("regime_note"):
        flow.append(Paragraph(f"<i>{report_data['regime_note']}</i>", META_STYLE))
    flow.append(Spacer(1, 6))
    flow.append(Paragraph("<b>Incident Description</b>", BODY_STYLE))
    flow.append(Paragraph(_safe_text(report_data.get("user_text", "")), BODY_STYLE))

    victim = report_data.get("victim_details") or {}
    if any(victim.values()):
        _section("Victim Details", flow)
        _kv_table([
            ("Name", victim.get("name")), ("Phone", victim.get("phone")),
            ("Email", victim.get("email")), ("Address", victim.get("address")),
        ], flow)

    suspect = report_data.get("suspect_details") or {}
    if any(suspect.values()):
        _section("Suspect Details", flow)
        _kv_table([
            ("Name", suspect.get("name")), ("Phone", suspect.get("phone")),
            ("Email", suspect.get("email")), ("UPI ID", suspect.get("upi_id")),
            ("Bank Account", suspect.get("bank_account")),
        ], flow)

    entities = report_data.get("extracted_entities") or {}
    if any(entities.values()):
        _section("Extracted Information", flow)
        for label, key in [
            ("Phone Numbers", "phone_numbers"), ("Email Addresses", "emails"),
            ("URLs", "urls"), ("Bank Details", "bank_details"),
            ("UPI IDs", "upi_ids"), ("Transaction IDs", "transaction_ids"),
            ("Wallet IDs", "wallet_ids"),
        ]:
            values = entities.get(key)
            if values:
                flow.append(Paragraph(f"<b>{label}:</b> {_safe_text(', '.join(values))}", BODY_STYLE))

    if report_data.get("device_info") or report_data.get("ip_address"):
        _section("Device Information", flow)
        _kv_table([
            ("Device Info", report_data.get("device_info")),
            ("IP Address", report_data.get("ip_address")),
        ], flow)

    evidence = report_data.get("evidence_list") or []
    if evidence:
        _section("Uploaded Evidence", flow)
        rows = [["File Name", "Type", "Uploaded", "SHA-256"]]
        for e in evidence:
            rows.append([
                e.get("filename", ""), e.get("file_type", ""),
                e.get("upload_time", ""), (e.get("sha256", "")[:16] + "…") if e.get("sha256") else "",
            ])
        table = Table(rows, colWidths=[45 * mm, 25 * mm, 35 * mm, 55 * mm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a2b4a")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dddddd")),
        ]))
        flow.append(table)

    timeline = report_data.get("timeline") or []
    if timeline:
        _section("AI-Generated Timeline", flow)
        for t in timeline:
            flow.append(Paragraph(f"<b>{t.get('time', '')}</b> — {_safe_text(t.get('event', ''))}", BODY_STYLE))

    applicable_law = report_data.get("applicable_law") or []
    if applicable_law:
        _section("Relevant Legal Sections", flow)
        for law in applicable_law:
            flow.append(Paragraph(
                f"<b>[{law.get('chunk_id', '')}]</b> {_safe_text(law.get('plain_language_summary', ''))}", BODY_STYLE,
            ))

    actions = report_data.get("immediate_actions") or []
    if actions:
        _section("Recommended Next Steps", flow)
        _bullets(actions, flow)

    safety = report_data.get("safety_recommendations") or []
    if safety:
        _section("Safety Recommendations", flow)
        _bullets(safety, flow)

    draft = report_data.get("draft_complaint") or ""
    if draft:
        _section("Draft Complaint (for reference)", flow)
        flow.append(Paragraph(_safe_text(draft), BODY_STYLE))

    if report_data.get("uncovered_aspects"):
        _section("Additional Notes", flow)
        flow.append(Paragraph(_safe_text(report_data["uncovered_aspects"]), BODY_STYLE))

    flow.append(Spacer(1, 16))
    flow.append(Paragraph(
        "This report was generated with AI assistance and is intended to help you organize "
        "information for filing a complaint. It does not constitute legal advice.",
        META_STYLE,
    ))

    doc.build(flow)
    return output_path


def _apply_privacy_redaction(report_data: dict) -> dict:
    """Feature 7: redacts sensitive fields for a 'privacy mode' export.
    Original stored data is untouched - this only affects the dict passed to PDF rendering."""
    def redact(value):
        if not value:
            return value
        s = str(value)
        return s[:2] + "*" * max(len(s) - 2, 3)

    if report_data.get("victim_details"):
        v = dict(report_data["victim_details"])
        for k in ("phone", "email", "address"):
            if v.get(k):
                v[k] = redact(v[k])
        report_data["victim_details"] = v

    if report_data.get("extracted_entities"):
        e = dict(report_data["extracted_entities"])
        for k in ("phone_numbers", "emails", "bank_details", "upi_ids"):
            if e.get(k):
                e[k] = [redact(x) for x in e[k]]
        report_data["extracted_entities"] = e

    return report_data


if __name__ == "__main__":
    sample = {
        "crime_type": "upi_fraud",
        "confidence": 0.94,
        "user_text": "Someone took money from my bank account using a fake UPI link.",
        "incident_datetime": "2026-07-05 09:20 AM",
        "platform": "PhonePe",
        "financial_loss": "Rs 15,000",
        "is_urgent": True,
        "emergency_message": "Call your bank and 1930 immediately.",
        "applicable_law": [
            {"chunk_id": "it_act_66d", "plain_language_summary": "Covers cheating by impersonation using a computer resource."},
        ],
        "immediate_actions": ["Call your bank's fraud helpline.", "Call 1930."],
        "safety_recommendations": ["Change your UPI PIN.", "Enable MFA."],
        "draft_complaint": "I am writing to report an unauthorized UPI transaction...",
    }
    build_pdf(sample, "/tmp/sample_report.pdf")
    print("Sample PDF built at /tmp/sample_report.pdf")
