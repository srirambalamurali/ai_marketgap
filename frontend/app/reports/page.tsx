"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useReports } from "@/hooks/useReports";
import { useReportDetail } from "@/hooks/useReportDetail";
import { Panel, SectionTitle, Skeleton } from "@/components/ui";
import type { ReportsListResponse } from "@/types";
import { asArray, asNumber, asText } from "@/lib/normalize";
import { getWorkflowState, type WorkflowState } from "@/lib/workflowState";

export default function ReportsPage() {
  const [workflowState, setWorkflowState] = useState<WorkflowState | null>(null);
  const [workflowReady, setWorkflowReady] = useState(false);
  const { data, isLoading, isError, error } = useReports();
  const latestReportId = workflowState?.latestReportId ?? "";
  const latestReportDetail = useReportDetail(latestReportId);

  useEffect(() => {
    const state = getWorkflowState();
    console.log("[workflow] loaded", state);
    setWorkflowState(state);
    setWorkflowReady(true);
  }, []);

  if (isLoading) return <Skeleton className="h-[50vh]" />;
  if (isError) return <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-6 text-red-200">{error instanceof Error ? error.message : "Failed to load reports"}</div>;
  const reports = asArray<ReportsListResponse["reports"][number]>((data as ReportsListResponse | undefined)?.reports);
  return (
    <div className="space-y-4">
      <SectionTitle title="Reports Center" subtitle="Generated intelligence reports from the backend report store" />
      {workflowReady && latestReportId ? (
        <Panel className="space-y-3">
          <div className="text-xs uppercase tracking-[0.2em] text-slate-400">Latest Report In This Session</div>
          {latestReportDetail.isLoading ? (
            <div className="text-slate-400">Loading latest report...</div>
          ) : latestReportDetail.isError ? (
            <div className="text-slate-400">Latest report could not be loaded.</div>
          ) : latestReportDetail.data?.report ? (
            <div className="space-y-3">
              <div className="text-lg font-semibold text-white">{asText(latestReportDetail.data.report.title || latestReportDetail.data.report.query, "Latest Report")}</div>
              <div className="text-sm text-slate-400">{asText(latestReportDetail.data.report.query, "No query available.")}</div>
              <Link href={`/reports/${latestReportId}`} className="inline-flex rounded-xl bg-accent px-4 py-2 text-sm font-medium text-white">
                Open Latest Report
              </Link>
            </div>
          ) : (
            <div className="text-slate-400">No latest report saved in this session.</div>
          )}
        </Panel>
      ) : null}
      <div className="grid gap-4 xl:grid-cols-2">
        {reports.length ? reports.map((report) => (
          <Panel key={report.id}>
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-lg font-semibold">{asText(report.title || report.query, "Untitled Report")}</div>
                <div className="mt-1 text-sm text-slate-400">{report.created_at ? new Date(report.created_at).toLocaleString() : "Unknown date"}</div>
                <div className="mt-1 text-xs text-slate-500">Confidence: {asNumber(report.market_confidence_score, 0)}</div>
              </div>
              <Link href={`/reports/${report.id}`} className="rounded-xl bg-accent px-4 py-2 text-sm font-medium text-white">View</Link>
            </div>
          </Panel>
        )) : <Panel><div className="text-slate-400">No generated reports yet. Run a generation flow from Opportunities to create one.</div></Panel>}
      </div>
    </div>
  );
}
