"use client";

import { useMemo, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { Badge, Panel, SectionTitle, Skeleton, StatCard } from "@/components/ui";
import { formatDate, formatNumber } from "@/lib/utils";
import { asArray, asNumber, asText } from "@/lib/normalize";
import type { Signal, SignalsLatestResponse, SignalsSourceResponse, SignalsStatsResponse } from "@/types";

const SOURCES = ["all", "github", "hackernews", "rss", "reddit", "google_trends"];

export default function SignalsPage() {
  const [source, setSource] = useState("all");
  const [sort, setSort] = useState<"date" | "score">("date");
  const latest = useQuery<SignalsLatestResponse>({
    queryKey: ["signals", "latest", source],
    queryFn: () => api.signals.latest(100) as Promise<SignalsLatestResponse>,
    placeholderData: keepPreviousData,
  });
  const stats = useQuery<SignalsStatsResponse>({
    queryKey: ["signals", "stats"],
    queryFn: () => api.signals.stats() as Promise<SignalsStatsResponse>,
    placeholderData: keepPreviousData,
  });
  const sourceSignals = useQuery<SignalsSourceResponse>({
    queryKey: ["signals", "source", source],
    queryFn: () => api.signals.bySource(source) as Promise<SignalsSourceResponse>,
    enabled: source !== "all",
    placeholderData: keepPreviousData,
  });

  const rows = useMemo(() => {
    const sourceRows = source === "all" ? asArray<Signal>(latest.data?.signals) : asArray<Signal>(sourceSignals.data?.signals);
    return [...sourceRows].sort((a, b) => {
      if (sort === "score") return asNumber(b.score, 0) - asNumber(a.score, 0);
      return new Date(String(b.collected_at ?? 0)).getTime() - new Date(String(a.collected_at ?? 0)).getTime();
    });
  }, [latest.data?.signals, sourceSignals.data?.signals, source, sort]);

  if (latest.isLoading || stats.isLoading) return <Skeleton className="h-[60vh]" />;
  if (latest.isError || stats.isError) {
    const err = latest.error ?? stats.error;
    return <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-6 text-red-200">{err instanceof Error ? err.message : "Failed to load signals"}</div>;
  }

  return (
    <div className="space-y-4">
      <SectionTitle title="Signal Intelligence" subtitle="Live market signals from the backend" />
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <StatCard label="Total Signals" value={formatNumber(stats.data?.total ?? 0)} />
        <StatCard label="Top Score" value={formatNumber(stats.data?.top_score ?? 0)} />
        <StatCard label="Sources" value={formatNumber(Object.keys(stats.data?.by_source ?? {}).length)} />
        <StatCard label="Signal Days" value={formatNumber(Object.keys(stats.data?.by_day ?? {}).length)} />
        <StatCard label="Source Type" value={source === "all" ? "All" : asText(source, "All")} />
      </section>

      <Panel className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
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
      </Panel>

      <Panel>
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="text-slate-400">
              <tr>
                <th className="px-3 py-2">Title</th>
                <th className="px-3 py-2">Source</th>
                <th className="px-3 py-2">Score</th>
                <th className="px-3 py-2">Timestamp</th>
                <th className="px-3 py-2">Signal Type</th>
              </tr>
            </thead>
            <tbody>
              {rows.length ? rows.map((row) => (
                <tr key={row.id} className="border-t border-white/8">
                  <td className="max-w-[480px] px-3 py-3">
                    <div className="font-medium text-white">{asText(row.title, "Untitled signal")}</div>
                    <div className="mt-1 line-clamp-2 text-xs text-slate-400">{asText(row.content, "No description available.")}</div>
                  </td>
                  <td className="px-3 py-3"><Badge>{asText(row.source, "unknown")}</Badge></td>
                  <td className="px-3 py-3">{formatNumber(asNumber(row.score, 0))}</td>
                  <td className="px-3 py-3">{formatDate(row.collected_at ?? null)}</td>
                  <td className="px-3 py-3">{asText(row.source_type, "unknown")}</td>
                </tr>
              )) : (
                <tr>
                  <td colSpan={5} className="px-3 py-10 text-center text-slate-400">No signals available for the selected filter.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
