import { createFileRoute } from "@tanstack/react-router";
import { AppLayout } from "@/components/AppLayout";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { API_BASE_URL } from "@/services/api";

export const Route = createFileRoute("/settings")({
  component: SettingsPage,
});

function SettingsPage() {
  const [apiBase, setApiBase] = useState(API_BASE_URL);
  const [dark, setDark] = useState(false);

  useEffect(() => {
    setDark(document.documentElement.classList.contains("dark"));
    const stored = localStorage.getItem("api_base");
    if (stored) setApiBase(stored);
  }, []);

  const save = () => {
    localStorage.setItem("api_base", apiBase);
    (window as any).__API_BASE__ = apiBase;
    toast.success("Settings saved. Reloading…");
    setTimeout(() => window.location.reload(), 500);
  };

  return (
    <AppLayout>
      <div className="p-4 md:p-8 max-w-3xl mx-auto">
        <PageHeader title="Settings" description="Configure your workspace." />

        <Card className="glass-card mb-6">
          <CardHeader><CardTitle className="text-base">Backend Connection</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>FastAPI Base URL</Label>
              <Input value={apiBase} onChange={(e) => setApiBase(e.target.value)} />
              <p className="text-xs text-muted-foreground">Defaults to <code>http://127.0.0.1:8000</code>.</p>
            </div>
            <Button className="gradient-brand text-white border-0" onClick={save}>Save</Button>
          </CardContent>
        </Card>

        <Card className="glass-card">
          <CardHeader><CardTitle className="text-base">Appearance</CardTitle></CardHeader>
          <CardContent className="flex items-center justify-between">
            <div>
              <div className="text-sm font-medium">Dark mode</div>
              <div className="text-xs text-muted-foreground">Toggle from the top navbar.</div>
            </div>
            <Switch checked={dark} onCheckedChange={(v) => {
              setDark(v); document.documentElement.classList.toggle("dark", v);
              localStorage.setItem("theme", v ? "dark" : "light");
            }} />
          </CardContent>
        </Card>
      </div>
    </AppLayout>
  );
}
