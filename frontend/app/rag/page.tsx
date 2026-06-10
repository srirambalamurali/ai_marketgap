"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/services/api";
import { Badge, Panel, SectionTitle, Skeleton } from "@/components/ui";
import { asArray, asNumber, asText, asDateText } from "@/lib/normalize";
import { DEFAULT_WORKFLOW_QUERY, getWorkflowState, type WorkflowState } from "@/lib/workflowState";

type RagSearchResponse = {
  success: boolean;
  query?: string | null;
  error?: string | null;
  answer?: string | null;
  results?: Array<{
    content: string;
    score: number;
    source?: string | null;
    url?: string | null;
    timestamp?: string | null;
    collected_at?: string | null;
    metadata?: {
      source?: string;
      source_type?: string;
      url?: string;
      collected_at?: string;
      [key: string]: unknown;
    };
  }>;
};

type RagSearchResult = NonNullable<RagSearchResponse["results"]>[number];
type RagSearchInput = {
  query: string;
  reportId?: string | null;
  queryId?: string | null;
};

export default function RagPage() {
  const [workflowState, setWorkflowState] = useState<WorkflowState | null>(null);
  const [workflowReady, setWorkflowReady] = useState(false);
  const [query, setQuery] = useState("");
  const autoSearchedRef = useRef(false);
  const workflowStateRef = useRef<WorkflowState | null>(null);
  const { mutate, data, error, isPending, isError } = useMutation<RagSearchResponse, Error, RagSearchInput>({
    mutationFn: (payload: RagSearchInput) =>
      api.rag.search(payload.query, 8, {
        reportId: payload.reportId ?? null,
        queryId: payload.queryId ?? null,
      }) as Promise<RagSearchResponse>,
  });
  const runSearch = useCallback(
    (payload: RagSearchInput) => {
      mutate(payload);
    },
    [mutate],
  );
  const isRagFailed = data?.success === false;
  const ragErrorMessage =
    data?.error ||
    (data?.success === false ? "Vector search unavailable. Start ChromaDB on port 8001." : "");

  useEffect(() => {
    const state = getWorkflowState();
    console.log("[workflow] loaded", state);
    workflowStateRef.current = state;
    setWorkflowState(state);
    setWorkflowReady(true);

    if (!state) {
      setQuery("");
      return;
    }

    setQuery(state.latestQuery || DEFAULT_WORKFLOW_QUERY);
  }, []);

  useEffect(() => {
    if (!workflowReady) {
      return;
    }

    const state = workflowStateRef.current;
    if (!state?.latestQuery) {
      return;
    }
    if (autoSearchedRef.current) {
      return;
    }

    autoSearchedRef.current = true;
    runSearch({
      query: state.latestQuery,
      reportId: state.latestReportId,
      queryId: state.latestQueryId,
    });
  }, [workflowReady, runSearch]);

  const handleSearch = () => {
    autoSearchedRef.current = true;
    runSearch({
      query,
      reportId: workflowState?.latestReportId ?? null,
      queryId: workflowState?.latestQueryId ?? null,
    });
  };

  return (
    <div className="space-y-4">
      <SectionTitle title="RAG Intelligence Search" subtitle="Ask for evidence-backed market context" />
      {!workflowReady ? <Skeleton className="h-28" /> : null}
      {workflowReady && !workflowState ? (
        <Panel>
          <div className="text-slate-400">Generate an opportunity first to ask evidence-backed questions.</div>
        </Panel>
      ) : null}
      <Panel className="space-y-3">
        <textarea value={query} onChange={(e) => setQuery(e.target.value)} className="min-h-28 w-full rounded-xl border border-white/10 bg-black/20 p-4 outline-none" />
        <button onClick={handleSearch} className="rounded-xl bg-accent px-4 py-2 text-white">
          Search
        </button>
      </Panel>

      {isPending ? <Skeleton className="h-64" /> : null}
      {isError ? <ErrorCard message={error instanceof Error ? error.message : "RAG search failed"} /> : null}
      {isRagFailed ? (
        <ErrorCard message={ragErrorMessage || "Vector search unavailable. Start ChromaDB on port 8001."} />
      ) : data ? (
        <RagResults data={data as any} />
      ) : workflowState ? (
        <Panel><div className="text-slate-400">Run a query to see answer, evidence, and sources.</div></Panel>
      ) : (
        <Panel><div className="text-slate-400">Generate an opportunity first to ask evidence-backed questions.</div></Panel>
      )}
    </div>
  );
}

function RagResults({ data }: { data: RagSearchResponse }) {
  const results = asArray<RagSearchResult>(data.results);
  const answer = asText(data.answer ?? results[0]?.content, "No evidence indexed yet. Generate opportunities first.");
  return (
    <div className="grid gap-4">
      <Panel className="space-y-3">
        <div className="text-sm uppercase tracking-[0.2em] text-slate-400">Answer</div>
        <div className="text-lg text-white">{answer}</div>
        {results.length ? <div className="text-xs text-slate-500">{results.length} evidence citation(s) attached below.</div> : null}
      </Panel>
      <div className="grid gap-4 xl:grid-cols-2">
        {results.length ? results.map((result: any, index: number) => (
          <Panel key={index} className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <Badge>{asText(result?.source ?? result?.metadata?.source, "unknown")}</Badge>
              <span className="text-sm text-slate-400">Score {asNumber(result?.score, 0).toFixed(3)}</span>
            </div>
            <div className="text-sm text-slate-300">{asText(result?.content, "No evidence content available.")}</div>
              <div className="space-y-1 rounded-xl border border-white/10 bg-black/20 p-3 text-xs text-slate-400">
                <div><span className="text-slate-200">Source:</span> {asText(result?.source ?? result?.metadata?.source, "n/a")}</div>
                <div><span className="text-slate-200">URL:</span> {asText(result?.url ?? result?.metadata?.url, "n/a")}</div>
                <div><span className="text-slate-200">Collection Timestamp:</span> {asDateText(result?.collected_at ?? result?.timestamp ?? result?.metadata?.collected_at, "n/a")}</div>
              </div>
            </Panel>
          )) : <Panel><div className="text-slate-400">No evidence found for this search.</div></Panel>}
      </div>
    </div>
  );
}

function ErrorCard({ message }: { message: string }) {
  return <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-6 text-red-200">{message}</div>;
}
