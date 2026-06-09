"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/services/api";
import { Badge, Panel, SectionTitle, Skeleton } from "@/components/ui";
import { asArray, asNumber, asText, asDateText } from "@/lib/normalize";

type RagSearchResponse = {
  success: boolean;
  query?: string | null;
  error?: string | null;
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

export default function RagPage() {
  const [query, setQuery] = useState("Find startup opportunities in Amazon seller tools");
  const mutation = useMutation<RagSearchResponse, Error, string>({ mutationFn: (q: string) => api.rag.search(q, 8) as Promise<RagSearchResponse> });
  const isRagFailed = mutation.data?.success === false;
  const ragErrorMessage =
    mutation.data?.error ||
    (mutation.data?.success === false ? "Vector search unavailable. Start ChromaDB on port 8001." : "");

  return (
    <div className="space-y-4">
      <SectionTitle title="RAG Intelligence Search" subtitle="Ask for evidence-backed market context" />
      <Panel className="space-y-3">
        <textarea value={query} onChange={(e) => setQuery(e.target.value)} className="min-h-28 w-full rounded-xl border border-white/10 bg-black/20 p-4 outline-none" />
        <button onClick={() => mutation.mutate(query)} className="rounded-xl bg-accent px-4 py-2 text-white">
          Search
        </button>
      </Panel>

      {mutation.isPending ? <Skeleton className="h-64" /> : null}
      {mutation.isError ? <ErrorCard message={mutation.error instanceof Error ? mutation.error.message : "RAG search failed"} /> : null}
      {isRagFailed ? (
        <ErrorCard message={ragErrorMessage || "Vector search unavailable. Start ChromaDB on port 8001."} />
      ) : mutation.data ? (
        <RagResults data={mutation.data as any} />
      ) : (
        <Panel><div className="text-slate-400">Run a query to see answer, evidence, and sources.</div></Panel>
      )}
    </div>
  );
}

function RagResults({ data }: { data: RagSearchResponse }) {
  const results = asArray<RagSearchResult>(data.results);
  const answer = asText(results[0]?.content, "No answer returned.");
  return (
    <div className="grid gap-4">
      <Panel className="space-y-3">
        <div className="text-sm uppercase tracking-[0.2em] text-slate-400">Answer</div>
        <div className="text-lg text-white">{answer}</div>
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
