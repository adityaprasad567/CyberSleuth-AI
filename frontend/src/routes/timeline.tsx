import { createFileRoute } from "@tanstack/react-router";
import { AppLayout } from "@/components/AppLayout";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useState } from "react";
import { CybercrimeAPI } from "@/services/api";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { Clock, Loader2, Calendar, Activity } from "lucide-react";

export const Route = createFileRoute("/timeline")({
  component: TimelinePage,
});

function TimelinePage() {
  const [text, setText] = useState("");
  const [id, setId] = useState("");
  const [loading, setLoading] = useState(false);
  const [events, setEvents] = useState<any[]>([]);

  const run = async () => {
    if (!text.trim() && !id.trim()) return toast.error("Enter a complaint or ID");
    setLoading(true);
    try {
      // Backend's /timeline returns TimelineEvent[] directly: { time, event }
      const res = await CybercrimeAPI.timeline({ text: text || "", complaint_id: id || undefined });
      setEvents(res);
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || e?.message || "Failed to generate timeline");
    } finally { setLoading(false); }
  };

  return (
    <AppLayout>
      <div className="p-4 md:p-8 max-w-6xl mx-auto">
        <PageHeader title="Timeline" description="Reconstruct the chronological sequence of events from a complaint." />

        <Card className="glass-card mb-6">
          <CardContent className="p-6 grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="md:col-span-2 space-y-2">
              <Label>Complaint text</Label>
              <Textarea rows={4} value={text} onChange={(e) => setText(e.target.value)} placeholder="Paste the complaint narrative…" />
            </div>
            <div className="space-y-2">
              <Label>Or complaint ID</Label>
              <Input value={id} onChange={(e) => setId(e.target.value)} placeholder="c_abc123" />
              <Button onClick={run} disabled={loading} className="w-full gradient-brand text-white border-0 mt-2">
                {loading ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Generating…</> : <><Clock className="mr-2 h-4 w-4" /> Generate Timeline</>}
              </Button>
            </div>
          </CardContent>
        </Card>

        {events.length === 0 ? (
          <Card className="glass-card border-dashed">
            <CardContent className="py-16 text-center text-sm text-muted-foreground">No timeline yet — generate one above.</CardContent>
          </Card>
        ) : (
          <Card className="glass-card">
            <CardContent className="p-6">
              <ol className="relative border-l-2 border-border pl-6 space-y-6">
                {events.map((e, i) => (
                  <motion.li key={i} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.06 }} className="relative">
                    <span className="absolute -left-[33px] top-0 grid h-6 w-6 place-items-center rounded-full gradient-brand text-white shadow">
                      <Activity className="h-3 w-3" />
                    </span>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="outline" className="text-[10px]"><Calendar className="mr-1 h-3 w-3" />{e.time || e.timestamp || `Step ${i + 1}`}</Badge>
                      {e.type && <Badge className="bg-primary/10 text-primary text-[10px]">{e.type}</Badge>}
                    </div>
                    <div className="mt-1.5 text-sm font-semibold">{e.event || e.title || "Event"}</div>
                    {e.description && <div className="text-sm text-muted-foreground mt-1">{e.description}</div>}
                  </motion.li>
                ))}
              </ol>
            </CardContent>
          </Card>
        )}
      </div>
    </AppLayout>
  );
}
