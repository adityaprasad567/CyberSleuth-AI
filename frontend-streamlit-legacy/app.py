"""
Minimal Streamlit frontend for the cybercrime legal advisor.

Run (with the backend already running on port 8000):
    streamlit run app.py

Install:
    pip install streamlit requests --break-system-packages
"""
import requests
import streamlit as st

import uuid

API_URL = "http://localhost:8000"

st.set_page_config(page_title="CyberSleuth AI", page_icon="🛡️")
st.title("🛡️ CyberSleuth AI")
st.caption("Describe what happened in plain language. This is not a substitute for legal advice.")

# One complaint_id per browser session - ties evidence uploads to this case
if "complaint_id" not in st.session_state:
    st.session_state.complaint_id = str(uuid.uuid4())

with st.expander("📎 Evidence (optional) - upload screenshots, chat exports, bank statements, etc."):
    uploaded_file = st.file_uploader(
        "Upload a file", type=None,
        help="Screenshots, PDFs, chat exports, audio, video, bank statements",
    )
    pasted_text = st.text_area(
        "Or paste relevant text from the file (chat export, statement text, etc.) - helps extraction",
        height=80, key="evidence_ocr_text",
    )
    if uploaded_file is not None and st.button("Upload evidence"):
        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type or "application/octet-stream")}
        data = {"complaint_id": st.session_state.complaint_id, "ocr_text": pasted_text}
        try:
            up_resp = requests.post(f"{API_URL}/evidence/upload", files=files, data=data, timeout=30)
            up_resp.raise_for_status()
            record = up_resp.json()
            st.success(f"Uploaded {record['filename']} — SHA-256: {record['sha256'][:16]}…")
            if record["extracted_entities"]:
                st.json(record["extracted_entities"])
        except requests.exceptions.ConnectionError:
            st.error(f"Could not reach the backend at {API_URL}. Is `uvicorn main:app` running?")
        except requests.exceptions.HTTPError as e:
            st.error(f"Upload failed: {e.response.text}")

    try:
        existing = requests.get(f"{API_URL}/evidence/{st.session_state.complaint_id}", timeout=10)
        if existing.ok and existing.json():
            st.markdown("**Uploaded so far:**")
            for e in existing.json():
                st.markdown(f"- {e['filename']} ({e['file_type']}, {e['file_size']} bytes) — {e['upload_time']}")
    except requests.exceptions.ConnectionError:
        pass

with st.form("complaint_form"):
    text = st.text_area(
        "What happened?",
        placeholder="e.g. Someone took money from my bank account using a fake UPI link",
        height=120,
    )
    incident_date = st.date_input("When did this happen? (optional, helps pick BNS vs IPC)", value=None)
    submitted = st.form_submit_button("Analyze")

