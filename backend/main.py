"""
FastAPI backend for the cybercrime legal advisor.

This is the single entry point tying together:
  user text -> fine-tuned classifier -> scoped RAG retrieval -> LLM reasoning
             -> structured JSON response

Run:
    uvicorn main:app --reload --port 8000

Requires the classifier to be trained (classifier/crime_classifier/) and the
RAG index to be built (rag/index/) first - see README.md.

Designed to be modular: later features (evidence upload, PDF report, etc.)
should call this endpoint's output as input, not reach into its internals,
so nothing here needs to change when those features are added.
"""
import sys
import os
from pathlib import Path

# Load .env regardless of how this is launched (plain `uvicorn main:app`,
# VS Code's F5 debug config, a deployed host, etc.) - previously this only
# worked via VS Code's "Backend: FastAPI (uvicorn)" launch config, which has
# envFile wired in; a plain terminal `uvicorn` command silently ignored
# CLASSIFIER_BACKEND/GEMINI_API_KEY/DATABASE_URL/SUPABASE_* entirely.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass  # python-dotenv not installed - fine if env vars are set another way

from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware

sys.path.append(str(Path(__file__).parent.parent / "data"))
sys.path.append(str(Path(__file__).parent.parent / "classifier"))
sys.path.append(str(Path(__file__).parent.parent / "rag"))
sys.path.append(str(Path(__file__).parent.parent / "evidence"))

import tempfile
import uuid

from fastapi.responses import FileResponse, Response

from schemas import (
    ComplaintRequest, AnalysisResponse, ClassificationResult, LegalReference, ReportRequest,
    EvidenceRecord, CompletenessResponse, CompletenessField, TimelineEvent, ComplaintDraftResponse,
    ReportHistoryItem, TimelineRequest,
)
# CLASSIFIER_BACKEND=local   (default) - classifier/predict.py, needs torch/transformers
#                                        + a trained model in classifier/crime_classifier/
# CLASSIFIER_BACKEND=sklearn            - classifier/predict_lite.py, needs only
#                                        scikit-learn+joblib (~100-150MB), no torch/GPU/API key
# CLASSIFIER_BACKEND=gemini             - classifier/gemini_classify.py, needs only
#                                        GEMINI_API_KEY, no local install/training at all
# Kept as separate import branches (not a runtime if/else on a single import)
# so each mode genuinely never imports the others' heavy deps - that's the
# whole point of offering this switch (smaller deploy, faster cold start).
CLASSIFIER_BACKEND = os.environ.get("CLASSIFIER_BACKEND", "local").lower()

if CLASSIFIER_BACKEND == "gemini":
    from gemini_classify import classify_with_gemini as classify
elif CLASSIFIER_BACKEND == "sklearn":
    from predict_lite import load_model, predict as classify
else:
    from predict import load_model, predict as classify

# RETRIEVER_BACKEND=faiss (default) - rag/retrieve.py, needs sentence-transformers
#                                     + faiss-cpu (sentence-transformers itself needs torch)
# RETRIEVER_BACKEND=lite            - rag/retrieve_lite.py, plain tag-filtering,
#                                     no ML dependency at all. Reasonable at this
#                                     corpus size (a handful of legal_kb chunks).
RETRIEVER_BACKEND = os.environ.get("RETRIEVER_BACKEND", "faiss").lower()
if RETRIEVER_BACKEND == "lite":
    from retrieve_lite import LiteLegalRetriever as LegalRetriever
else:
    from retrieve import LegalRetriever
from llm_reasoning import generate_response
from taxonomy import URGENT_CATEGORIES, EMERGENCY_MESSAGE, SAFETY_RECOMMENDATIONS, MIN_CONFIDENCE_THRESHOLD

sys.path.append(str(Path(__file__).parent.parent / "reports"))
from pdf_report import build_pdf
from export_formats import build_docx, build_plain_text

import extraction
import hashing
import storage
import blob_storage

sys.path.append(str(Path(__file__).parent.parent / "case_builder"))
from timeline import build_timeline
from completeness import check_completeness
from complaint_draft import build_complaint_draft

app = FastAPI(title="CyberSleuth AI", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this before any real deployment
    allow_methods=["*"],
    allow_headers=["*"],
)

# Loaded once at startup, reused across requests
_tokenizer = None
_model = None
_retriever = None


