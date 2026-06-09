"use client";

import { useReportDetail } from "@/hooks/useReportDetail";
import { Badge, Panel, SectionTitle, Skeleton } from "@/components/ui";
import { asArray, asNumber, asText } from "@/lib/normalize";

export default function ReportDetailClient({ id }: { id: string }) {
  const { data, isLoading, isError, error } = useReportDetail(id);
  const report = (data?.report ?? null) as any;
  const topOpps = asArray<any>(report?.top_opportunities);
  const evidenceLinks = extractEvidenceLinks(topOpps);
  const reportTitle = asText(report?.title || report?.query, "Report");

  if (isLoading) return <Skeleton className="h-[60vh]" />;
  if (isError) return <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-6 text-red-200">{error instanceof Error ? error.message : "Failed to load report"}</div>;
  if (!data?.success || !report) return <Panel><div className="text-slate-400">Report not found.</div></Panel>;

  return (
    <div className="space-y-4">
      <SectionTitle title={reportTitle} subtitle="Readable report from the live intelligence engine" />
      <Panel className="space-y-4">
        <SectionBlock title="Executive Summary" value={describeExecutiveSummary(report?.executive_summary)} />
        <SectionBlock title="Pain Points" value={formatBullets(report?.top_pain_points)} />
        <SectionBlock title="Market Gaps" value={formatBullets(report?.top_market_gaps)} />
        <SectionBlock title="Top Opportunities" value={formatOpportunities(topOpps)} />
        <SectionBlock title="Scores" value={formatScores(topOpps)} />
        <SectionBlock title="Evidence Links" value={formatEvidence(evidenceLinks)} />
      </Panel>
    </div>
  );
}

function SectionBlock({ title, value }: { title: string; value: string }) {
  return (
    <div className="space-y-2">
      <div className="text-sm uppercase tracking-[0.2em] text-slate-400">{title}</div>
      <div className="whitespace-pre-wrap rounded-xl border border-white/10 bg-black/20 p-4 text-slate-200">{value || "No data available."}</div>
    </div>
  );
}

function formatBullets(items: any[] = []) {
  const safeItems = asArray<any>(items);
  if (!safeItems.length) return "No entries.";
  return safeItems
    .map((item) => `- ${asText(item?.title, "Untitled")}: ${asText(item?.description, "No description.")}`)
    .join("\n");
}

function formatOpportunities(items: any[] = []) {
  const safeItems = asArray<any>(items);
  if (!safeItems.length) return "No opportunities available.";
  return safeItems
    .map((item) => {
      const title = asText(item?.opportunity?.title ?? item?.startup_name ?? item?.name, "Untitled");
      const description = asText(item?.opportunity?.description ?? item?.problem ?? item?.market_gap, "");
      return `- ${title} (${asNumber(item?.overall_score ?? item?.opportunity_score, 0)}/100): ${description}`;
    })
    .join("\n");
}

function formatScores(items: any[] = []) {
  const safeItems = asArray<any>(items);
  if (!safeItems.length) return "No scoring data.";
  return safeItems
    .map((item) => {
      const title = asText(item?.opportunity?.title ?? item?.startup_name ?? item?.name, "Untitled");
      return `- ${title}: ${asNumber(item?.overall_score ?? item?.opportunity_score, 0)}/100, confidence ${asNumber(item?.opportunity?.confidence_score ?? item?.confidence_score, 0)}`;
    })
    .join("\n");
}

function formatEvidence(items: { title: string; url: string; source: string }[] = []) {
  const safeItems = asArray<{ title?: string; url?: string; source?: string }>(items);
  if (!safeItems.length) return "No evidence links.";
  return safeItems
    .map((item) => `- [${asText(item?.source, "unknown")}] ${asText(item?.title, "Untitled")}\n  ${asText(item?.url, "n/a")}`)
    .join("\n");
}

function extractEvidenceLinks(topOpps: any[] = []) {
  const urls = new Map<string, { title: string; url: string; source: string }>();
  for (const opp of asArray<any>(topOpps)) {
    const signals = asArray<any>(opp?.opportunity?.evidence?.signals);
    for (const signal of signals) {
      if (signal?.url && !urls.has(signal.url)) {
        urls.set(signal.url, {
          title: asText(signal.title, "Evidence"),
          url: asText(signal.url, ""),
          source: asText(signal.source, "unknown"),
        });
      }
    }
  }
  return [...urls.values()];
}

function describeExecutiveSummary(value: unknown) {
  if (!value) return "No executive summary available.";
  if (typeof value === "string") return value || "No executive summary available.";
  if (Array.isArray(value)) {
    return value
      .map((item) => `- ${asText(item?.title, "Untitled")}: ${asText(item?.description, "No description.")}`)
      .join("\n");
  }
  if (typeof value === "object") {
    const summary = value as Record<string, unknown>;
    return Object.entries(summary)
      .map(([key, item]) => {
        if (Array.isArray(item)) {
          return `- ${key}: ${item.map((entry) => asText(entry, "item")).join(", ")}`;
        }
        if (item && typeof item === "object") {
          const nested = item as Record<string, unknown>;
          const label = asText(nested.title ?? nested.name ?? nested.label, "details");
          const description = asText(nested.description ?? nested.summary ?? nested.value, "");
          return `- ${key}: ${description ? `${label} - ${description}` : label}`;
        }
        return `- ${key}: ${asText(item, "Unavailable")}`;
      })
      .join("\n");
  }
  return String(value);
}
