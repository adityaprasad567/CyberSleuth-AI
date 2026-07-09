from datetime import date
from typing import List, Optional

from pydantic import BaseModel


class ComplaintRequest(BaseModel):
    text: str
    incident_date: Optional[date] = None  # used to pick BNS vs IPC regime


class TimelineRequest(BaseModel):
    text: str = ""
    complaint_id: Optional[str] = None  # merges in timestamps from uploaded evidence too


class ClassificationResult(BaseModel):
    label: str
    confidence: float
    legal_tags: List[str]


class LegalReference(BaseModel):
    chunk_id: str
    plain_language_summary: str


class AnalysisResponse(BaseModel):
    classification: ClassificationResult
    top_alternatives: List[ClassificationResult]
    crime_type_explanation: str
    applicable_law: List[LegalReference]
    regime_note: str
    immediate_actions: List[str]
    safety_recommendations: List[str]
    draft_complaint: str
    uncovered_aspects: str
    retrieved_chunk_ids: List[str]
    is_urgent: bool = False
    emergency_message: str = ""
    low_confidence: bool = False


# --- Phase 1: report generation models (new, additive) ---

class VictimDetails(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None


class SuspectDetails(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    upi_id: Optional[str] = None
    bank_account: Optional[str] = None


class ReportRequest(BaseModel):
    text: str
    incident_date: Optional[date] = None
    incident_datetime_display: Optional[str] = None  # free-text, e.g. "5 July 2026, 9:20 AM"
    platform: Optional[str] = None
    financial_loss: Optional[str] = None
    victim_details: Optional[VictimDetails] = None
    suspect_details: Optional[SuspectDetails] = None
    privacy_mode: bool = False
    complaint_id: Optional[str] = None  # if provided, evidence + extracted entities are merged in
    export_format: str = "pdf"  # Feature 11: "pdf" | "docx" | "txt"
    device_info: Optional[str] = None  # e.g. "Android 14, Chrome 126" - user-supplied, not auto-detected
    ip_address: Optional[str] = None   # user-supplied, not auto-detected server-side (privacy)


# --- Phase 4: report history models (new, additive) ---

class ReportHistoryItem(BaseModel):
    id: str
    complaint_id: str
    crime_type: str
    generated_date: str
    status: str
    format: str
    filename: str


# --- Phase 2: evidence models (new, additive) ---

class EvidenceRecord(BaseModel):
    id: str
    complaint_id: str
    filename: str
    file_type: str
    file_size: int
    upload_time: str
    sha256: str
    extracted_entities: dict


# --- Phase 3: completeness + timeline + complaint draft models (new, additive) ---

class CompletenessField(BaseModel):
    key: str
    label: str
    present: bool


class CompletenessResponse(BaseModel):
    crime_type: str
    fields: List[CompletenessField]
    missing_count: int
    is_complete: bool
    can_proceed: bool


class TimelineEvent(BaseModel):
    time: str
    event: str


class ComplaintDraftResponse(BaseModel):
    draft: str
    timeline: List[TimelineEvent]
    complaint_id: str