@app.on_event("startup")
def load_resources():
    global _tokenizer, _model, _retriever
    if CLASSIFIER_BACKEND == "gemini":
        if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
            print("WARNING: CLASSIFIER_BACKEND=gemini but no GEMINI_API_KEY/GOOGLE_API_KEY set.")
        _tokenizer, _model = "gemini", "gemini"  # sentinel truthy values - no local model to load
    elif CLASSIFIER_BACKEND == "sklearn":
        try:
            _tokenizer, _model = load_model("../classifier/crime_classifier_lite")
        except Exception as e:
            print(f"WARNING: sklearn classifier not loaded ({e}). Train it first: python train_lite.py")
    else:
        try:
            _tokenizer, _model = load_model("../classifier/crime_classifier")
        except Exception as e:
            print(f"WARNING: classifier not loaded ({e}). Train it first - see README.")
    try:
        _retriever = LegalRetriever(index_dir="../rag/index")
    except Exception as e:
        print(f"WARNING: RAG index not loaded ({e}). Build it first - see README.")


@app.post("/complaint/new")
def new_complaint():
    """
    Mints a fresh complaint_id for the frontend to use across
    /evidence/upload, /complaint-draft, /generate-report, and /timeline for
    the same case, so evidence and reports stay linked together under one id.
    Purely a UUID generator - doesn't touch the database. A row only
    actually appears in storage once evidence is uploaded or a report is
    generated against this id.
    """
    return {"complaint_id": uuid.uuid4().hex}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "classifier_loaded": _model is not None,
        "retriever_loaded": _retriever is not None,
    }


def _run_pipeline(text: str, incident_date=None):
    """Shared core pipeline: classify -> retrieve -> LLM reasoning.
    Used by both /analyze and /generate-report so neither endpoint drifts
    out of sync with the other."""
    if _model is None or _retriever is None:
        raise HTTPException(
            status_code=503,
            detail="Backend resources not loaded. Train the classifier and build the RAG index first (see README).",
        )

    if CLASSIFIER_BACKEND == "gemini":
        classification_results = classify(text, top_k=3)
    else:
        classification_results = classify(text, _tokenizer, _model, top_k=3)
    top = classification_results[0]

    retrieved = _retriever.retrieve(
        query_text=text,
        legal_tags=top["legal_tags"],
        top_k=4,
        incident_date=incident_date,
    )

    llm_output = generate_response(
        user_text=text,
        crime_type=top["label"],
        confidence=top["confidence"],
        retrieved_chunks=retrieved,
    )

    if "error" in llm_output:
        raise HTTPException(status_code=502, detail=f"LLM reasoning layer failed: {llm_output['error']}")

    # Feature 9: merge rule-based safety recommendations with LLM-generated ones,
    # de-duplicated, so recommendations remain reliable even if the LLM omits them.
    rule_based_safety = SAFETY_RECOMMENDATIONS.get(top["label"], [])
    llm_safety = llm_output.get("safety_recommendations", [])
    merged_safety = list(dict.fromkeys(rule_based_safety + llm_safety))  # preserves order, dedupes

    # Feature 10: emergency alert - rule-based, not LLM-dependent, for reliability.
    # Gated on confidence: a low-confidence prediction shouldn't fire a
    # high-stakes "call your bank now" alert - that's worse than no alert.
    low_confidence = top["confidence"] < MIN_CONFIDENCE_THRESHOLD
    is_urgent = (top["label"] in URGENT_CATEGORIES) and not low_confidence
    emergency_message = EMERGENCY_MESSAGE if is_urgent else ""

    return {
        "classification_results": classification_results,
        "top": top,
        "retrieved": retrieved,
        "llm_output": llm_output,
        "merged_safety": merged_safety,
        "is_urgent": is_urgent,
        "emergency_message": emergency_message,
        "low_confidence": low_confidence,
    }


@app.post("/analyze", response_model=AnalysisResponse)
def analyze(request: ComplaintRequest):
    pipeline = _run_pipeline(request.text, request.incident_date)
    top = pipeline["top"]
    llm_output = pipeline["llm_output"]
    retrieved = pipeline["retrieved"]

    return AnalysisResponse(
        classification=ClassificationResult(
            label=top["label"], confidence=top["confidence"], legal_tags=top["legal_tags"]
        ),
        top_alternatives=[
            ClassificationResult(label=r["label"], confidence=r["confidence"], legal_tags=r["legal_tags"])
            for r in pipeline["classification_results"][1:]
        ],
        crime_type_explanation=llm_output.get("crime_type_explanation", ""),
        applicable_law=[
            LegalReference(chunk_id=item["chunk_id"], plain_language_summary=item["plain_language_summary"])
            for item in llm_output.get("applicable_law", [])
        ],
        regime_note=llm_output.get("regime_note", ""),
        immediate_actions=llm_output.get("immediate_actions", []),
        safety_recommendations=pipeline["merged_safety"],
        draft_complaint=llm_output.get("draft_complaint", ""),
        uncovered_aspects=llm_output.get("uncovered_aspects", ""),
        retrieved_chunk_ids=[c["id"] for c in retrieved],
        is_urgent=pipeline["is_urgent"],
        emergency_message=pipeline["emergency_message"],
        low_confidence=pipeline["low_confidence"],
    )


