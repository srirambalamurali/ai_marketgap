"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { Badge, Panel, SectionTitle, Skeleton, StatCard } from "@/components/ui";
import { formatDate, formatNumber } from "@/lib/utils";
import { asArray, asNumber, asText } from "@/lib/normalize";
import { useReportDetail } from "@/hooks/useReportDetail";
import { getWorkflowState } from "@/lib/workflowState";
import type { Signal, SignalsLatestResponse, SignalsSourceResponse, SignalsStatsResponse } from "@/types";

const SOURCES = ["all", "github", "hackernews", "rss", "reddit", "google_trends"];

export default function SignalsClient() {
  const searchParams = useSearchParams();
  const [viewMode, setViewMode] = useState<"current" | "all">("current");
  const [source, setSource] = useState("all");
  const [sort, setSort] = useState<"date" | "score">("date");
  const [queryId, setQueryId] = useState("");
  const [reportId, setReportId] = useState("");
  const [queryDomain, setQueryDomain] = useState("");
  const [workflowState, setWorkflowState] = useState<{ latestQuery?: string; latestReportId?: string | null; latestQueryId?: string | null } | null>(null);
  const [workflowReady, setWorkflowReady] = useState(false);

  const urlQueryId = searchParams.get("query_id")?.trim() ?? "";
  const urlReportId = searchParams.get("report_id")?.trim() ?? "";
  const urlQueryDomain = searchParams.get("query_domain")?.trim() ?? "";

  useEffect(() => {
    if (urlQueryId) setQueryId(urlQueryId);
    if (urlReportId) setReportId(urlReportId);
    if (urlQueryDomain) setQueryDomain(urlQueryDomain);
  }, [urlQueryId, urlReportId, urlQueryDomain]);

  useEffect(() => {
    const state = getWorkflowState();
    console.log("[workflow] loaded", state);
    setWorkflowState(state ? { latestQuery: state.latestQuery, latestReportId: state.latestReportId, latestQueryId: state.latestQueryId } : null);
    setWorkflowReady(true);
    if (state?.latestReportId && !urlReportId) {
      setReportId(state.latestReportId);
    }
    if (state?.latestQueryId && !urlQueryId) {
      setQueryId(state.latestQueryId);
    }
  }, [urlQueryId, urlReportId]);

  const scopeParams = useMemo(() => {
    const trimmedQueryId = urlQueryId || queryId.trim();
    const trimmedReportId = urlReportId || reportId.trim();
    const trimmedQueryDomain = urlQueryDomain || queryDomain.trim();
    return {
      queryId: trimmedQueryId || null,
      reportId: trimmedReportId || null,
      queryDomain: trimmedQueryDomain || null,
    };
  }, [urlQueryId, urlReportId, urlQueryDomain, queryId, reportId, queryDomain]);

  const activeReportId = (viewMode === "current" ? scopeParams.reportId : null) ?? "";
  const hasSelectedReport = viewMode === "all" || Boolean(activeReportId);
  const reportDetail = useReportDetail(activeReportId);

  const latestQueryLabel = workflowState?.latestQuery || "Untitled Report";

  const latest = useQuery<SignalsLatestResponse>({
    queryKey: ["signals", "latest", viewMode, source, scopeParams.queryId, scopeParams.reportId, scopeParams.queryDomain],
    queryFn: () =>
      (viewMode === "all"
        ? api.signals.latest(100) as Promise<SignalsLatestResponse>
        : api.signals.latest(100, scopeParams) as Promise<SignalsLatestResponse>),
    enabled: workflowReady && hasSelectedReport,
    placeholderData: keepPreviousData,
  });
  const stats = useQuery<SignalsStatsResponse>({
    queryKey: ["signals", "stats", viewMode, scopeParams.queryId, scopeParams.reportId, scopeParams.queryDomain],
    queryFn: () =>
      (viewMode === "all"
        ? api.signals.stats() as Promise<SignalsStatsResponse>
        : api.signals.stats(scopeParams) as Promise<SignalsStatsResponse>),
    enabled: workflowReady && hasSelectedReport,
    placeholderData: keepPreviousData,
  });
  const sourceSignals = useQuery<SignalsSourceResponse>({
    queryKey: ["signals", "source", viewMode, source, scopeParams.queryId, scopeParams.reportId, scopeParams.queryDomain],
    queryFn: () =>
      (viewMode === "all"
        ? api.signals.bySource(source, 100) as Promise<SignalsSourceResponse>
        : api.signals.bySource(source, 100, scopeParams) as Promise<SignalsSourceResponse>),
    enabled: workflowReady && hasSelectedReport && source !== "all",
    placeholderData: keepPreviousData,
  });

  const signals = source === "all" ? asArray<Signal>(latest.data?.signals) : asArray<Signal>(sourceSignals.data?.signals);

  const rows = useMemo(() => {
    return [...signals].sort((a, b) => {
      if (sort === "score") return asNumber(b.score, 0) - asNumber(a.score, 0);
      return new Date(String(b.collected_at ?? 0)).getTime() - new Date(String(a.collected_at ?? 0)).getTime();
    });
  }, [signals, sort]);

  if (!workflowReady) return <Skeleton className="h-[60vh]" />;
  if (hasSelectedReport && (latest.isLoading || stats.isLoading)) return <Skeleton className="h-[60vh]" />;
  if (hasSelectedReport && (latest.isError || stats.isError)) {
    const err = latest.error ?? stats.error;
    return <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-6 text-red-200">{err instanceof Error ? err.message : "Failed to load signals"}</div>;
  }

  const effectiveDomain = asText(stats.data?.query_domain ?? scopeParams.queryDomain ?? "", "");
  const effectiveQueryId = asText(stats.data?.query_id ?? scopeParams.queryId ?? "", "");
  const effectiveReportId = asText(stats.data?.report_id ?? scopeParams.reportId ?? "", "");
  const reportTitle = asText(reportDetail.data?.report?.query ?? reportDetail.data?.report?.title ?? "", "");
  const hasScopedReport = Boolean(effectiveReportId);
  const showScopedEvidence = viewMode === "all" || hasScopedReport;

  return (
    <div className="space-y-4">
      <SectionTitle
        title={viewMode === "all" ? "All Signals" : hasScopedReport ? `Signals for selected report: ${reportTitle || latestQueryLabel}` : "Signal Intelligence"}
        subtitle={viewMode === "all" ? "Showing global signals." : hasScopedReport ? "Showing only evidence linked to the selected report." : "Generate an opportunity first to view related live evidence."}
      />

      <Panel className="space-y-4">
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setViewMode("current")}
            className={`rounded-full border px-3 py-1.5 text-sm transition ${
              viewMode === "current" ? "border-accent bg-accent/20 text-white" : "border-white/10 bg-white/5 text-slate-300 hover:bg-white/10"
            }`}
          >
            Current Report
          </button>
          <button
            onClick={() => setViewMode("all")}
            className={`rounded-full border px-3 py-1.5 text-sm transition ${
              viewMode === "all" ? "border-accent bg-accent/20 text-white" : "border-white/10 bg-white/5 text-slate-300 hover:bg-white/10"
            }`}
          >
            All Signals
          </button>
        </div>
        <div className="grid gap-3 md:grid-cols-3">
          <label className="space-y-2">
            <span className="text-xs uppercase tracking-wide text-slate-400">query_id</span>
            <input
              value={queryId}
              onChange={(e) => setQueryId(e.target.value)}
              placeholder="Filter by query_id"
              className="w-full rounded-xl border border-white/10 bg-black/20 px-4 py-3 outline-none"
            />
          </label>
          <label className="space-y-2">
            <span className="text-xs uppercase tracking-wide text-slate-400">report_id</span>
            <input
              value={reportId}
              onChange={(e) => setReportId(e.target.value)}
              placeholder="Filter by report_id"
              className="w-full rounded-xl border border-white/10 bg-black/20 px-4 py-3 outline-none"
            />
          </label>
          <label className="space-y-2">
            <span className="text-xs uppercase tracking-wide text-slate-400">query_domain</span>
            <input
              value={queryDomain}
              onChange={(e) => setQueryDomain(e.target.value)}
              placeholder="fitness, cybersecurity, accounting..."
              className="w-full rounded-xl border border-white/10 bg-black/20 px-4 py-3 outline-none"
            />
          </label>
        </div>
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="flex flex-wrap gap-2">
            {SOURCES.map((item) => (
              <button
                key={item}
                onClick={() => setSource(item)}
                className={`rounded-full border px-3 py-1.5 text-sm transition ${
                  source === item ? "border-accent bg-accent/20 text-white" : "border-white/10 bg-white/5 text-slate-300 hover:bg-white/10"
                }`}
              >
                {item}
              </button>
            ))}
          </div>
          <select value={sort} onChange={(e) => setSort(e.target.value as "date" | "score")} className="rounded-xl border border-white/10 bg-black/20 px-4 py-3 outline-none">
            <option value="date">Sort by Date</option>
            <option value="score">Sort by Score</option>
          </select>
        </div>
        <div className="flex flex-wrap gap-2 text-xs text-slate-400">
          <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">Scope: {viewMode === "all" ? "global" : effectiveDomain || "current report"}</span>
          <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">Query: {effectiveQueryId || "n/a"}</span>
          <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">Report: {effectiveReportId || "n/a"}</span>
        </div>
      </Panel>

      {showScopedEvidence ? (
        <>
          <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
            <StatCard label="Total Signals" value={formatNumber(stats.data?.total ?? 0)} />
            <StatCard label="Top Score" value={formatNumber(stats.data?.top_score ?? 0)} />
            <StatCard label="Sources" value={formatNumber(Object.keys(stats.data?.by_source ?? {}).length)} />
            <StatCard label="Signal Days" value={formatNumber(Object.keys(stats.data?.by_day ?? {}).length)} />
            <StatCard label="Query Domain" value={effectiveDomain || "Not set"} />
          </section>

          <div className="grid gap-4 xl:grid-cols-2">
            {rows.length ? rows.map((row) => {
          const status = asText(row.status, "unknown");
          const statusClass = status === "accepted" ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-200" : "border-rose-500/30 bg-rose-500/10 text-rose-200";
          return (
            <Panel key={row.id} className="space-y-4">
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-2">
                  <div className="text-base font-semibold text-white">{asText(row.title, "Untitled signal")}</div>
                  <div className="text-xs text-slate-400">{asText(row.content, "No description available.")}</div>
                  <a
                    href={asText(row.url, "") || "#"}
                    target="_blank"
                    rel="noreferrer"
                    className="block text-xs text-cyan-300 underline decoration-cyan-300/40 underline-offset-2"
                  >
                    {asText(row.url, "No URL available")}
                  </a>
                </div>
                <Badge className={statusClass}>{status}</Badge>
              </div>
              <div className="flex flex-wrap gap-2 text-xs">
                <Badge>{asText(row.source, "unknown")}</Badge>
                <Badge>{asText(row.source_type, "unknown")}</Badge>
                <Badge>{asText(row.query_domain, effectiveDomain || "general")}</Badge>
                <Badge>{asText(row.rejection_reason, "no_rejection")}</Badge>
              </div>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <div className="rounded-xl border border-white/10 bg-black/20 p-3">
                  <div className="text-xs uppercase tracking-wide text-slate-400">Score</div>
                  <div className="mt-1 text-lg font-semibold text-white">{formatNumber(asNumber(row.score, 0))}</div>
                </div>
                <div className="rounded-xl border border-white/10 bg-black/20 p-3">
                  <div className="text-xs uppercase tracking-wide text-slate-400">Relevance</div>
                  <div className="mt-1 text-lg font-semibold text-white">{formatNumber(asNumber(row.query_relevance_score, 0))}</div>
                </div>
                <div className="rounded-xl border border-white/10 bg-black/20 p-3">
                  <div className="text-xs uppercase tracking-wide text-slate-400">Domain Relevance</div>
                  <div className="mt-1 text-lg font-semibold text-white">{formatNumber(asNumber(row.domain_relevance_score, 0))}</div>
                </div>
                <div className="rounded-xl border border-white/10 bg-black/20 p-3">
                  <div className="text-xs uppercase tracking-wide text-slate-400">Timestamp</div>
                  <div className="mt-1 text-sm font-medium text-white">{formatDate(row.collected_at ?? null)}</div>
                </div>
              </div>
              <div className="rounded-xl border border-white/10 bg-black/10 p-3 text-xs text-slate-300">
                {asText(row.content, "No snippet available.")}
              </div>
            </Panel>
          );
        }) : (
          <Panel>
            <div className="px-3 py-10 text-center text-slate-400">No signals found for this report.</div>
          </Panel>
        )}
          </div>
        </>
      ) : (
        <Panel>
          <div className="px-3 py-10 text-center text-slate-400">Generate an opportunity first to view related live evidence.</div>
        </Panel>
      )}
    </div>
  );
}
