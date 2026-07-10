import { createFileRoute } from "@tanstack/react-router";
import { AppLayout } from "@/components/AppLayout";
import { PageHeader } from "@/components/PageHeader";
import { EvidenceDropzone } from "@/components/EvidenceDropzone";
import { EvidenceResultCard, EvidenceUploadItem } from "@/components/EvidenceResultCard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useState } from "react";
import { CybercrimeAPI, EvidenceRecord } from "@/services/api";
import { toast } from "sonner";
import { UploadCloud, Search, FileText } from "lucide-react";

export const Route = createFileRoute("/evidence")({
  component: EvidencePage,
});

function EvidencePage() {
  const [files, setFiles] = useState<File[]>([]);
  const [complaintId, setComplaintId] = useState("");
  const [uploading, setUploading] = useState(false);
  // Feature 13 (OCR pipeline): per-file upload/OCR status, replacing the old
  // single aggregate progress bar so each image can show its own
  // "OCR Processing… / OCR Completed" state as its request resolves.
  const [uploadItems, setUploadItems] = useState<EvidenceUploadItem[]>([]);

  const [lookupId, setLookupId] = useState("");
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const upload = async () => {
    if (!files.length) return toast.error("Add at least one file");
    if (!complaintId.trim()) return toast.error("Complaint ID is required — the backend links evidence to a complaint by this ID");

    setUploading(true);
    const pending: EvidenceUploadItem[] = files.map((file) => ({ file, status: "processing" }));
    setUploadItems((prev) => [...prev, ...pending]);
    const startIdx = uploadItems.length;

    // Uploaded one at a time (not Promise.all) so each card's status
    // updates as soon as its own OCR result comes back, rather than all
    // flipping to "done" at once when the slowest file finishes.
    for (let i = 0; i < files.length; i++) {
      try {
        const record = await CybercrimeAPI.uploadSingleEvidence(files[i], complaintId.trim());
        setUploadItems((prev) => {
          const next = [...prev];
          next[startIdx + i] = { file: files[i], status: "done", record, editedText: record.ocr_text };
          return next;
        });
      } catch (e: any) {
        const message = e?.response?.data?.detail || e?.message || "Upload failed";
        setUploadItems((prev) => {
          const next = [...prev];
          next[startIdx + i] = { file: files[i], status: "error", error: message };
          return next;
        });
      }
    }

    toast.success("Evidence processed");
    setFiles([]);
    setUploading(false);
  };

  const updateRecord = (idx: number, record: EvidenceRecord) => {
    setUploadItems((prev) => {
      const next = [...prev];
      next[idx] = { ...next[idx], record, editedText: record.ocr_text };
      return next;
    });
  };

  const lookup = async () => {
    if (!lookupId.trim()) return;
    setLoading(true);
    try {
      const res = await CybercrimeAPI.getEvidence(lookupId.trim());
      setItems(res);
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || e?.message || "Failed to fetch evidence");
    } finally { setLoading(false); }
  };

  return (
    <AppLayout>
      <div className="p-4 md:p-8 max-w-7xl mx-auto">
        <PageHeader title="Evidence" description="Upload and manage digital evidence tied to a complaint." />

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card className="glass-card">
            <CardHeader><CardTitle className="text-base flex items-center gap-2"><UploadCloud className="h-4 w-4 text-primary" /> Upload Evidence</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Complaint ID (optional)</Label>
                <Input value={complaintId} onChange={(e) => setComplaintId(e.target.value)} placeholder="e.g. c_abc123" />
              </div>
              <EvidenceDropzone files={files} onChange={setFiles} disabled={uploading} />
              <Button onClick={upload} disabled={uploading || !files.length} className="w-full gradient-brand text-white border-0">
                {uploading ? "Uploading & running OCR…" : "Upload"}
              </Button>

              {uploadItems.length > 0 && (
                <div className="space-y-3 pt-2">
                  {uploadItems.map((item, i) => (
                    <EvidenceResultCard key={i} item={item} onUpdated={(record) => updateRecord(i, record)} />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="glass-card">
            <CardHeader><CardTitle className="text-base flex items-center gap-2"><Search className="h-4 w-4 text-primary" /> Retrieve Evidence</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2">
                <Input value={lookupId} onChange={(e) => setLookupId(e.target.value)} placeholder="Enter complaint ID" />
                <Button onClick={lookup} disabled={loading} variant="outline">Fetch</Button>
              </div>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {items.length === 0 && (
                  <div className="text-sm text-muted-foreground text-center py-8">No evidence yet</div>
                )}
                {items.map((it, i) => (
                  <div key={i} className="flex items-center gap-3 rounded-lg border border-border bg-muted/20 p-3">
                    <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-medium truncate">{it.filename || `Evidence ${i + 1}`}</div>
                      <div className="text-xs text-muted-foreground truncate">
                        {it.file_type} · {(it.file_size / 1024).toFixed(1)} KB · SHA-256: {it.sha256?.slice(0, 10)}…
                      </div>
                      {it.crime_prediction && (
                        <div className="text-xs text-muted-foreground mt-0.5">
                          Crime category: {it.crime_prediction.replace(/_/g, " ")}
                          {typeof it.confidence === "number" && ` (${(it.confidence * 100).toFixed(0)}%)`}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </AppLayout>
  );
}