def _evidence_context(complaint_id: str = None):
    """Shared helper: returns (evidence_rows, merged_extracted_entities) for a
    complaint_id, or ([], {}) if none provided/found."""
    if not complaint_id:
        return [], {}
    rows = storage.list_evidence_for_complaint(complaint_id)
    merged = storage.merged_extracted_entities(complaint_id)
    return rows, merged


@app.post("/evidence/upload", response_model=EvidenceRecord)
async def upload_evidence(complaint_id: str = Form(...), file: UploadFile = File(...), ocr_text: str = Form("")):
    """
    Feature 2 (Evidence Manager) + Feature 3 (AI Evidence Extraction) +
    Feature 8 (Evidence Integrity - SHA-256 hash).

    `ocr_text` is optional: if the caller already has extracted text (e.g.
    pasted chat export content, or OCR run client-side), pass it here so
    extraction.py can pull entities from it. Phase 2 does not include OCR
    itself - see README for why and what to add for that.
    """
    evidence_id = str(uuid.uuid4())
    safe_filename = f"{evidence_id}_{file.filename}"
    file_path = str(Path(storage.STORAGE_DIR) / safe_filename)

    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)

    file_size = len(contents)
    file_type = file.content_type or "application/octet-stream"
    sha256 = hashing.compute_sha256(file_path)

    extracted = extraction.extract_from_evidence_file(file_path, file_type, ocr_text=ocr_text)

    # file_path above is a local temp copy used only so extraction.py's
    # cv2/QR-code reading has an actual file to open. The locator saved to
    # the DB is the durable copy - Supabase Storage if configured, otherwise
    # the same local disk (storage/blobs/) as a fallback.
    locator = blob_storage.save_blob(f"evidence/{safe_filename}", contents)

    storage.save_evidence_record(
        evidence_id=evidence_id, complaint_id=complaint_id, filename=file.filename,
        file_path=locator, file_type=file_type, file_size=file_size,
        sha256=sha256, extracted_entities=extracted,
    )

    return EvidenceRecord(
        id=evidence_id, complaint_id=complaint_id, filename=file.filename,
        file_type=file_type, file_size=file_size,
        upload_time=storage.list_evidence_for_complaint(complaint_id)[-1]["upload_time"],
        sha256=sha256, extracted_entities=extracted,
    )


@app.get("/evidence/{complaint_id}", response_model=list[EvidenceRecord])
def list_evidence(complaint_id: str):
    rows = storage.list_evidence_for_complaint(complaint_id)
    return [
        EvidenceRecord(
            id=row["id"], complaint_id=row["complaint_id"], filename=row["filename"],
            file_type=row["file_type"], file_size=row["file_size"], upload_time=row["upload_time"],
            sha256=row["sha256"], extracted_entities=__import__("json").loads(row["extracted_entities_json"] or "{}"),
        )
        for row in rows
    ]


@app.delete("/evidence/{evidence_id}")
def delete_evidence(evidence_id: str):
    storage.delete_evidence(evidence_id)
    return {"status": "deleted", "id": evidence_id}


@app.post("/completeness-check", response_model=CompletenessResponse)
def completeness_check(request: ReportRequest):
    """
    Feature 5: Complaint Completeness Checker.
    Runs classification (to know which fields are required for this crime
    type) then checks what's present. Does not require evidence to exist -
    evidence_count simply comes back 0 if no complaint_id / no uploads yet.
    """
    pipeline = _run_pipeline(request.text, request.incident_date)
    top = pipeline["top"]

    evidence_rows, merged_entities = _evidence_context(request.complaint_id)

    context = {
        "description": request.text,
        "crime_type": top["label"],
        "evidence_count": len(evidence_rows),
        "extracted_entities": merged_entities,
        "platform": request.platform,
        "financial_loss": request.financial_loss,
        "suspect_details": request.suspect_details.dict() if request.suspect_details else {},
    }
    result = check_completeness(top["label"], context)
    return CompletenessResponse(
        crime_type=result["crime_type"],
        fields=[CompletenessField(**f) for f in result["fields"]],
        missing_count=result["missing_count"],
        is_complete=result["is_complete"],
        can_proceed=result["can_proceed"],
    )


