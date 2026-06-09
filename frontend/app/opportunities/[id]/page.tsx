"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useOpportunity, useOpportunityEvidence } from "@/hooks/useOpportunities";
import { Badge, Panel, SectionTitle, Skeleton } from "@/components/ui";
import { formatDate } from "@/lib/utils";
import { asArray, asNumber, asText } from "@/lib/normalize";

export default function OpportunityDetailPage() {
  const params = useParams<{ id: string }>();
  const opportunityId = Array.isArray(params?.id) ? params.id[0] : params?.id ?? "";
  const { data, isLoading, isError, error } = useOpportunity(opportunityId);
  const evidence = useOpportunityEvidence(opportunityId);
  const opportunity = data?.opportunity;

  if (isLoading || evidence.isLoading) return <Skeleton className="h-[60vh]" />;

  if (isError || !opportunity) {
    return (
      <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-6 text-red-100">
        <h2 className="text-xl font-semibold">Opportunity not found.</h2>
        <p className="mt-2 text-sm text-red-200/80">
          {error instanceof Error ? error.message : "The selected opportunity could not be loaded."}
        </p>
      </div>
    );
  }

  const evidenceItems = asArray<any>(evidence.data?.evidence);
  const title = asText(opportunity.startup_name || opportunity.name, "Untitled Opportunity");
  const problem = asText(opportunity.problem, "Problem not available.");
  const solution = asText(opportunity.solution, "Solution not available.");
  const competitionLevel = asText(opportunity.competition_level, "unknown");
  const targetCustomers = asText(opportunity.target_customers || opportunity.target_user, "Not specified");
  const revenueModel = asText(opportunity.revenue_model, "Not specified");
  const goToMarket = asText(opportunity.go_to_market, "Not specified");
  const explanation = opportunity.explanation ?? {};
  const reportId = asText(opportunity.report_id, "");

  return (
    <div className="space-y-5">
      <Panel>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-2">
            <SectionTitle title={title} subtitle={problem} />
            <p className="max-w-4xl text-slate-300">{solution}</p>
          </div>
          <Badge>{competitionLevel}</Badge>
        </div>
        {reportId ? (
          <Link href={`/reports/${reportId}`} className="mt-4 inline-flex rounded-xl border border-white/10 px-4 py-2 text-sm text-slate-200 hover:bg-white/5">
            Open Report
          </Link>
        ) : null}
      </Panel>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {[
          ["Score", asNumber(opportunity.market_score, 0)],
          ["Confidence", asNumber(opportunity.confidence_score, 0)],
          ["Demand", asNumber(opportunity.demand_score, 0)],
          ["Evidence", asArray(opportunity.evidence?.signals).length],
        ].map(([label, value]) => (
          <Panel key={String(label)}>
            <div className="text-xs uppercase tracking-[0.25em] text-slate-400">{label}</div>
            <div className="mt-2 text-3xl font-semibold">{String(value)}</div>
          </Panel>
        ))}
      </div>

      <Panel className="scroll-mt-24">
        <SectionTitle title="Evidence Sources" subtitle="Live supporting signals" />
        <div className="space-y-3">
          {evidenceItems.length ? (
            evidenceItems.map((item: any) => {
              const url = asText(item?.url, "");
              return (
                <div key={String(item?.signal_id ?? url ?? item?.title ?? "evidence")} className="rounded-xl border border-white/8 bg-white/5 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-medium">{asText(item?.title, "Untitled evidence")}</div>
                    <Badge>{asText(item?.source, "unknown")}</Badge>
                  </div>
                  <div className="mt-2 text-sm text-slate-400">
                    {asText(item?.source_type, "unknown")} · {formatDate(item?.collected_at ?? null)}
                  </div>
                  {url ? (
                    <a href={url} className="mt-2 inline-block text-sm text-accent hover:underline" target="_blank" rel="noreferrer">
                      Open source
                    </a>
                  ) : (
                    <div className="mt-2 text-sm text-slate-500">Source URL unavailable.</div>
                  )}
                </div>
              );
            })
          ) : (
            <div className="rounded-xl border border-dashed border-white/10 p-6 text-slate-400">No evidence available yet.</div>
          )}
        </div>
      </Panel>

      <Panel>
        <SectionTitle title="Explainability" />
        <div className="space-y-3 text-sm text-slate-300">
          <p>
            <strong>Why this opportunity exists:</strong> {asText(explanation.why_this_opportunity_exists, "Not available.")}
          </p>
          <p>
            <strong>Why demand is growing:</strong> {asText(explanation.why_demand_is_growing, "Not available.")}
          </p>
          <p>
            <strong>Target customers:</strong> {targetCustomers}
          </p>
          <p>
            <strong>Revenue model:</strong> {revenueModel}
          </p>
          <p>
            <strong>Go-to-market:</strong> {goToMarket}
          </p>
        </div>
      </Panel>
    </div>
  );
}
