import { createFileRoute } from "@tanstack/react-router";
import { AppLayout } from "@/components/AppLayout";
import { PageHeader } from "@/components/PageHeader";
import { EvidenceDropzone } from "@/components/EvidenceDropzone";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useState } from "react";
import { CybercrimeAPI, newComplaintId, type AnalyzeResponse } from "@/services/api";
import { toast } from "sonner";
import { motion, AnimatePresence } from "framer-motion";
import { AlertTriangle, CheckCircle2, Loader2, ScanSearch, Scale, ShieldAlert, Sparkles, Siren, Download, Mail } from "lucide-react";

export const Route = createFileRoute("/analyze")({
  component: AnalyzePage,
});

function ConfidenceRing({ value }: { value: number }) {
  const pct = Math.max(0, Math.min(100, value));
  const r = 42;
  const c = 2 * Math.PI * r;
  const offset = c - (pct / 100) * c;
  return (
    <div className="relative h-28 w-28">
      <svg className="h-full w-full -rotate-90">
        <circle cx="56" cy="56" r={r} stroke="var(--muted)" strokeWidth="10" fill="none" />
        <motion.circle
          cx="56" cy="56" r={r} stroke="url(#g)" strokeWidth="10" fill="none" strokeLinecap="round"
          strokeDasharray={c}
          initial={{ strokeDashoffset: c }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1, ease: "easeOut" }}
        />
        <defs>
          <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="oklch(0.5 0.22 275)" />
            <stop offset="100%" stopColor="oklch(0.72 0.14 210)" />
          </linearGradient>
        </defs>
      </svg>
      <div className="absolute inset-0 grid place-items-center">
        <div className="text-center">
          <div className="text-xl font-bold">{pct.toFixed(0)}%</div>
          <div className="text-[10px] text-muted-foreground uppercase">Confidence</div>
        </div>
      </div>
    </div>
  );
}

