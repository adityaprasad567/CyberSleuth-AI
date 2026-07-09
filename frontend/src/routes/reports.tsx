import { createFileRoute } from "@tanstack/react-router";
import { AppLayout } from "@/components/AppLayout";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import { useEffect, useMemo, useState } from "react";
import { CybercrimeAPI } from "@/services/api";
import { toast } from "sonner";
import {
  Download,
  Printer,
  Search,
  FileBarChart2,
  RefreshCw,
  Share2,
  Filter,
  ArrowUpDown,
  X,
} from "lucide-react";

export const Route = createFileRoute("/reports")({
  component: ReportsPage,
});

type SortKey = "newest" | "oldest" | "title" | "type";

const PAGE_SIZE_OPTIONS = [10, 25, 50];

function ReportsPage() {
  const [loading, setLoading] = useState(true);
  const [reports, setReports] = useState<any[]>([]);
  const [q, setQ] = useState("");
  const [crimeType, setCrimeType] = useState<string>("all");
  const [sort, setSort] = useState<SortKey>("newest");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(10);
  const [active, setActive] = useState<any | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const res = await CybercrimeAPI.getReports();
      setReports(res);
      setActive(res[0] || null);
    } catch (e: any) {
      toast.error(
        e?.response?.data?.detail || e?.message || "Could not load reports",
      );
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    load();
  }, []);

  // Reset page when filters change
  useEffect(() => {
    setPage(1);
  }, [q, crimeType, sort, pageSize]);

  const crimeTypes = useMemo(() => {
    const set = new Set<string>();
    reports.forEach((r) => {
      const t = r.crime_type || r.type;
      if (t) set.add(String(t));
    });
    return Array.from(set).sort();
  }, [reports]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    let list = reports.filter((r) => {
      const matchesQuery = !needle || JSON.stringify(r).toLowerCase().includes(needle);
      const matchesType =
        crimeType === "all" || String(r.crime_type || r.type || "") === crimeType;
      return matchesQuery && matchesType;
    });

    const ts = (r: any) => {
      const v = r.created_at || r.createdAt || r.timestamp || r.date;
      const t = v ? new Date(v).getTime() : 0;
      return Number.isNaN(t) ? 0 : t;
    };
    const title = (r: any) =>
      String(r.title || r.crime_type || r.complaint_id || r.id || "").toLowerCase();
    const typ = (r: any) => String(r.crime_type || r.type || "").toLowerCase();

    list = [...list].sort((a, b) => {
      switch (sort) {
        case "oldest":
          return ts(a) - ts(b);
        case "title":
          return title(a).localeCompare(title(b));
        case "type":
          return typ(a).localeCompare(typ(b));
        case "newest":
        default:
          return ts(b) - ts(a);
      }
    });
    return list;
  }, [reports, q, crimeType, sort]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const paged = useMemo(
    () => filtered.slice((currentPage - 1) * pageSize, currentPage * pageSize),
    [filtered, currentPage, pageSize],
  );

  const resetFilters = () => {
    setQ("");
    setCrimeType("all");
    setSort("newest");
  };
  const hasFilters = q.trim() !== "" || crimeType !== "all" || sort !== "newest";

  const [fetchingFile, setFetchingFile] = useState(false);

  const download = async () => {
    if (!active?.id) {
      toast.error("No report selected");
      return;
    }
    setFetchingFile(true);
    try {
      const blob = await CybercrimeAPI.downloadReport(active.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = active.filename || `report-${active.id}.${active.format || "pdf"}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || e?.message || "Could not download report");
    } finally {
      setFetchingFile(false);
    }
  };
  const print = async () => {
    if (!active?.id) return;
    setFetchingFile(true);
    try {
      const blob = await CybercrimeAPI.downloadReport(active.id);
      const url = URL.createObjectURL(blob);
      const w = window.open(url, "_blank");
      // PDF opens directly in the browser's PDF viewer, which has its own
      // print button - for docx/txt there's no in-browser preview, so at
      // least the real file downloads/opens instead of showing nothing.
      w?.addEventListener?.("load", () => w.print());
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || e?.message || "Could not open report");
    } finally {
      setFetchingFile(false);
    }
  };
  const share = async () => {
    if (!active) return;
    try {
      await navigator.clipboard.writeText(
        `Cybercrime report - ${active.crime_type || ""}\nComplaint ID: ${active.complaint_id || ""}\nReport ID: ${active.id}\nGenerated: ${active.generated_date || ""}`
      );
      toast.success("Report reference copied to clipboard");
    } catch {}
  };

  // Pagination page numbers with ellipsis
  const pageNumbers = useMemo(() => {
    const nums: (number | "ellipsis")[] = [];
    const push = (n: number | "ellipsis") => nums.push(n);
    if (totalPages <= 7) {
      for (let i = 1; i <= totalPages; i++) push(i);
    } else {
      push(1);
      if (currentPage > 3) push("ellipsis");
      const start = Math.max(2, currentPage - 1);
      const end = Math.min(totalPages - 1, currentPage + 1);
      for (let i = start; i <= end; i++) push(i);
      if (currentPage < totalPages - 2) push("ellipsis");
      push(totalPages);
    }
    return nums;
  }, [currentPage, totalPages]);

  return (
    <AppLayout>
      <div className="p-4 md:p-8 max-w-7xl mx-auto">
        <PageHeader
          title="Investigation Reports"
          description="Browse, filter and export AI-generated investigation reports."
          actions={
            <Button variant="outline" size="sm" onClick={load}>
              <RefreshCw className="mr-2 h-3.5 w-3.5" /> Refresh
            </Button>
          }
        />

        {/* Filter bar */}
        <Card className="glass-card mb-6">
          <CardContent className="p-4 flex flex-col lg:flex-row lg:items-center gap-3">
            <div className="relative flex-1 min-w-0">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                className="pl-9"
                placeholder="Search by ID, crime type, keywords…"
                value={q}
                onChange={(e) => setQ(e.target.value)}
              />
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <div className="flex items-center gap-2">
                <Filter className="h-4 w-4 text-muted-foreground" />
                <Select value={crimeType} onValueChange={setCrimeType}>
                  <SelectTrigger className="w-[180px]">
                    <SelectValue placeholder="Crime type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All crime types</SelectItem>
                    {crimeTypes.map((t) => (
                      <SelectItem key={t} value={t}>
                        {t}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-center gap-2">
                <ArrowUpDown className="h-4 w-4 text-muted-foreground" />
                <Select value={sort} onValueChange={(v) => setSort(v as SortKey)}>
                  <SelectTrigger className="w-[160px]">
                    <SelectValue placeholder="Sort" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="newest">Newest first</SelectItem>
                    <SelectItem value="oldest">Oldest first</SelectItem>
                    <SelectItem value="title">Title (A–Z)</SelectItem>
                    <SelectItem value="type">Crime type</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <Select
                value={String(pageSize)}
                onValueChange={(v) => setPageSize(Number(v))}
              >
                <SelectTrigger className="w-[110px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PAGE_SIZE_OPTIONS.map((n) => (
                    <SelectItem key={n} value={String(n)}>
                      {n} / page
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              {hasFilters && (
                <Button variant="ghost" size="sm" onClick={resetFilters}>
                  <X className="mr-1 h-3.5 w-3.5" /> Clear
                </Button>
              )}
            </div>
          </CardContent>
        </Card>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card className="glass-card lg:col-span-1">
            <CardContent className="p-4">
              <div className="flex items-center justify-between mb-3 text-xs text-muted-foreground">
                <span>
                  {loading
                    ? "Loading…"
                    : `${filtered.length} report${filtered.length === 1 ? "" : "s"}`}
                </span>
                {!loading && filtered.length > 0 && (
                  <span>
                    Page {currentPage} of {totalPages}
                  </span>
                )}
              </div>

              <div className="space-y-2 max-h-[60vh] overflow-y-auto pr-1">
                {loading ? (
                  Array.from({ length: 5 }).map((_, i) => (
                    <Skeleton key={i} className="h-16 w-full" />
                  ))
                ) : paged.length === 0 ? (
                  <div className="text-sm text-muted-foreground text-center py-12">
                    No reports match your filters
                  </div>
                ) : (
                  paged.map((r, i) => {
                    const id = r.complaint_id || r.id || `report-${i}`;
                    const isActive = active === r;
                    const type = r.crime_type || r.type;
                    return (
                      <button
                        key={String(id) + i}
                        onClick={() => setActive(r)}
                        className={`w-full text-left rounded-lg border p-3 transition-colors ${
                          isActive
                            ? "border-primary bg-primary/5"
                            : "border-border hover:bg-muted/40"
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <FileBarChart2 className="h-4 w-4 text-primary shrink-0" />
                          <div className="text-sm font-semibold truncate">
                            {r.title || type || `Report ${(currentPage - 1) * pageSize + i + 1}`}
                          </div>
                        </div>
                        <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground">
                          <Badge variant="outline" className="font-mono">
                            {String(id).slice(0, 12)}
                          </Badge>
                          {type && (
                            <Badge className="bg-primary/10 text-primary border-0">
                              {type}
                            </Badge>
                          )}
                          {r.created_at && (
                            <span>{new Date(r.created_at).toLocaleDateString()}</span>
                          )}
                        </div>
                      </button>
                    );
                  })
                )}
              </div>

              {!loading && totalPages > 1 && (
                <div className="mt-4">
                  <Pagination>
                    <PaginationContent className="flex-wrap">
                      <PaginationItem>
                        <PaginationPrevious
                          href="#"
                          onClick={(e) => {
                            e.preventDefault();
                            setPage((p) => Math.max(1, p - 1));
                          }}
                          aria-disabled={currentPage === 1}
                          className={currentPage === 1 ? "pointer-events-none opacity-50" : ""}
                        />
                      </PaginationItem>
                      {pageNumbers.map((n, idx) =>
                        n === "ellipsis" ? (
                          <PaginationItem key={`e-${idx}`}>
                            <PaginationEllipsis />
                          </PaginationItem>
                        ) : (
                          <PaginationItem key={n}>
                            <PaginationLink
                              href="#"
                              isActive={n === currentPage}
                              onClick={(e) => {
                                e.preventDefault();
                                setPage(n);
                              }}
                            >
                              {n}
                            </PaginationLink>
                          </PaginationItem>
                        ),
                      )}
                      <PaginationItem>
                        <PaginationNext
                          href="#"
                          onClick={(e) => {
                            e.preventDefault();
                            setPage((p) => Math.min(totalPages, p + 1));
                          }}
                          aria-disabled={currentPage === totalPages}
                          className={
                            currentPage === totalPages ? "pointer-events-none opacity-50" : ""
                          }
                        />
                      </PaginationItem>
                    </PaginationContent>
                  </Pagination>
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="glass-card lg:col-span-2">
            <CardContent className="p-6 md:p-10">
              {!active ? (
                <div className="text-center py-24 text-sm text-muted-foreground">
                  Select a report to preview
                </div>
              ) : (
                <>
                  <div className="flex flex-wrap items-center gap-2 mb-4">
                    <Button
                      size="sm"
                      onClick={download}
                      disabled={fetchingFile}
                      className="gradient-brand text-white border-0"
                    >
                      {fetchingFile ? (
                        <><RefreshCw className="mr-2 h-3.5 w-3.5 animate-spin" /> Working…</>
                      ) : (
                        <><Download className="mr-2 h-3.5 w-3.5" /> Download</>
                      )}
                    </Button>
                    <Button size="sm" variant="outline" onClick={print} disabled={fetchingFile}>
                      <Printer className="mr-2 h-3.5 w-3.5" /> Print
                    </Button>
                    <Button size="sm" variant="outline" onClick={share} disabled={fetchingFile}>
                      <Share2 className="mr-2 h-3.5 w-3.5" /> Share
                    </Button>
                    {active?.complaint_id && (
                      <Badge variant="outline" className="ml-auto font-mono text-[11px]">
                        {active.complaint_id}
                      </Badge>
                    )}
                  </div>
                  <div className="rounded-lg border border-border bg-muted/20 p-6 space-y-3">
                    <div className="text-lg font-semibold">
                      {(active.crime_type || "Report").replace(/_/g, " ")}
                    </div>
                    <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
                      <div className="text-muted-foreground">Report ID</div>
                      <div className="font-mono text-xs">{active.id}</div>
                      <div className="text-muted-foreground">Complaint ID</div>
                      <div className="font-mono text-xs">{active.complaint_id || "—"}</div>
                      <div className="text-muted-foreground">Format</div>
                      <div className="uppercase">{active.format || "pdf"}</div>
                      <div className="text-muted-foreground">Status</div>
                      <div className="capitalize">{active.status || "generated"}</div>
                      <div className="text-muted-foreground">Generated</div>
                      <div>{active.generated_date ? new Date(active.generated_date).toLocaleString() : "—"}</div>
                      <div className="text-muted-foreground">Filename</div>
                      <div className="text-xs break-all">{active.filename}</div>
                    </div>
                    <p className="text-xs text-muted-foreground pt-2 border-t border-border">
                      This panel shows this report's metadata. Click Download to fetch the actual{" "}
                      {(active.format || "pdf").toUpperCase()} file, or Print to open it directly in a
                      new tab.
                    </p>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </AppLayout>
  );
}
