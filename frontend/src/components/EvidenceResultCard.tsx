import { useState } from "react";
import { Loader2, ScanText, CheckCircle2, AlertTriangle, ImageIcon, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { CybercrimeAPI, EvidenceRecord } from "@/services/api";
import { toast } from "sonner";

export interface EvidenceUploadItem {
  file: File;
  status: "processing" | "done" | "error";
  record?: EvidenceRecord;
  editedText?: string;
  error?: string;
}

const SUMMARY_LABELS: Record<string, string> = {
  phone_numbers: "Phone Numbers",
  emails: "Emails",
  upi_ids: "UPI IDs",
  transaction_ids: "Transaction IDs",
  urls: "URLs",
  bank_names: "Bank Names",
  amounts: "Amounts",
  dates: "Dates",
  times: "Times",
  social_handles: "Social Handles",
  reference_numbers: "Reference Numbers",
  wallet_ids: "Wallet IDs",
  order_ids: "Order IDs",
  otps: "OTPs",
  ip_addresses: "IP Addresses",
  device_ids: "Device IDs",
  masked_account_numbers: "Account Numbers",
};

/** Feature 13: renders one uploaded evidence image's OCR pipeline result -
 * processing status, editable extracted text, crime prediction/confidence,
 * and the structured "Key Information" entity summary. */
export function EvidenceResultCard({
  item,
  onUpdated,
}: {
  item: EvidenceUploadItem;
  onUpdated: (record: EvidenceRecord) => void;
}) {
  const [text, setText] = useState(item.editedText ?? item.record?.ocr_text ?? "");
  const [saving, setSaving] = useState(false);
  const record = item.record;

  const save = async () => {
    if (!record) return;
    setSaving(true);
    try {
      const updated = await CybercrimeAPI.updateEvidenceText(record.id, text);
      onUpdated(updated);
      toast.success("Extracted text updated — crime prediction re-checked");
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || e?.message || "Failed to save edited text");
    } finally {
      setSaving(false);
    }
  };

  const summaryEntries = record?.evidence_summary
    ? Object.entries(record.evidence_summary).filter(
        ([key, value]) => key !== "summary" && Array.isArray(value) && value.length > 0,
      )
    : [];

  return (
    <div className="rounded-lg border border-border bg-card p-4 space-y-3">
      <div className="flex items-center gap-2">
        <ImageIcon className="h-4 w-4 text-muted-foreground shrink-0" />
        <div className="text-sm font-medium truncate flex-1">{item.file.name}</div>
        {item.status === "processing" && (
          <Badge variant="secondary" className="gap-1">
            <Loader2 className="h-3 w-3 animate-spin" /> OCR Processing…
          </Badge>
        )}
        {item.status === "done" && (
          <Badge variant="secondary" className="gap-1 text-green-700 dark:text-green-400">
            <CheckCircle2 className="h-3 w-3" /> OCR Completed
          </Badge>
        )}
        {item.status === "error" && (
          <Badge variant="destructive" className="gap-1">
            <AlertTriangle className="h-3 w-3" /> Upload Failed
          </Badge>
        )}
      </div>

      {item.status === "error" && (
        <div className="text-xs text-destructive">{item.error}</div>
      )}

      {item.status === "done" && record && (
        <>
          {record.ocr_message && !record.ocr_text && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground bg-muted/40 rounded-md px-3 py-2">
              <ScanText className="h-3.5 w-3.5 shrink-0" /> {record.ocr_message}
            </div>
          )}

          {(record.ocr_text || record.ocr_message) && (
            <div className="space-y-1.5">
              <div className="text-xs font-medium text-muted-foreground">Extracted Text (editable)</div>
              <Textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                rows={4}
                className="text-sm font-mono"
                placeholder="No text extracted"
              />
              <div className="flex justify-end">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={save}
                  disabled={saving || text === (record.ocr_text || "")}
                  className="gap-1.5"
                >
                  <Save className="h-3.5 w-3.5" />
                  {saving ? "Saving…" : "Save Edited Text"}
                </Button>
              </div>
            </div>
          )}

          {record.crime_prediction && (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-medium text-muted-foreground">Detected Crime Category:</span>
              <Badge className="gradient-brand text-white border-0">
                {record.crime_prediction.replace(/_/g, " ")}
              </Badge>
              {typeof record.confidence === "number" && (
                <span className="text-xs text-muted-foreground">
                  Confidence: {(record.confidence * 100).toFixed(0)}%
                </span>
              )}
            </div>
          )}

          {summaryEntries.length > 0 && (
            <div className="space-y-1.5">
              <div className="text-xs font-medium text-muted-foreground">Key Information</div>
              <div className="flex flex-wrap gap-1.5">
                {summaryEntries.map(([key, values]) =>
                  (values as string[]).map((v, i) => (
                    <Badge key={`${key}-${i}`} variant="outline" className="text-[11px] font-normal">
                      {SUMMARY_LABELS[key] || key}: {v}
                    </Badge>
                  )),
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
