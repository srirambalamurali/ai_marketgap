"use client";

import { Suspense, useEffect, useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useDashboardByReport } from "@/hooks/useDashboard";
import { useReports } from "@/hooks/useReports";
import { useDashboardStore } from "@/store/dashboardStore";
import { formatNumber } from "@/lib/utils";
import { asArray, asNumber, asText } from "@/lib/normalize";
import { Panel, SectionTitle, Skeleton, StatCard } from "@/components/ui";
import type { DashboardChartPoint, DashboardCharts, DashboardMetricsResponse, ReportsListResponse } from "@/types";

const COLORS = ["#4f8cff", "#22c55e", "#f59e0b", "#ef4444", "#a855f7"];

export default function DashboardPage() {
  return (
    <Suspense fallback={<DashboardSkeleton />}>
      <DashboardContent />
    </Suspense>
  );
}

function DashboardContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const reportIdFromUrl = searchParams.get("report_id");
  const queryIdFromUrl = searchParams.get("query_id");
  const scopeFromUrl = searchParams.get("scope") as "latest" | "report" | "query" | "all" | null;

  const { selectedReportId, setSelectedReportId } = useDashboardStore();
  const reportsQuery = useReports();
  const reports = asArray<ReportsListResponse["reports"][number]>((reportsQuery.data as { reports?: unknown } | undefined)?.reports);

  const dashboardQuery = useDashboardByReport(reportIdFromUrl, queryIdFromUrl, scopeFromUrl);
  const metrics: DashboardMetricsResponse | undefined = dashboardQuery.data;
  const selectedAnalysis = metrics?.selected_analysis ?? null;
  const effectiveReportId = reportIdFromUrl ?? metrics?.selected_report_id ?? selectedReportId ?? null;

  useEffect(() => {
    if (effectiveReportId && effectiveReportId !== selectedReportId) {
      setSelectedReportId(effectiveReportId);
    }
    if (!effectiveReportId && selectedReportId) {
      setSelectedReportId(null);
    }
  }, [effectiveReportId, selectedReportId, setSelectedReportId]);

  const selectedReport = useMemo(
    () => reports.find((report) => report.id === effectiveReportId) ?? reports.find((report) => report.id === metrics?.selected_report_id) ?? reports[0] ?? null,
    [reports, effectiveReportId, metrics?.selected_report_id],
  );

  const summary = metrics?.summary ?? {
    total_signals: asNumber(metrics?.total_signals, 0),
    total_documents: asNumber(metrics?.total_documents, 0),
    total_opportunities: asNumber(metrics?.total_opportunities, 0),
    total_evidence_links: asNumber(metrics?.total_documents, 0),
    top_opportunity_score: asNumber(metrics?.top_opportunity_score, 0),
    rag_status: asText(metrics?.rag_status, "unknown"),
    active_sources: [],
  };

  const charts = (metrics?.charts ?? {}) as Partial<DashboardCharts>;
  const signalsOverTime = asArray<DashboardChartPoint>(charts.signals_over_time);
  const sourceDistributionRaw = asArray<DashboardChartPoint>(charts.source_distribution);
  const opportunityScoreDistributionRaw = asArray<DashboardChartPoint>(charts.opportunity_score_distribution);
  const competitionLevelRows = asArray<{ level?: string; count?: number }>(charts.competition_levels);
  const competitionLevelsFallback = [
    { level: "Low", count: 0 },
    { level: "Medium", count: 0 },
    { level: "High", count: 0 },
  ];

  const loading = reportsQuery.isLoading || dashboardQuery.isLoading;
  const selectedAnalysisLabel = selectedAnalysis?.title || selectedReport?.title || "No analysis selected";
  const reportDisplayId = effectiveReportId ? shortId(effectiveReportId) : "Latest";
  const signalStatus = asText(charts.signals_over_time_status?.status, "healthy");
  const isLowActivity = signalStatus === "low_activity" && Number(summary.total_evidence_links ?? 0) <= 0;
  const isSingleBatch = signalStatus === "single_batch" || (signalStatus === "low_activity" && Number(summary.total_evidence_links ?? 0) > 0);
  const signalSeries = signalsOverTime.map((point) => ({
    label: asText(point?.label, ""),
    value: asNumber(point?.count, 0),
  }));
  const sourceDistribution = sourceDistributionRaw.map((point, index) => ({
    label: asText(point?.source ?? point?.label, "Unknown"),
    value: asNumber(point?.count, 0),
    status: asText(point?.status, "SUCCESS"),
    color: COLORS[index % COLORS.length],
  }));
  const scoreDistribution = opportunityScoreDistributionRaw.map((point) => ({
    name: asText(point?.name, "Untitled Opportunity"),
    score: asNumber(point?.score, 0),
  }));
  const competitionLevels = ["Low", "Medium", "High"].map((level) => ({
    level,
    count: asNumber(competitionLevelRows.find((item) => asText(item?.level, "") === level)?.count, competitionLevelsFallback.find((item) => item.level === level)?.count ?? 0),
  }));

  const handleSelectReport = (value: string) => {
    const params = new URLSearchParams(searchParams.toString());
    if (value) {
      params.set("report_id", value);
      params.delete("query_id");
      params.delete("scope");
      setSelectedReportId(value);
    } else {
      params.delete("report_id");
      setSelectedReportId(null);
    }
    const query = params.toString();
    router.push(query ? `${pathname}?${query}` : pathname, { scroll: false });
  };

  if (loading) {
    return <DashboardSkeleton />;
  }

  if (reportsQuery.isError) {
    return <ErrorState message={reportsQuery.error instanceof Error ? reportsQuery.error.message : "Unable to load report list."} />;
  }

  if (dashboardQuery.isError) {
    return <ErrorState message={dashboardQuery.error instanceof Error ? dashboardQuery.error.message : "Unable to load dashboard for selected report."} />;
  }

  if (!metrics || metrics.state === "empty") {
    return (
      <Panel className="rounded-2xl border border-dashed border-white/10 p-8 text-slate-400">
        No dashboard data found for this report.
      </Panel>
    );
  }

  return (
    <div className="space-y-6">
      <Panel className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div className="space-y-1">
          <div className="text-sm uppercase tracking-[0.25em] text-slate-400">Executive Dashboard</div>
          <h2 className="text-2xl font-semibold text-white">Current Active Analysis</h2>
          <p className="max-w-2xl text-sm text-slate-400">
            {metrics.scope === "all"
              ? "Global metrics are shown because All Data was explicitly selected."
              : "Charts and counts are scoped to the selected report only."}
          </p>
        </div>
        <button
          onClick={() => dashboardQuery.refetch()}
          className="rounded-xl bg-accent px-4 py-2 text-sm font-medium text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
        >
          Refresh Metrics
        </button>
      </Panel>

      <Panel className="space-y-4">
        <SectionTitle title="Analysis Selector" subtitle="Choose the active analysis report" />
        <div className="grid gap-4 md:grid-cols-[1fr_auto] md:items-end">
          <div className="space-y-2">
            <label className="text-xs uppercase tracking-[0.2em] text-slate-400">Recent Reports</label>
            <select
              value={effectiveReportId ?? ""}
              onChange={(event) => handleSelectReport(event.target.value)}
              className="w-full rounded-xl border border-white/10 bg-black/20 px-4 py-3 outline-none"
            >
              <option value="">No analysis selected</option>
              {reports.map((report) => (
                <option key={report.id} value={report.id}>
                  {report.query || report.title || "Untitled Report"} · {report.created_at ? new Date(report.created_at).toLocaleDateString() : "Unknown date"} · {shortId(report.id)}
                </option>
              ))}
            </select>
          </div>
          <div className="rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-300">
            <div className="text-xs uppercase tracking-[0.2em] text-slate-500">Current Active Analysis</div>
            <div className="mt-1 font-medium text-white">{selectedAnalysisLabel}</div>
          </div>
        </div>
      </Panel>

      <section className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
        <Panel className="space-y-3">
          <SectionTitle title="Current Analysis" subtitle="Scoped to the selected report" />
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-xl border border-white/10 bg-white/5 px-4 py-3">
              <div className="text-xs uppercase tracking-[0.2em] text-slate-500">Query</div>
              <div className="mt-1 text-white">{selectedAnalysis?.query || selectedReport?.query || "No analysis selected"}</div>
            </div>
            <div className="rounded-xl border border-white/10 bg-white/5 px-4 py-3">
              <div className="text-xs uppercase tracking-[0.2em] text-slate-500">Report</div>
              <div className="mt-1 text-white">{selectedReport?.id ? `${shortId(selectedReport.id)} · ${selectedReport.title || selectedReport.query || "Untitled Report"}` : "No analysis selected"}</div>
            </div>
          </div>
        </Panel>

        <Panel className="space-y-3">
          <SectionTitle title="Recent Reports" subtitle="Latest persisted analyses" />
          <div className="space-y-2">
            {reports.length ? (
              reports.slice(0, 5).map((report) => (
                <button
                  key={report.id}
                  type="button"
                  onClick={() => handleSelectReport(report.id)}
                  className={`w-full rounded-xl border px-4 py-3 text-left transition ${effectiveReportId === report.id ? "border-accent bg-accent/10" : "border-white/10 bg-white/5 hover:bg-white/10"}`}
                >
                  <div className="font-medium text-white">{report.query || report.title || "Untitled Report"}</div>
                  <div className="mt-1 text-xs text-slate-400">
                    {report.created_at ? new Date(report.created_at).toLocaleString() : "Unknown date"} · {shortId(report.id)}
                  </div>
                </button>
              ))
            ) : (
              <div className="rounded-xl border border-dashed border-white/10 p-6 text-slate-400">No analysis generated yet. Go to Opportunities and create your first analysis.</div>
            )}
          </div>
        </Panel>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
        <StatCard label="Total Signals" value={formatNumber(summary.total_signals ?? 0)} hint="Scoped to selected report" />
        <StatCard label="Total Documents" value={formatNumber(summary.total_documents ?? 0)} hint="Evidence linked to the report" />
        <StatCard label="Total Opportunities" value={formatNumber(summary.total_opportunities ?? 0)} hint="Report opportunities only" />
        <StatCard label="Top Opportunity Score" value={String(asNumber(summary.top_opportunity_score, 0) || 0)} hint="Highest report score" />
        <StatCard label="RAG Status" value={asText(summary.rag_status, "unknown")} hint="Vector search health" />
        <StatCard label="Active Sources" value={summary.active_sources.length ? summary.active_sources.join(", ") : "None"} hint="Sources within selected report" />
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        <StatCard label="Embedded Documents" value={formatNumber(asNumber(metrics.embedded_documents, 0))} hint="Vectors stored in ChromaDB" />
        <StatCard label="Last Collection" value={metrics.last_collection_time ? new Date(String(metrics.last_collection_time)).toLocaleString() : "Unknown"} hint="Latest report collection" />
        <StatCard label="Selection" value={`${selectedAnalysisLabel}`} hint={effectiveReportId ? `Report ${shortId(effectiveReportId)}` : "Latest report"} />
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <Panel className="xl:col-span-2">
          <SectionTitle title="Signals Over Time" subtitle="Activity inside the selected report" />
          <div className="h-72">
            {isLowActivity ? (
              <div className="flex h-full items-center justify-center rounded-2xl border border-dashed border-white/10 bg-white/5 p-6 text-center text-slate-400">
                {charts.signals_over_time_status?.message || "Not enough timestamp variation for this selected report."}
              </div>
            ) : isSingleBatch ? (
              <div className="grid h-full gap-3 md:grid-cols-3">
                {signalSeries.map((entry) => (
                  <div key={entry.label} className="flex flex-col justify-between rounded-2xl border border-white/10 bg-white/5 p-4">
                    <div className="text-xs uppercase tracking-[0.2em] text-slate-500">{entry.label}</div>
                    <div className="mt-3 text-3xl font-semibold text-white">{formatNumber(entry.value)}</div>
                    <div className="mt-2 text-sm text-slate-400">Evidence was collected in one analysis batch.</div>
                  </div>
                ))}
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={signalSeries}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.18)" />
                  <XAxis dataKey="label" stroke="#94a3b8" />
                  <YAxis stroke="#94a3b8" />
                  <Tooltip />
                  <Line type="monotone" dataKey="value" stroke="#4f8cff" strokeWidth={2} dot={{ r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        </Panel>

        <Panel>
          <SectionTitle title="Source Distribution" subtitle="Signals by source" />
          <div className="h-72">
            {sourceDistribution.length ? (
              sourceDistribution.some((entry) => entry.value > 0) ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={sourceDistribution} dataKey="value" nameKey="label" innerRadius={52} outerRadius={88}>
                    {sourceDistribution.map((entry, index) => (
                      <Cell key={entry.label || index} fill={entry.color || COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
              ) : (
                <div className="space-y-2 rounded-2xl border border-dashed border-white/10 bg-white/5 p-4">
                  {sourceDistribution.map((entry, index) => (
                    <div key={entry.label || index} className="flex items-center justify-between rounded-xl border border-white/10 bg-black/10 px-4 py-3">
                      <div>
                        <div className="font-medium text-white">{entry.label}</div>
                        <div className="text-xs uppercase tracking-[0.2em] text-slate-500">{entry.status || "SUCCESS"}</div>
                      </div>
                      <div className="text-right">
                        <div className="text-lg font-semibold text-white">{formatNumber(entry.value)}</div>
                        <div className="text-xs text-slate-400">Evidence links</div>
                      </div>
                    </div>
                  ))}
                  {!sourceDistribution.length ? null : (
                    <div className="text-xs text-slate-400">Sources are shown with their live status because the report evidence arrived in a single batch.</div>
                  )}
                </div>
              )
            ) : (
              <div className="flex h-full items-center justify-center rounded-2xl border border-dashed border-white/10 bg-white/5 p-6 text-center text-slate-400">
                No source distribution available for the selected analysis.
              </div>
            )}
          </div>
        </Panel>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <Panel>
          <SectionTitle title="Opportunity Score Distribution" subtitle="Report-specific opportunities only" />
          <div className="h-72">
            {scoreDistribution.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={scoreDistribution}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.18)" />
                  <XAxis dataKey="name" stroke="#94a3b8" interval={0} angle={-18} textAnchor="end" height={60} />
                  <YAxis stroke="#94a3b8" />
                  <Tooltip />
                  <Bar dataKey="score" fill="#4f8cff" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center rounded-2xl border border-dashed border-white/10 bg-white/5 p-6 text-center text-slate-400">
                No opportunity score data for the selected report.
              </div>
            )}
          </div>
        </Panel>

        <Panel>
          <SectionTitle title="Competition Levels" subtitle="Market whitespace snapshot from this report" />
          <div className="space-y-3">
            {competitionLevels.length ? (
              competitionLevels.map((item) => (
                <div key={item.level} className="flex items-center justify-between rounded-xl border border-white/8 bg-white/5 px-4 py-3">
                  <span>{item.level}</span>
                  <span className="text-slate-300">{formatNumber(item.count)}</span>
                </div>
              ))
            ) : (
              <div className="rounded-xl border border-dashed border-white/10 p-6 text-slate-400">No opportunity data yet.</div>
            )}
          </div>
        </Panel>
      </section>
    </div>
  );
}

function shortId(id: string) {
  return id ? id.slice(0, 8) : "";
}

function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
        {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-28" />)}
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        <Skeleton className="h-80" />
        <Skeleton className="h-80" />
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        <Skeleton className="h-80" />
        <Skeleton className="h-80" />
      </div>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-6 text-red-200">{message}</div>;
}

