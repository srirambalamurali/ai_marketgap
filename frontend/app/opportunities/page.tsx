"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useOpportunityStore } from "@/store/opportunityStore";
import { useOpportunities, useOpportunitiesByQuery } from "@/hooks/useOpportunities";
import { api } from "@/services/api";
import { Badge, Panel, SectionTitle, Skeleton } from "@/components/ui";
import { asArray, asNumber, asText } from "@/lib/normalize";
import { formatNumber } from "@/lib/utils";
import {
  clearWorkflowState,
  DEFAULT_WORKFLOW_QUERY,
  getWorkflowState,
  saveWorkflowState,
} from "@/lib/workflowState";

type GeneratedOpportunity = {
  id?: string;
  query_id?: string | null;
  name?: string;
  startup_name?: string;
  problem?: string;
  market_gap?: string;
  solution?: string;
  target_user?: string;
  target_customers?: string;
  sources?: unknown;
  competition_level?: string;
  opportunity_score?: number;
  market_score?: number;
  confidence_score?: number;
  demand_score?: number;
  competition_score?: number;
  query_relevance_score?: number;
  evidence_count?: number;
  evidence?: { signals?: unknown[] };
  created_at?: string | null;
};

type GenerationResult = {
  success: boolean;
  query?: string;
  query_id?: string | null;
  duration_ms?: number;
  collection_duration_ms?: number;
  run_source?: string;
  source_statuses?: Array<{
    source: string;
    status: string;
    duration_ms?: number;
    signals_collected?: number;
  }>;
  opportunities_count?: number;
  evidence_links_count?: number;
  signals_collected?: number;
  signals_accepted?: number;
  signals_rejected?: number;
  report_id?: string | null;
  opportunities?: GeneratedOpportunity[];
  message?: string;
  status?: string;
  errors?: string[];
  debug?: Record<string, unknown>;
};

type OpportunityCard = {
  id: string;
  queryId?: string | null;
  name: string;
  problem: string;
  marketGap: string;
  solution: string;
  targetUser: string;
  sources: string[];
  competitionLevel: string;
  opportunityScore: number | null;
  marketScore: number | null;
  confidenceScore: number | null;
  demandScore: number | null;
  competitionScore: number | null;
  queryRelevanceScore: number | null;
  evidenceCount: number | null;
  createdAt?: string | null;
};

type WorkflowSnapshot = {
  latestQuery: string;
  latestReportId: string | null;
  latestQueryId: string | null;
  latestGeneratedOpportunities: OpportunityCard[];
  latestEvidenceCount: number;
  latestSourceStatuses: GenerationResult["source_statuses"];
};

