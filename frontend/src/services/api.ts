import axios from "axios";

export const API_BASE_URL =
  (typeof window !== "undefined" && (window as any).__API_BASE__) ||
  import.meta.env.VITE_API_BASE_URL ||
  "http://127.0.0.1:8000";

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
});

// ---- Response shapes, mirrored 1:1 from backend/schemas.py ----

export interface ClassificationResult {
  label: string;
  confidence: number;
  legal_tags: string[];
}

export interface LegalReference {
  chunk_id: string;
  plain_language_summary: string;
}

export interface AnalyzeResponse {
  classification: ClassificationResult;
  top_alternatives: ClassificationResult[];
  crime_type_explanation: string;
  applicable_law: LegalReference[];
  regime_note: string;
  immediate_actions: string[];
  safety_recommendations: string[];
  draft_complaint: string;
  uncovered_aspects: string;
  retrieved_chunk_ids: string[];
  is_urgent: boolean;
  emergency_message: string;
  low_confidence: boolean;
}

export interface TimelineEvent {
  time: string;
  event: string;
}

export interface ComplaintDraftResponse {
  draft: string;
  timeline: TimelineEvent[];
}

export interface CompletenessField {
  key: string;
  label: string;
  present: boolean;
}

export interface CompletenessResponse {
  crime_type: string;
  fields: CompletenessField[];
  missing_count: number;
  is_complete: boolean;
  can_proceed: boolean;
}

export interface EvidenceRecord {
  id: string;
  complaint_id: string;
  filename: string;
  file_type: string;
  file_size: number;
  upload_time: string;
  sha256: string;
  extracted_entities: Record<string, unknown>;
  // Feature 13 (OCR pipeline) - present on image evidence; empty/undefined
  // defaults on non-image evidence (PDF/audio/video), unchanged from before.
  ocr_text?: string;
  ocr_message?: string; // e.g. "No readable text detected in the uploaded image."
  crime_prediction?: string | null;
  confidence?: number | null;
  evidence_summary?: EvidenceSummary;
}

// Structured "Key Information" shape returned by extraction.build_evidence_summary()
export interface EvidenceSummary {
  phone_numbers: string[];
  emails: string[];
  upi_ids: string[];
  transaction_ids: string[];
  urls: string[];
  bank_names: string[];
  amounts: string[];
  dates: string[];
  times: string[];
  social_handles: string[];
  reference_numbers: string[];
  wallet_ids: string[];
  order_ids: string[];
  otps: string[];
  ip_addresses: string[];
  device_ids: string[];
  masked_account_numbers: string[];
  summary: string;
}

export interface ReportHistoryItem {
  id: string;
  complaint_id: string;
  crime_type: string;
  generated_date: string;
  status: string;
  format: string;
  filename: string;
}

export interface VictimDetails {
  name?: string;
  phone?: string;
  email?: string;
  address?: string;
}

export interface SuspectDetails {
  name?: string;
  phone?: string;
  email?: string;
  upi_id?: string;
  bank_account?: string;
}

// Shared by /completeness-check, /complaint-draft, /generate-report
// (backend's ReportRequest model). `text` is required by the backend.
export interface ReportRequestPayload {
  text: string;
  incident_date?: string;
  incident_datetime_display?: string;
  platform?: string;
  financial_loss?: string;
  victim_details?: VictimDetails;
  suspect_details?: SuspectDetails;
  privacy_mode?: boolean;
  complaint_id?: string;
  export_format?: "pdf" | "docx" | "txt";
}