@app.post("/timeline", response_model=list[TimelineEvent])
def timeline(request: TimelineRequest):
    """
    Standalone timeline endpoint for the frontend's Timeline page. Does not
    require classification - just reconstructs chronological events from the
    submitted text plus any evidence already uploaded under complaint_id.
    (The classify->retrieve->LLM pipeline still runs this same build_timeline
    step internally as part of /complaint-draft and /generate-report.)
    """
    evidence_rows, _ = _evidence_context(request.complaint_id)
    events = build_timeline(request.text, evidence_rows)
    return [TimelineEvent(**e) for e in events]


@app.post("/complaint-draft", response_model=ComplaintDraftResponse)
def complaint_draft(request: ReportRequest):
    """
    Feature 6: Government Complaint Draft (standalone - for copy/download
    without generating a full PDF). Feature 4 (timeline) feeds into this.
    """
    pipeline = _run_pipeline(request.text, request.incident_date)
    top = pipeline["top"]
    llm_output = pipeline["llm_output"]

    complaint_id = request.complaint_id or uuid.uuid4().hex
    evidence_rows, _ = _evidence_context(complaint_id)
    timeline = build_timeline(request.text, evidence_rows)

    draft = build_complaint_draft({
        "crime_type": top["label"],
        "user_text": request.text,
        "timeline": timeline,
        "victim_details": request.victim_details.dict() if request.victim_details else None,
        "suspect_details": request.suspect_details.dict() if request.suspect_details else None,
        "platform": request.platform,
        "financial_loss": request.financial_loss,
        "applicable_law": llm_output.get("applicable_law", []),
        "incident_datetime": request.incident_datetime_display or (
            str(request.incident_date) if request.incident_date else ""
        ),
    })
    return ComplaintDraftResponse(
        draft=draft,
        timeline=[TimelineEvent(**e) for e in timeline],
        complaint_id=complaint_id,
    )