export default function OpportunitiesPage() {
  const queryClient = useQueryClient();
  const { query, setQuery, sort, setSort } = useOpportunityStore();
  const [generationQuery, setGenerationQuery] = useState("");
  const [generatedResults, setGeneratedResults] = useState<OpportunityCard[]>([]);
  const [latestReportId, setLatestReportId] = useState<string | null>(null);
  const [latestQueryId, setLatestQueryId] = useState<string | null>(null);
  const [generationMeta, setGenerationMeta] = useState<GenerationResult | null>(null);
  const [workflowReady, setWorkflowReady] = useState(false);

  useEffect(() => {
    const restoreFromWorkflowState = () => {
      const state = getWorkflowState();
      if (state) {
        setGenerationQuery(state.latestQuery || DEFAULT_WORKFLOW_QUERY);
        setGeneratedResults(dedupeOpportunities(normalizeOpportunities(state.latestGeneratedOpportunities ?? [], state.latestQueryId ?? undefined)));
        setLatestReportId(state.latestReportId);
        setLatestQueryId(state.latestQueryId);
        setGenerationMeta({
          success: true,
          query: state.latestQuery || DEFAULT_WORKFLOW_QUERY,
          query_id: state.latestQueryId,
          report_id: state.latestReportId,
          opportunities_count: state.latestGeneratedOpportunities.length,
          evidence_links_count: state.latestEvidenceCount,
          source_statuses: state.latestSourceStatuses,
          run_source: "LIVE",
        });
      } else {
        setGenerationQuery(DEFAULT_WORKFLOW_QUERY);
        setGeneratedResults([]);
        setLatestReportId(null);
        setLatestQueryId(null);
        setGenerationMeta(null);
      }
      setWorkflowReady(true);
    };

    restoreFromWorkflowState();

    const handlePageShow = (event: PageTransitionEvent) => {
      if (event.persisted) {
        restoreFromWorkflowState();
      }
    };

    window.addEventListener("pageshow", handlePageShow);
    return () => {
      window.removeEventListener("pageshow", handlePageShow);
    };
  }, []);

  const savedQueryId = generationMeta?.query_id ?? latestQueryId ?? undefined;
  const savedQuery = useOpportunitiesByQuery(100, savedQueryId);
  const fallbackSaved = useOpportunities(100);
  const savedSource = workflowReady ? (savedQueryId ? savedQuery : fallbackSaved) : ({ isLoading: true } as typeof fallbackSaved);

  const generateMutation = useMutation({
    mutationFn: async (submittedQuery: string) => {
      return api.opportunities.run(submittedQuery) as Promise<GenerationResult>;
    },
    onSuccess: async (result, submittedQuery) => {
      setGenerationMeta(result);
      const normalized = dedupeOpportunities(normalizeOpportunities(result.opportunities ?? [], result.query_id ?? undefined));
      setGeneratedResults(normalized);
      setGenerationQuery(result.query || submittedQuery);
      setLatestReportId(result.report_id ?? null);
      setLatestQueryId(result.query_id ?? null);
      saveWorkflowState({
        latestQuery: submittedQuery,
        latestReportId: result.report_id ?? null,
        latestQueryId: result.query_id ?? null,
        latestGeneratedOpportunities: normalized as Array<Record<string, unknown>>,
        latestEvidenceCount: result.evidence_links_count ?? result.signals_accepted ?? 0,
        latestSourceStatuses: asArray(result.source_statuses).map((item: any) => ({
          source: asText(item?.source, "unknown"),
          status: asText(item?.status, "unknown"),
          duration_ms: asNumber(item?.duration_ms, 0),
          signals_collected: asNumber(item?.signals_collected, 0),
        })),
        updatedAt: new Date().toISOString(),
      });
      if (result.debug && process.env.NODE_ENV !== "production") {
        console.debug("Opportunity generation debug:", result.debug);
      }
      await queryClient.invalidateQueries({ queryKey: ["opportunities"] });
      await queryClient.invalidateQueries({ queryKey: ["reports"] });
      await queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      await queryClient.invalidateQueries({ queryKey: ["signals"] });
    },
  });

  const handleReset = () => {
    clearWorkflowState();
    setGenerationQuery(DEFAULT_WORKFLOW_QUERY);
    setGeneratedResults([]);
    setLatestReportId(null);
    setLatestQueryId(null);
    setGenerationMeta(null);
    void queryClient.invalidateQueries({ queryKey: ["opportunities"] });
    void queryClient.invalidateQueries({ queryKey: ["reports"] });
    void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    void queryClient.invalidateQueries({ queryKey: ["signals"] });
  };

  const savedOpportunities = useMemo(() => {
    const rows = normalizeOpportunities(savedSource.data?.opportunities ?? [], savedQueryId);
    return dedupeOpportunities(rows);
  }, [savedSource.data?.opportunities, savedQueryId]);

  const filteredSaved = useMemo(() => {
    return savedOpportunities
      .filter((o) => `${o.name} ${o.problem} ${o.marketGap} ${o.solution} ${o.targetUser}`.toLowerCase().includes(query.toLowerCase()))
      .sort((a, b) => {
        const confidenceA = a.confidenceScore ?? 0;
        const confidenceB = b.confidenceScore ?? 0;
        const opportunityA = a.opportunityScore ?? 0;
        const opportunityB = b.opportunityScore ?? 0;
        if (sort === "confidence") return confidenceB - confidenceA;
        if (sort === "recent") return new Date(b.createdAt ?? 0).getTime() - new Date(a.createdAt ?? 0).getTime();
        return opportunityB - opportunityA;
      });
  }, [savedOpportunities, query, sort]);

  const generatedQueryLabel = generationMeta?.query || generationQuery;
  const hasGeneratedResults = generatedResults.length > 0;
  const opportunitiesCount = generationMeta?.opportunities_count ?? generatedResults.length;
  const evidenceCount = generationMeta?.evidence_links_count ?? 0;
  const signalsAccepted = generationMeta?.signals_accepted ?? 0;
  const hasEvidenceOrOpportunities = opportunitiesCount > 0 || evidenceCount > 0;
  const generationStatus = hasEvidenceOrOpportunities || signalsAccepted > 0 ? "SUCCESS" : "NO_EVIDENCE";
  const generationMessage = generationStatus === "SUCCESS"
    ? "Live generation complete"
    : "No evidence found";
  const runSource = generationMeta?.run_source || "LIVE";

  return (
    <div className="space-y-4">
      <SectionTitle title="Opportunity Explorer" subtitle="Live opportunities from the intelligence engine" />

      <Panel className="space-y-4">
        <div className="grid gap-3 md:grid-cols-[1fr_auto_auto]">
          <input
            value={generationQuery}
            onChange={(e) => setGenerationQuery(e.target.value)}
            placeholder="Describe the market gap you want to explore..."
            className="w-full rounded-xl border border-white/10 bg-black/20 px-4 py-3 outline-none"
          />
          <button
            onClick={() => generateMutation.mutate(generationQuery)}
            disabled={generateMutation.isPending}
            className="rounded-xl bg-accent px-4 py-3 text-sm font-medium text-white disabled:opacity-60"
          >
            {generateMutation.isPending ? "Generating..." : "Generate Opportunity"}
          </button>
          <button
            onClick={handleReset}
            type="button"
            className="rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm font-medium text-slate-200 transition hover:bg-white/10"
          >
            Reset
          </button>
        </div>
        <div className="text-sm text-slate-400">This runs the backend generation flow and refreshes the live data store.</div>
        {generateMutation.isPending ? <ProgressState /> : null}
        {generationMeta ? (
          <div className="space-y-4 rounded-2xl border border-white/10 bg-white/5 p-4">
            <div className="flex flex-wrap items-center gap-3">
              <Badge className={generationStatus === "SUCCESS" ? "bg-emerald-500/15 text-emerald-200" : "bg-amber-500/15 text-amber-200"}>
                {generationStatus}
              </Badge>
              <Badge className="bg-sky-500/15 text-sky-200">Source: {runSource}</Badge>
              <span className="text-sm text-slate-300">{generationMessage}</span>
            </div>
            <div className="grid gap-3 md:grid-cols-4">
              <Metric label="Duration" value={`${Math.round((generationMeta.duration_ms ?? 0) / 1000)}s`} />
              <Metric label="Opportunities" value={formatNumber(opportunitiesCount)} />
              <Metric label="Evidence" value={formatNumber(evidenceCount)} />
              <Metric
                label="Evidence"
                value={
                  generationMeta.report_id ? (
                    <Link href={`/signals?report_id=${generationMeta.report_id}`} className="text-accent underline">
                      View Evidence
                    </Link>
                  ) : (
                    "Pending"
                  )
                }
              />
            </div>
            <div className="flex flex-wrap gap-2">
              {asArray(generationMeta.source_statuses).map((item: any) => (
                <Badge key={`${item.source}-${item.status}`} className={badgeClass(String(item.status))}>
                  {item.source}: {item.status}
                </Badge>
              ))}
            </div>
          </div>
        ) : null}
      </Panel>

      <Panel className="space-y-3">
        <SectionTitle title={`Generated Results for: ${generatedQueryLabel}`} subtitle="Only opportunities returned from the current generate response are shown here." />
        {hasGeneratedResults ? (
          <div className="grid gap-4 xl:grid-cols-2">
            {generatedResults.map((op: OpportunityCard) => (
              <OpportunityCardView
                key={op.id}
                opportunity={op}
                workflowSnapshot={buildWorkflowSnapshot({
                  query: generationMeta?.query || generationQuery,
                  reportId: latestReportId,
                  queryId: latestQueryId,
                  opportunities: generatedResults,
                  evidenceCount,
                  sourceStatuses: asArray(generationMeta?.source_statuses),
                })}
              />
            ))}
          </div>
        ) : (
          <div className="rounded-2xl border border-dashed border-white/10 p-8 text-slate-400">
            {hasEvidenceOrOpportunities ? "Evidence collected but no opportunities were returned after validation." : "No evidence found"}
          </div>
        )}
      </Panel>

      <Panel className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search saved opportunities..."
          className="w-full rounded-xl border border-white/10 bg-black/20 px-4 py-3 outline-none md:max-w-md"
        />
        <select value={sort} onChange={(e) => setSort(e.target.value as any)} className="rounded-xl border border-white/10 bg-black/20 px-4 py-3 outline-none">
          <option value="score">Sort by Score</option>
          <option value="confidence">Sort by Confidence</option>
          <option value="recent">Sort by Recent</option>
        </select>
      </Panel>

      <Panel className="space-y-3">
        <SectionTitle title="Saved Opportunities" subtitle="Historical opportunities stored in the database and separated from the current generated result." />
        {savedSource.isLoading ? (
          <div className="rounded-2xl border border-dashed border-white/10 p-8 text-slate-400">Loading saved opportunities...</div>
        ) : savedSource.isError ? (
          <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-6 text-red-200">
            {savedSource.error instanceof Error ? savedSource.error.message : "Failed to load opportunities"}
          </div>
        ) : (
          <div className="grid gap-4 xl:grid-cols-2">
            {filteredSaved.length ? (
              filteredSaved.map((op: OpportunityCard) => (
                <OpportunityCardView
                  key={`saved-${op.id}`}
                  opportunity={op}
                  workflowSnapshot={buildWorkflowSnapshot({
                    query: generationMeta?.query || generationQuery,
                    reportId: latestReportId,
                    queryId: latestQueryId,
                    opportunities: generatedResults,
                    evidenceCount,
                    sourceStatuses: asArray(generationMeta?.source_statuses),
                  })}
                />
              ))
            ) : (
              <div className="rounded-2xl border border-dashed border-white/10 p-8 text-slate-400 xl:col-span-2">
                No saved opportunities match the selected filters.
              </div>
            )}
          </div>
        )}
      </Panel>
    </div>
  );
}