function AnalyzePage() {
  const [text, setText] = useState("");
  const [date, setDate] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [progress, setProgress] = useState(0);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [complaintId, setComplaintId] = useState<string>("");
  const [reportFormat, setReportFormat] = useState<"pdf" | "docx" | "txt">("pdf");
  const [downloading, setDownloading] = useState(false);

  const downloadReport = async () => {
    if (!text.trim()) return;
    setDownloading(true);
    try {
      const { blob, filename } = await CybercrimeAPI.generateReport({
        text,
        incident_date: date || undefined,
        complaint_id: complaintId || undefined,
        export_format: reportFormat,
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Report downloaded");
    } catch (e: any) {
      toast.error(
        e?.response?.data?.detail || e?.message || "Could not generate report"
      );
    } finally {
      setDownloading(false);
    }
  };

  const draftMail = () => {
    if (!result) return;
    const subject = encodeURIComponent(
      `Cybercrime Complaint - ${result.classification.label.replace(/_/g, " ")}${complaintId ? ` (Ref: ${complaintId.slice(0, 12)})` : ""}`
    );
    const body = encodeURIComponent(
      `${result.draft_complaint || text}\n\n---\nSubmitted via CyberSleuth AI` +
      (complaintId ? `\nComplaint Reference: ${complaintId}` : "")
    );
    window.location.href = `mailto:?subject=${subject}&body=${body}`;
  };

  const submit = async () => {
    if (!text.trim()) {
      toast.error("Please describe the complaint first.");
      return;
    }
    if (text.trim().length < 15) {
      toast.error("Please describe what happened in a bit more detail (at least a sentence) for an accurate result.");
      return;
    }
    if (date && date > new Date().toISOString().split("T")[0]) {
      toast.error("Incident date can't be in the future.");
      return;
    }
    setLoading(true);
    setResult(null);
    // The backend never issues a complaint_id, so we mint one client-side
    // the first time this complaint is analyzed, and reuse it for evidence.
    const id = complaintId || newComplaintId();
    setComplaintId(id);
    try {
      const res = await CybercrimeAPI.analyze({ text, incident_date: date || undefined });
      setResult(res);
      if (files.length) {
        await CybercrimeAPI.uploadEvidence(files, id, setProgress);
        toast.success("Evidence uploaded");
      }
      toast.success("Analysis complete");
    } catch (e: any) {
      toast.error(
        e?.response?.data?.detail || e?.message || "Analysis failed. Ensure the backend is running at http://127.0.0.1:8000"
      );
    } finally {
      setLoading(false);
      setProgress(0);
    }
  };

  return (
    <AppLayout>
      <div className="p-4 md:p-8 max-w-7xl mx-auto">
        <PageHeader
          title="Analyze Complaint"
          description="Submit a cybercrime complaint. Our AI will classify the crime, retrieve applicable laws, and generate actionable insights."
        />

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          {/* LEFT */}
          <Card className="glass-card lg:col-span-2">
            <CardHeader>
              <CardTitle className="text-base">Complaint Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="space-y-2">
                <Label htmlFor="complaint">Complaint description</Label>
                <Textarea
                  id="complaint"
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  rows={8}
                  placeholder="Describe what happened — messages received, links clicked, transactions, screenshots, etc."
                  className="resize-none"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="date">Incident date</Label>
                <Input
                  id="date"
                  type="date"
                  value={date}
                  onChange={(e) => setDate(e.target.value)}
                  max={new Date().toISOString().split("T")[0]}
                />
              </div>
              <div className="space-y-2">
                <Label>Evidence files</Label>
                <EvidenceDropzone files={files} onChange={setFiles} progress={progress} disabled={loading} />
              </div>
              <Button onClick={submit} disabled={loading} className="w-full gradient-brand text-white border-0 h-11">
                {loading ? (
                  <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Analyzing…</>
                ) : (
                  <><ScanSearch className="mr-2 h-4 w-4" /> Analyze Complaint</>
                )}
              </Button>
            </CardContent>
          </Card>

          {/* RIGHT */}
          <div className="lg:col-span-3 space-y-4">
            <AnimatePresence mode="wait">
              {loading && (
                <motion.div key="loading" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                  <Card className="glass-card"><CardContent className="p-6 space-y-4">
                    <Skeleton className="h-24 w-full" />
                    <Skeleton className="h-16 w-full" />
                    <Skeleton className="h-16 w-2/3" />
                  </CardContent></Card>
                </motion.div>
              )}
              {!loading && !result && (
                <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                  <Card className="glass-card border-dashed">
                    <CardContent className="py-16 text-center">
                      <div className="mx-auto grid h-14 w-14 place-items-center rounded-full bg-primary/10 text-primary mb-4">
                        <Sparkles className="h-6 w-6" />
                      </div>
                      <div className="text-base font-semibold">Awaiting analysis</div>
                      <p className="text-sm text-muted-foreground mt-1 max-w-sm mx-auto">
                        Fill in the complaint details on the left and click Analyze to see AI-driven insights, laws and next steps.
                      </p>
                    </CardContent>
                  </Card>
                </motion.div>
              )}
              {!loading && result && (
                <motion.div key="result" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
                  {result.low_confidence && (
                    <Card className="border-warning bg-warning/10">
                      <CardContent className="p-4 flex gap-3 items-start">
                        <AlertTriangle className="h-5 w-5 text-warning shrink-0 mt-0.5" />
                        <div className="text-sm">
                          <div className="font-medium text-warning">Not enough detail to classify confidently</div>
                          <div className="text-muted-foreground mt-1">
                            The description is too short or unclear for a reliable result (confidence:{" "}
                            {(result.classification.confidence * 100).toFixed(0)}%). The crime type below is only
                            the model's best guess - add more specific details (what happened, which app/platform,
                            what was asked of you, any amounts involved) and re-analyze for an accurate classification.
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  {result.is_urgent && result.emergency_message && (
                    <Card className="border-destructive bg-destructive/10">
                      <CardContent className="p-4 flex gap-3 items-start">
                        <Siren className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
                        <div className="text-sm font-medium text-destructive">{result.emergency_message}</div>
                      </CardContent>
                    </Card>
                  )}

                  <Card className="glass-card">
                    <CardContent className="p-6">
                      <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-6 items-center">
                        <div className="min-w-0">
                          <div className="text-xs uppercase text-muted-foreground font-medium">Predicted Crime</div>
                          <div className="text-2xl font-bold mt-1 truncate">{result.classification.label || "Unclassified"}</div>
                          <div className="flex flex-wrap items-center gap-2 mt-3">
                            {result.low_confidence && (
                              <Badge className="bg-warning/15 text-warning border-warning/30 text-[10px]">
                                Low Confidence
                              </Badge>
                            )}
                            {result.classification.legal_tags?.map((tag) => (
                              <Badge key={tag} variant="outline" className="text-[10px]">{tag}</Badge>
                            ))}
                            <Badge variant="outline" className="font-mono text-[10px]">ID: {complaintId.slice(0, 12)}</Badge>
                          </div>
                        </div>
                        <ConfidenceRing value={result.classification.confidence * 100} />
                      </div>
                      <div className="flex flex-wrap items-center gap-2 mt-5 pt-5 border-t border-border">
                        <select
                          value={reportFormat}
                          onChange={(e) => setReportFormat(e.target.value as "pdf" | "docx" | "txt")}
                          className="h-9 rounded-md border border-input bg-background px-3 text-sm"
                        >
                          <option value="pdf">PDF</option>
                          <option value="docx">DOCX</option>
                          <option value="txt">TXT</option>
                        </select>
                        <Button size="sm" onClick={downloadReport} disabled={downloading} className="gradient-brand text-white border-0">
                          {downloading ? (
                            <><Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" /> Generating…</>
                          ) : (
                            <><Download className="mr-2 h-3.5 w-3.5" /> Download Report</>
                          )}
                        </Button>
                        <Button size="sm" variant="outline" onClick={draftMail}>
                          <Mail className="mr-2 h-3.5 w-3.5" /> Draft for Mail
                        </Button>
                      </div>
                    </CardContent>
                  </Card>

                  {result.crime_type_explanation && (
                    <Card className="glass-card">
                      <CardHeader><CardTitle className="text-sm flex items-center gap-2"><Sparkles className="h-4 w-4 text-primary" /> Explanation</CardTitle></CardHeader>
                      <CardContent className="text-sm leading-relaxed whitespace-pre-wrap">{result.crime_type_explanation}</CardContent>
                    </Card>
                  )}

                  {result.applicable_law?.length > 0 && (
                    <Card className="glass-card">
                      <CardHeader><CardTitle className="text-sm flex items-center gap-2"><Scale className="h-4 w-4 text-primary" /> Applicable Law</CardTitle></CardHeader>
                      <CardContent className="space-y-2">
                        {result.regime_note && (
                          <div className="text-xs text-muted-foreground italic mb-2">{result.regime_note}</div>
                        )}
                        {result.applicable_law.map((l) => (
                          <div key={l.chunk_id} className="rounded-lg border border-border bg-muted/30 p-3">
                            <div className="text-xs font-mono text-muted-foreground mb-1">{l.chunk_id}</div>
                            <div className="text-sm">{l.plain_language_summary}</div>
                          </div>
                        ))}
                      </CardContent>
                    </Card>
                  )}

                  {(result.immediate_actions?.length > 0 || result.safety_recommendations?.length > 0) && (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {result.immediate_actions?.length > 0 && (
                        <Card className="glass-card">
                          <CardHeader><CardTitle className="text-sm flex items-center gap-2"><AlertTriangle className="h-4 w-4 text-warning" /> Immediate Actions</CardTitle></CardHeader>
                          <CardContent><ul className="space-y-2 text-sm">
                            {result.immediate_actions.map((a, i) => (
                              <li key={i} className="flex gap-2"><CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" /><span>{a}</span></li>
                            ))}
                          </ul></CardContent>
                        </Card>
                      )}
                      {result.safety_recommendations?.length > 0 && (
                        <Card className="glass-card">
                          <CardHeader><CardTitle className="text-sm flex items-center gap-2"><ShieldAlert className="h-4 w-4 text-cyan" /> Safety Recommendations</CardTitle></CardHeader>
                          <CardContent><ul className="space-y-2 text-sm">
                            {result.safety_recommendations.map((a, i) => (
                              <li key={i} className="flex gap-2"><CheckCircle2 className="h-4 w-4 text-cyan shrink-0 mt-0.5" /><span>{a}</span></li>
                            ))}
                          </ul></CardContent>
                        </Card>
                      )}
                    </div>
                  )}

                  {result.draft_complaint && (
                    <Card className="glass-card">
                      <CardHeader><CardTitle className="text-sm">Quick Draft Complaint</CardTitle></CardHeader>
                      <CardContent className="text-sm whitespace-pre-wrap font-serif">{result.draft_complaint}</CardContent>
                    </Card>
                  )}

                  {result.uncovered_aspects && (
                    <Card className="glass-card border-dashed">
                      <CardHeader><CardTitle className="text-sm text-muted-foreground">Not Covered by Retrieved Law</CardTitle></CardHeader>
                      <CardContent className="text-sm text-muted-foreground">{result.uncovered_aspects}</CardContent>
                    </Card>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
