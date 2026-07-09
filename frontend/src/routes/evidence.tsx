import { createFileRoute } from "@tanstack/react-router";
import { AppLayout } from "@/components/AppLayout";
import { PageHeader } from "@/components/PageHeader";
import { EvidenceDropzone } from "@/components/EvidenceDropzone";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useState } from "react";
import { CybercrimeAPI } from "@/services/api";
import { toast } from "sonner";
import { UploadCloud, Search, FileText } from "lucide-react";

export const Route = createFileRoute("/evidence")({
  component: EvidencePage,
});

function EvidencePage() {
  const [files, setFiles] = useState<File[]>([]);
  const [complaintId, setComplaintId] = useState("");
  const [progress, setProgress] = useState(0);
  const [uploading, setUploading] = useState(false);

  const [lookupId, setLookupId] = useState("");
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const upload = async () => {
    if (!files.length) return toast.error("Add at least one file");
    if (!complaintId.trim()) return toast.error("Complaint ID is required — the backend links evidence to a complaint by this ID");
    setUploading(true);
    try {
      // Backend accepts one file per call; api.ts loops internally and
      // reports combined progress across all files.
      const res = await CybercrimeAPI.uploadEvidence(files, complaintId.trim(), setProgress);
      toast.success("Evidence uploaded");
      setFiles([]);
      setItems(res);
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || e?.message || "Upload failed");
    } finally {
      setUploading(false); setProgress(0);
    }
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
              <EvidenceDropzone files={files} onChange={setFiles} progress={progress} disabled={uploading} />
              <Button onClick={upload} disabled={uploading || !files.length} className="w-full gradient-brand text-white border-0">
                {uploading ? "Uploading…" : "Upload"}
              </Button>
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