function OpportunityCardView({ opportunity, workflowSnapshot }: { opportunity: OpportunityCard; workflowSnapshot?: WorkflowSnapshot | null }) {
  const persistWorkflowState = () => {
    if (!workflowSnapshot) {
      return;
    }

    saveWorkflowState({
      latestQuery: workflowSnapshot.latestQuery,
      latestReportId: workflowSnapshot.latestReportId,
      latestQueryId: workflowSnapshot.latestQueryId,
      latestGeneratedOpportunities: workflowSnapshot.latestGeneratedOpportunities as Array<Record<string, unknown>>,
      latestEvidenceCount: workflowSnapshot.latestEvidenceCount,
      latestSourceStatuses: (workflowSnapshot.latestSourceStatuses ?? []).map((item) => ({
        source: item?.source ?? "unknown",
        status: item?.status ?? "unknown",
        duration_ms: asNumber(item?.duration_ms, 0),
        signals_collected: asNumber(item?.signals_collected, 0),
      })),
      updatedAt: new Date().toISOString(),
    });
  };

  return (
    <Panel className="flex h-full flex-col justify-between">
      <div className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-xl font-semibold">{opportunity.name}</h3>
        <Badge>{opportunity.competitionLevel || "Not calculated"}</Badge>
        </div>
        <p className="text-sm text-slate-300">{opportunity.problem}</p>
        <p className="text-sm text-slate-400">{opportunity.marketGap}</p>
        <div className="text-xs uppercase tracking-[0.2em] text-slate-500">{opportunity.targetUser}</div>
        <div className="flex flex-wrap gap-2">
          {opportunity.sources.length ? (
            opportunity.sources.map((source) => (
              <Badge key={`${opportunity.id}-${source}`} className="bg-white/5 text-slate-300">
                {source}
              </Badge>
            ))
          ) : (
            <Badge className="bg-white/5 text-slate-300">unknown</Badge>
          )}
        </div>
      </div>
      <div className="mt-6 grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
        <Metric label="Opportunity" value={formatScore(opportunity.opportunityScore)} />
        <Metric label="Demand" value={formatScore(opportunity.demandScore)} />
        <Metric label="Competition" value={formatScore(opportunity.competitionScore)} />
        <Metric label="Query Relevance" value={formatScore(opportunity.queryRelevanceScore)} />
        <Metric label="Evidence" value={formatScore(opportunity.evidenceCount)} />
        <Metric label="Target User" value={opportunity.targetUser} />
      </div>
      <div className="mt-5 flex gap-3">
        <Link
          href={`/opportunities/${opportunity.id}`}
          onClick={persistWorkflowState}
          className="rounded-xl bg-accent px-4 py-2 text-sm font-medium text-white"
        >
          View Details
        </Link>
        <Link
          href={`/opportunities/${opportunity.id}#evidence`}
          onClick={persistWorkflowState}
          className="rounded-xl border border-white/10 px-4 py-2 text-sm text-slate-200"
        >
          View Evidence
        </Link>
      </div>
    </Panel>
  );
}

