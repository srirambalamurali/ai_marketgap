"use client";

import Link from "next/link";
import { useReports } from "@/hooks/useReports";
import { Panel, SectionTitle, Skeleton } from "@/components/ui";
import type { ReportsListResponse } from "@/types";
import { asArray, asNumber, asText } from "@/lib/normalize";

export default function ReportsPage() {
  const { data, isLoading, isError, error } = useReports();
  if (isLoading) return <Skeleton className="h-[50vh]" />;
  if (isError) return <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-6 text-red-200">{error instanceof Error ? error.message : "Failed to load reports"}</div>;
  const reports = asArray<ReportsListResponse["reports"][number]>((data as ReportsListResponse | undefined)?.reports);
  return (
    <div className="space-y-4">
      <SectionTitle title="Reports Center" subtitle="Generated intelligence reports from the backend report store" />
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