@app.post("/generate-report")
def generate_report(request: ReportRequest):
    """
    Feature 1: Download Investigation Report (PDF).
    Runs the same pipeline as /analyze, then layers in optional case metadata
    (victim/suspect details, platform, financial loss) before rendering a PDF.
    If complaint_id is provided, evidence uploaded via /evidence/upload for
    that complaint is merged in too (Feature 2/3/8 -> Feature 1 integration).
    The PDF's complaint draft uses the structured template from
    case_builder/complaint_draft.py (Feature 6), not the LLM's quick draft
    from /analyze - that quick draft is still returned unchanged by /analyze.
    Does not change /analyze's behavior or response shape at all.
    """
    pipeline = _run_pipeline(request.text, request.incident_date)
    top = pipeline["top"]
    llm_output = pipeline["llm_output"]
    retrieved = pipeline["retrieved"]

    # If the caller didn't already have a case going (via /complaint/new or a
    # prior evidence upload), mint one now so this report - and anything
    # uploaded against it afterward - can still be found together later.
    complaint_id = request.complaint_id or uuid.uuid4().hex

    evidence_rows, extracted_entities = _evidence_context(complaint_id)
    evidence_list = [
        {"filename": r["filename"], "file_type": r["file_type"],
         "upload_time": r["upload_time"], "sha256": r["sha256"]}
        for r in evidence_rows
    ]
    timeline = build_timeline(request.text, evidence_rows)

    victim_dict = request.victim_details.dict() if request.victim_details else None
    suspect_dict = request.suspect_details.dict() if request.suspect_details else None
    incident_display = request.incident_datetime_display or (
        str(request.incident_date) if request.incident_date else ""
    )

    formal_draft = build_complaint_draft({
        "crime_type": top["label"],
        "user_text": request.text,
        "timeline": timeline,
        "victim_details": victim_dict,
        "suspect_details": suspect_dict,
        "platform": request.platform,
        "financial_loss": request.financial_loss,
        "applicable_law": llm_output.get("applicable_law", []),
        "incident_datetime": incident_display,
    })

    top_alternatives = [
        {"label": r["label"], "confidence": r["confidence"], "legal_tags": r["legal_tags"]}
        for r in pipeline["classification_results"][1:]
    ]

    report_data = {
        "crime_type": top["label"],
        "confidence": top["confidence"],
        "user_text": request.text,
        "incident_datetime": incident_display,
        "platform": request.platform or "",
        "financial_loss": request.financial_loss or "",
        "victim_details": victim_dict,
        "suspect_details": suspect_dict,
        "applicable_law": llm_output.get("applicable_law", []),
        "regime_note": llm_output.get("regime_note", ""),
        "top_alternatives": top_alternatives,
        "immediate_actions": llm_output.get("immediate_actions", []),
        "safety_recommendations": pipeline["merged_safety"],
        "draft_complaint": formal_draft,
        "uncovered_aspects": llm_output.get("uncovered_aspects", ""),
        "is_urgent": pipeline["is_urgent"],
        "emergency_message": pipeline["emergency_message"],
        "privacy_mode": request.privacy_mode,
        "extracted_entities": extracted_entities,
        "evidence_list": evidence_list,
        "timeline": timeline,
        "device_info": request.device_info or "",
        "ip_address": request.ip_address or "",
    }

    # Feature 11: Export Formats. Feature 12: Report History.
    # Built to a local temp path first (build_pdf/build_docx need an actual
    # path to write to), then the bytes are persisted through blob_storage -
    # Supabase Storage if configured, otherwise local disk under
    # storage/blobs/. That locator (not the temp path) is what's saved to
    # the DB and what /reports/{id}/download reads back later, so reports
    # survive a redeploy even though the temp file itself won't.
    report_id = uuid.uuid4().hex
    fmt = (request.export_format or "pdf").lower()
    tmp_dir = tempfile.mkdtemp()

    if fmt == "docx":
        filename = f"cybercrime_report_{top['label']}_{report_id}.docx"
        tmp_path = str(Path(tmp_dir) / filename)
        build_docx(report_data, tmp_path)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        with open(tmp_path, "rb") as f:
            file_bytes = f.read()
    elif fmt == "txt":
        filename = f"cybercrime_report_{top['label']}_{report_id}.txt"
        media_type = "text/plain"
        file_bytes = build_plain_text(report_data).encode("utf-8")
    else:
        fmt = "pdf"
        filename = f"cybercrime_report_{top['label']}_{report_id}.pdf"
        tmp_path = str(Path(tmp_dir) / filename)
        build_pdf(report_data, tmp_path)
        media_type = "application/pdf"
        with open(tmp_path, "rb") as f:
            file_bytes = f.read()

    locator = blob_storage.save_blob(f"reports/{report_id}_{filename}", file_bytes)

    storage.save_report_record(
        report_id=report_id,
        complaint_id=complaint_id,
        crime_type=top["label"],
        status="generated",
        format=fmt,
        filename=filename,
        file_path=locator,
    )

    return Response(
        content=file_bytes,
        media_type=media_type,
        headers={
            "X-Complaint-Id": complaint_id,
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@app.get("/reports", response_model=list[ReportHistoryItem])
def report_history(complaint_id: str = None):
    """Feature 12: Report History."""
    rows = storage.list_reports(complaint_id=complaint_id)
    return [
        ReportHistoryItem(
            id=r["id"], complaint_id=r["complaint_id"], crime_type=r["crime_type"],
            generated_date=r["generated_date"], status=r["status"], format=r["format"], filename=r["filename"],
        )
        for r in rows
    ]


@app.get("/reports/{report_id}/download")
def download_report(report_id: str):
    """Feature 12: 'Download Again' from report history."""
    record = storage.get_report(report_id)
    if not record or not record.get("file_path") or not blob_storage.blob_exists(record["file_path"]):
        raise HTTPException(status_code=404, detail="Report not found")
    media_types = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "txt": "text/plain",
    }
    file_bytes = blob_storage.read_blob(record["file_path"])
    return Response(
        content=file_bytes,
        media_type=media_types.get(record["format"], "application/octet-stream"),
        headers={"Content-Disposition": f'attachment; filename="{record["filename"]}"'},
    )


# @app.delete("/reports/{report_id}")
# def delete_report_endpoint(report_id: str):
#     """Feature 12: 'Delete' from report history."""
#     storage.delete_report(report_id)
#     return {"status": "deleted", "id": report_id}

# @app.get("/")
# def root():
#     return {
#         "message": "CyberSleuth AI Backend is running 🚀"
#     }

@app.delete("/reports/{report_id}")
def delete_report_endpoint(report_id: str):
    """Feature 12: 'Delete' from report history."""
    storage.delete_report(report_id)
    return {"status": "deleted", "id": report_id}


@app.get("/")
def root():
    return {
        "message": "CyberSleuth AI Backend is running 🚀"
    }