function Metric({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-3">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-400">{label}</div>
      <div className="mt-1 font-semibold">{value}</div>
    </div>
  );
}

function formatScore(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return "Not calculated";
  }
  const num = Number(value);
  return Number.isFinite(num) ? num.toFixed(1) : "Not calculated";
}

function optionalNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
}

function normalizeOpportunities(items: unknown[], queryId?: string | null): OpportunityCard[] {
  return items
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
    .map((op, index) => {
      const sources = asArray<unknown>(op.sources)
        .map((source) => asText(source, "unknown"))
        .filter((source) => source !== "unknown");
      const evidenceSignals = asArray<unknown>((op.evidence as { signals?: unknown } | undefined)?.signals);
      const evidenceSources = asArray<unknown>((op.evidence as { sources?: unknown } | undefined)?.sources);
      const name = asText(op.name || op.startup_name, "Untitled Opportunity");
      const problem = asText(op.problem || op.problemStatement, "Problem not specified");
      const marketGap = asText(op.market_gap || op.marketGap || op.problem || op.problemStatement, "Market gap not specified");
      const solution = asText(op.solution || op.solutionText, "Solution not specified");
      const targetUser = asText(op.target_user || op.targetUser || op.target_customers, "Target user not specified");
      return {
        id: asText(op.id, `op-${index}`),
        queryId: asText(op.query_id ?? op.queryId ?? queryId ?? "", ""),
        name,
        problem,
        marketGap,
        solution,
        targetUser,
        sources: sources.length ? sources : dedupeStrings(evidenceSources.map((source) => asText(source, "unknown"))),
        competitionLevel: asText(op.competition_level || op.competitionLevel, "Not calculated"),
        opportunityScore: optionalNumber(op.opportunity_score ?? op.opportunityScore ?? op.score ?? op.market_score ?? op.marketScore),
        marketScore: optionalNumber(op.market_score ?? op.marketScore ?? op.score),
        confidenceScore: optionalNumber(op.confidence_score ?? op.confidenceScore),
        demandScore: optionalNumber(op.demand_score ?? op.demandScore),
        competitionScore: optionalNumber(op.competition_score ?? op.competitionScore),
        queryRelevanceScore: optionalNumber(op.query_relevance_score ?? op.queryRelevanceScore),
        evidenceCount: optionalNumber(op.evidence_count ?? op.evidenceCount ?? evidenceSignals.length),
        createdAt: op.created_at ? String(op.created_at) : op.createdAt ? String(op.createdAt) : null,
      };
    });
}