export const CybercrimeAPI = {
  // POST /analyze - backend expects { text, incident_date }, not complaint_text.
  // There is no complaint_id in the response: the backend never mints one,
  // so the frontend must generate its own (see newComplaintId()) and pass it
  // through to every other call it wants linked to this complaint.
  analyze: (payload: { text: string; incident_date?: string }) =>
    api.post<AnalyzeResponse>("/analyze", payload).then((r) => r.data),

  // POST /complaint-draft - backend's ReportRequest model (no crime_type field)
  complaintDraft: (payload: ReportRequestPayload) =>
    api.post<ComplaintDraftResponse>("/complaint-draft", payload).then((r) => r.data),

  // POST /timeline - { text, complaint_id }, returns TimelineEvent[] directly
  timeline: (payload: { text?: string; complaint_id?: string }) =>
    api.post<TimelineEvent[]>("/timeline", payload).then((r) => r.data),

  // POST /completeness-check - backend's ReportRequest model
  completenessCheck: (payload: ReportRequestPayload) =>
    api.post<CompletenessResponse>("/completeness-check", payload).then((r) => r.data),

  // POST /evidence/upload - backend accepts ONE file per call (Form: complaint_id,
  // File: file, Form: ocr_text), not a batch /evidence endpoint. We loop client-side
  // and report aggregate progress across all files.
  uploadEvidence: async (
    files: File[],
    complaintId: string,
    onProgress?: (p: number) => void,
    ocrText = ""
  ): Promise<EvidenceRecord[]> => {
    const results: EvidenceRecord[] = [];
    for (let i = 0; i < files.length; i++) {
      const fd = new FormData();
      fd.append("complaint_id", complaintId);
      fd.append("file", files[i]);
      if (ocrText) fd.append("ocr_text", ocrText);

      const res = await api.post<EvidenceRecord>("/evidence/upload", fd, {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (e) => {
          if (onProgress && e.total) {
            const filePct = (e.loaded * 100) / e.total;
            onProgress(Math.round(((i + filePct / 100) / files.length) * 100));
          }
        },
      });
      results.push(res.data);
    }
    if (onProgress) onProgress(100);
    return results;
  },

  getEvidence: (complaintId: string) =>
    api.get<EvidenceRecord[]>(`/evidence/${complaintId}`).then((r) => r.data),

  deleteEvidence: (evidenceId: string) =>
    api.delete(`/evidence/${evidenceId}`).then((r) => r.data),

  // Feature 13 (OCR pipeline): uploads exactly ONE file and returns its
  // record directly (unlike the batch uploadEvidence() above), so the
  // caller can show per-file "OCR Processing… / OCR Completed" status as
  // each request resolves rather than waiting for the whole batch.
  uploadSingleEvidence: (file: File, complaintId: string, onProgress?: (p: number) => void) => {
    const fd = new FormData();
    fd.append("complaint_id", complaintId);
    fd.append("file", file);
    return api
      .post<EvidenceRecord>("/evidence/upload", fd, {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (e) => {
          if (onProgress && e.total) onProgress(Math.round((e.loaded * 100) / e.total));
        },
      })
      .then((r) => r.data);
  },

  // Feature 13: PATCH corrected OCR text - re-runs entity extraction, the
  // evidence summary, and crime classification server-side against the
  // user-edited text ("edit extracted text before final submission").
  updateEvidenceText: (evidenceId: string, ocrText: string) =>
    api.patch<EvidenceRecord>(`/evidence/${evidenceId}/text`, { ocr_text: ocrText }).then((r) => r.data),

  // POST /generate-report - returns a raw file (PDF/DOCX/TXT), not JSON.
  generateReport: (payload: ReportRequestPayload) =>
    api
      .post("/generate-report", payload, { responseType: "blob" })
      .then((r) => {
        const disposition = r.headers["content-disposition"] as string | undefined;
        const match = disposition?.match(/filename="?([^"]+)"?/);
        const filename = match?.[1] || `report.${payload.export_format || "pdf"}`;
        return { blob: r.data as Blob, filename };
      }),

  getReports: (complaintId?: string) =>
    api
      .get<ReportHistoryItem[]>("/reports", { params: complaintId ? { complaint_id: complaintId } : {} })
      .then((r) => r.data),

  downloadReport: (reportId: string) =>
    api.get(`/reports/${reportId}/download`, { responseType: "blob" }).then((r) => r.data as Blob),

  deleteReport: (reportId: string) =>
    api.delete(`/reports/${reportId}`).then((r) => r.data),

  health: () => api.get("/health").then((r) => r.data),
};

// The backend never issues a complaint_id - it's purely a client-side key used
// to link an /analyze session to its evidence, drafts, and reports. Generate
// one per new complaint and keep it in state (or a route param) for the
// lifetime of that complaint's workflow.
export function newComplaintId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `c_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
}