if submitted and text.strip():
    payload = {"text": text}
    if incident_date:
        payload["incident_date"] = str(incident_date)

    with st.spinner("Classifying and retrieving relevant law..."):
        try:
            resp = requests.post(f"{API_URL}/analyze", json=payload, timeout=60)
            resp.raise_for_status()
            result = resp.json()
        except requests.exceptions.ConnectionError:
            st.error(f"Could not reach the backend at {API_URL}. Is `uvicorn main:app` running?")
            st.stop()
        except requests.exceptions.HTTPError as e:
            st.error(f"Backend error: {e.response.text}")
            st.stop()

    if result.get("is_urgent"):
        st.error(f"⚠ URGENT: {result['emergency_message']}")

    cls = result["classification"]
    st.subheader(f"Detected: {cls['label'].replace('_', ' ').title()}")
    st.progress(cls["confidence"], text=f"Confidence: {cls['confidence']:.0%}")

    if result["top_alternatives"]:
        with st.expander("Other possible classifications"):
            for alt in result["top_alternatives"]:
                st.write(f"- {alt['label'].replace('_', ' ').title()} ({alt['confidence']:.0%})")

    st.markdown("### What this means")
    st.write(result["crime_type_explanation"])

    if result["regime_note"]:
        st.info(result["regime_note"])

    st.markdown("### Applicable law")
    for law in result["applicable_law"]:
        st.markdown(f"**[{law['chunk_id']}]** {law['plain_language_summary']}")

    st.markdown("### Immediate actions")
    for action in result["immediate_actions"]:
        st.markdown(f"- {action}")

    st.markdown("### Safety recommendations")
    for rec in result["safety_recommendations"]:
        st.markdown(f"- {rec}")

    st.markdown("### Draft complaint")
    st.text_area("Copy this for filing:", value=result["draft_complaint"], height=200)

    if result["uncovered_aspects"]:
        st.warning(f"Not covered by retrieved legal sources: {result['uncovered_aspects']}")

    st.caption(f"Retrieved chunks: {', '.join(result['retrieved_chunk_ids'])}")
    st.caption("This tool provides general legal information, not legal advice. Consult a lawyer for your specific situation.")

    st.divider()
    st.markdown("### Case Completeness Check")
    completeness_payload = {"text": text, "complaint_id": st.session_state.complaint_id}
    if incident_date:
        completeness_payload["incident_date"] = str(incident_date)
    try:
        comp_resp = requests.post(f"{API_URL}/completeness-check", json=completeness_payload, timeout=30)
        if comp_resp.ok:
            comp = comp_resp.json()
            for field in comp["fields"]:
                icon = "✅" if field["present"] else "❌"
                st.markdown(f"{icon} {field['label']}")
            if not comp["is_complete"]:
                st.caption(f"{comp['missing_count']} field(s) missing - you can still continue and generate a report.")
        else:
            st.caption("Completeness check unavailable.")
    except requests.exceptions.ConnectionError:
        st.caption("Completeness check unavailable (backend not reachable).")

    st.markdown("### Government Complaint Draft")
    if st.button("Generate Complaint Draft"):
        draft_payload = {"text": text, "complaint_id": st.session_state.complaint_id}
        if incident_date:
            draft_payload["incident_date"] = str(incident_date)
        with st.spinner("Building your draft..."):
            draft_resp = requests.post(f"{API_URL}/complaint-draft", json=draft_payload, timeout=60)
        if draft_resp.ok:
            draft_data = draft_resp.json()
            st.text_area("Copy this for filing on cybercrime.gov.in or at a police station:",
                         value=draft_data["draft"], height=300)
            if draft_data["timeline"]:
                with st.expander("Timeline used in this draft"):
                    for e in draft_data["timeline"]:
                        st.markdown(f"**{e['time']}** — {e['event']}")
        else:
            st.error(f"Could not generate draft: {draft_resp.text}")

    st.divider()
    st.markdown("### Download Report")
    with st.expander("Optional details to include in the report"):
        platform = st.text_input("Platform involved (e.g. PhonePe, WhatsApp)", key="report_platform")
        financial_loss = st.text_input("Financial loss (e.g. Rs 15,000)", key="report_loss")
        privacy_mode = st.checkbox("Privacy mode (redact sensitive details in the report)", key="report_privacy")

    export_format = st.radio("Export format", ["PDF", "DOCX", "Plain text"], horizontal=True, key="export_format")
    format_map = {"PDF": "pdf", "DOCX": "docx", "Plain text": "txt"}
    mime_map = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "txt": "text/plain",
    }

    if st.button("Generate Report"):
        fmt = format_map[export_format]
        report_payload = {"text": text, "platform": platform, "financial_loss": financial_loss,
                           "privacy_mode": privacy_mode, "complaint_id": st.session_state.complaint_id,
                           "export_format": fmt}
        if incident_date:
            report_payload["incident_date"] = str(incident_date)
        with st.spinner("Building your report..."):
            report_resp = requests.post(f"{API_URL}/generate-report", json=report_payload, timeout=60)
        if report_resp.ok:
            st.download_button(
                f"Download {export_format}", data=report_resp.content,
                file_name=f"cybercrime_report_{cls['label']}.{fmt}", mime=mime_map[fmt],
            )
        else:
            st.error(f"Could not generate report: {report_resp.text}")

    st.divider()
    st.markdown("### Report History")
    try:
        history_resp = requests.get(f"{API_URL}/reports", params={"complaint_id": st.session_state.complaint_id}, timeout=10)
        if history_resp.ok and history_resp.json():
            for r in history_resp.json():
                cols = st.columns([3, 2, 2, 1, 1])
                cols[0].write(r["filename"])
                cols[1].write(r["crime_type"].replace("_", " ").title())
                cols[2].write(r["generated_date"])
                if cols[3].button("⬇", key=f"dl_{r['id']}"):
                    dl_resp = requests.get(f"{API_URL}/reports/{r['id']}/download", timeout=30)
                    if dl_resp.ok:
                        st.download_button("Save file", data=dl_resp.content, file_name=r["filename"],
                                            key=f"save_{r['id']}")
                if cols[4].button("🗑", key=f"del_{r['id']}"):
                    requests.delete(f"{API_URL}/reports/{r['id']}", timeout=10)
                    st.rerun()
        else:
            st.caption("No reports generated yet for this session.")
    except requests.exceptions.ConnectionError:
        st.caption("Report history unavailable (backend not reachable).")
