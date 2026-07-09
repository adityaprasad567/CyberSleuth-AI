import { createFileRoute } from "@tanstack/react-router";
import { AppLayout } from "@/components/AppLayout";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { useState } from "react";
import { CybercrimeAPI } from "@/services/api";
import { toast } from "sonner";
import { Loader2, FileText, Copy, Download, Sparkles } from "lucide-react";

export const Route = createFileRoute("/complaint-draft")({
  component: ComplaintDraftPage,
});

function ComplaintDraftPage() {
  const [text, setText] = useState("");
  const [id, setId] = useState("");
  const [loading, setLoading] = useState(false);
  const [draft, setDraft] = useState("");

  const generate = async () => {
    if (!text.trim()) {
      toast.error("Complaint text is required — the backend classifies it internally.");
      return;
    }
    setLoading(true);
    try {
      // Backend's ReportRequest requires `text`; there's no separate
      // crime_type field - the backend classifies the text itself.
      const res = await CybercrimeAPI.complaintDraft({
        text,
        complaint_id: id || undefined,
      });
      setDraft(res.draft);
      toast.success("Draft generated");
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || e?.message || "Failed to generate draft");
    } finally { setLoading(false); }
  };

  const copy = async () => {
    await navigator.clipboard.writeText(draft);
    toast.success("Copied to clipboard");
  };

  const downloadTxt = () => {
    const blob = new Blob([draft], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = "complaint-draft.txt"; a.click();
    URL.revokeObjectURL(url);
  };

  const printPdf = () => {
    const w = window.open("", "_blank");
    if (!w) return;
    w.document.write(`<html><head><title>Complaint Draft</title><style>body{font-family:Georgia,serif;padding:48px;line-height:1.7;color:#111}pre{white-space:pre-wrap;font-family:inherit}</style></head><body><h1>Cybercrime Complaint Draft</h1><pre>${draft.replace(/[<>&]/g, (c: string) => (({ "<": "&lt;", ">": "&gt;", "&": "&amp;" } as Record<string,string>)[c]))}</pre></body></html>`);
    w.document.close(); w.focus(); w.print();
  };

  return (
    <AppLayout>
      <div className="p-4 md:p-8 max-w-6xl mx-auto">
        <PageHeader
          title="Complaint Draft"
          description="Generate a professionally worded cybercrime complaint draft ready for submission."
          actions={
            draft ? (
              <>
                <Button variant="outline" size="sm" onClick={copy}><Copy className="mr-2 h-3.5 w-3.5" /> Copy</Button>
                <Button variant="outline" size="sm" onClick={downloadTxt}><Download className="mr-2 h-3.5 w-3.5" /> TXT</Button>
                <Button size="sm" className="gradient-brand text-white border-0" onClick={printPdf}><FileText className="mr-2 h-3.5 w-3.5" /> PDF</Button>
              </>
            ) : null
          }
        />

        <Card className="glass-card mb-6">
          <CardContent className="p-6 grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="md:col-span-2 space-y-2">
              <Label>Complaint text</Label>
              <Textarea rows={5} value={text} onChange={(e) => setText(e.target.value)} placeholder="Describe the incident…" />
            </div>
            <div className="space-y-2">
              <Label>Complaint ID</Label>
              <Input value={id} onChange={(e) => setId(e.target.value)} placeholder="Optional — links evidence uploaded under this ID" />
              <Button onClick={generate} disabled={loading} className="w-full gradient-brand text-white border-0 mt-2">
                {loading ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Generating…</> : <><Sparkles className="mr-2 h-4 w-4" /> Generate Draft</>}
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card className="glass-card">
          <CardContent className="p-8 md:p-12">
            {draft ? (
              <article className="prose prose-slate dark:prose-invert max-w-none">
                <pre className="whitespace-pre-wrap font-serif text-[15px] leading-relaxed text-foreground">{draft}</pre>
              </article>
            ) : (
              <div className="text-center py-16 text-sm text-muted-foreground">
                Your generated complaint draft will appear here.
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </AppLayout>
  );
}