function dedupeOpportunities(items: OpportunityCard[]) {
  const seen = new Set<string>();
  const output: OpportunityCard[] = [];

  for (const item of items) {
    const key = buildOpportunityKey(item);
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    output.push(item);
  }

  return output;
}

function buildOpportunityKey(item: OpportunityCard) {
  const normalizedName = normalizeKey(item.name);
  const normalizedProblem = normalizeKey(item.problem);
  const queryId = normalizeKey(item.queryId ?? "");
  if (normalizedName && queryId) {
    return `name-query:${normalizedName}:${queryId}`;
  }
  return `name-problem:${normalizedName}:${normalizedProblem}`;
}

function normalizeKey(value: string) {
  return value.toLowerCase().replace(/\s+/g, " ").trim();
}

function dedupeStrings(values: string[]) {
  return [...new Set(values.filter(Boolean))];
}

function buildWorkflowSnapshot({
  query,
  reportId,
  queryId,
  opportunities,
  evidenceCount,
  sourceStatuses,
}: {
  query: string;
  reportId: string | null;
  queryId: string | null;
  opportunities: OpportunityCard[];
  evidenceCount: number;
  sourceStatuses: GenerationResult["source_statuses"];
}): WorkflowSnapshot {
  return {
    latestQuery: query,
    latestReportId: reportId,
    latestQueryId: queryId,
    latestGeneratedOpportunities: opportunities,
    latestEvidenceCount: evidenceCount,
    latestSourceStatuses: sourceStatuses ?? [],
  };
}

function ProgressState() {
  const steps = ["Collecting Sources", "Building Knowledge Base", "Running Agents", "Generating Report"];
  return (
    <div className="grid gap-2 md:grid-cols-4">
      {steps.map((step, index) => (
        <div key={step} className="rounded-xl border border-white/10 bg-black/20 p-3 text-sm text-slate-300">
          <div className="text-xs uppercase tracking-[0.2em] text-slate-500">Step {index + 1}</div>
          <div className="mt-1 font-medium">{step}</div>
        </div>
      ))}
    </div>
  );
}

function badgeClass(status: string) {
  if (status === "SUCCESS") return "bg-emerald-500/15 text-emerald-200";
  if (status === "TIMEOUT") return "bg-amber-500/15 text-amber-200";
  if (status === "CONFIG_BLOCKED") return "bg-orange-500/15 text-orange-200";
  return "bg-red-500/15 text-red-200";
}
