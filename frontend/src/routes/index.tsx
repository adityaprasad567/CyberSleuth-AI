import { createFileRoute, Link } from "@tanstack/react-router";
import { AppLayout } from "@/components/AppLayout";
import { PageHeader } from "@/components/PageHeader";
import { StatCard } from "@/components/StatCard";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ArrowRight, ShieldCheck, FileBarChart2, FolderUp, ScanSearch, Sparkles, Activity, Gauge, Cpu } from "lucide-react";
import { motion } from "framer-motion";

export const Route = createFileRoute("/")({
  component: DashboardPage,
});

function DashboardPage() {
  return (
    <AppLayout>
      <div className="p-4 md:p-8 max-w-7xl mx-auto">
        {/* Hero */}
        <motion.section
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="relative overflow-hidden rounded-2xl border border-border bg-navy text-white p-8 md:p-12 mb-8"
        >
          <div className="absolute inset-0 opacity-40 pointer-events-none"
               style={{ background: "radial-gradient(1200px 400px at 10% 0%, oklch(0.5 0.22 275 / 0.6), transparent), radial-gradient(800px 400px at 100% 100%, oklch(0.72 0.14 210 / 0.4), transparent)" }} />
          <div className="relative max-w-3xl">
            <div className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/5 backdrop-blur px-3 py-1 text-xs">
              <Sparkles className="h-3.5 w-3.5 text-cyan" />
              <span>Powered by DistilBERT · RAG · Gemini</span>
            </div>
            <h1 className="mt-4 text-3xl md:text-5xl font-bold tracking-tight leading-tight">
              AI Cybercrime <span className="text-gradient-brand">Investigation Assistant</span>
            </h1>
            <p className="mt-4 text-sm md:text-base text-white/70 max-w-2xl">
              Analyze cybercrime complaints using AI, retrieve applicable Indian cyber laws, generate complaint
              drafts, create investigation reports, and assist victims with immediate actions — in seconds.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Button asChild size="lg" className="gradient-brand text-white border-0 shadow-lg hover:opacity-95">
                <Link to="/analyze">
                  Analyze Complaint <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
              <Button asChild size="lg" variant="outline" className="bg-white/5 border-white/20 text-white hover:bg-white/10 hover:text-white">
                <Link to="/reports">View Reports</Link>
              </Button>
            </div>
          </div>
        </motion.section>

        {/* Stats */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatCard icon={ScanSearch} label="Complaints Processed" value={1284} accent="primary" />
          <StatCard icon={FolderUp} label="Evidence Uploaded" value={3427} accent="cyan" />
          <StatCard icon={FileBarChart2} label="Reports Generated" value={912} accent="success" />
          <StatCard icon={Gauge} label="Model Accuracy" value={94} suffix="%" accent="warning" />
        </div>

        {/* Capabilities */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {[
            { icon: Cpu, title: "DistilBERT Classifier", desc: "Categorizes complaints by crime type with confidence scores." },
            { icon: ShieldCheck, title: "RAG Legal Retrieval", desc: "Retrieves applicable IT Act & IPC sections in real time." },
            { icon: Activity, title: "Gemini AI Summaries", desc: "Human-readable summaries, immediate actions & safety guidance." },
          ].map((c, i) => (
            <motion.div
              key={c.title}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 * i, duration: 0.4 }}
            >
              <Card className="glass-card border-border h-full">
                <CardHeader>
                  <div className="grid h-10 w-10 place-items-center rounded-lg gradient-brand text-white shadow">
                    <c.icon className="h-5 w-5" />
                  </div>
                  <CardTitle className="mt-3 text-base">{c.title}</CardTitle>
                </CardHeader>
                <CardContent className="text-sm text-muted-foreground">{c.desc}</CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      </div>
    </AppLayout>
  );
}
