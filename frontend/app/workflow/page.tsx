"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { Panel, SectionTitle, Skeleton, StatCard } from "@/components/ui";
import { formatNumber } from "@/lib/utils";
import { asNumber, asText } from "@/lib/normalize";

export default function WorkflowPage() {
  const workflowHealth = useQuery({
    queryKey: ["workflow", "health"],
    queryFn: () => api.workflow.monitor(),
    placeholderData: keepPreviousData,
  });
  const dashboard = useQuery({
    queryKey: ["workflow", "dashboard"],
    queryFn: () => api.dashboard.metrics() as Promise<any>,
    placeholderData: keepPreviousData,
  });
  if (workflowHealth.isLoading || dashboard.isLoading) return <Skeleton className="h-[60vh]" />;
  if (workflowHealth.isError || dashboard.isError) {
    const err = workflowHealth.error ?? dashboard.error;
    return <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-6 text-red-200">{err instanceof Error ? err.message : "Workflow load failed"}</div>;
  }
  const health = (workflowHealth.data as any) ?? {};
  const metrics = (dashboard.data as any) ?? {};
  return (
    <div className="space-y-4">
      <SectionTitle title="Workflow Monitor" subtitle="LangGraph execution overview and scheduler health" />
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Health" value={asText(health.status, "unknown")} hint="Pipeline health summary" />
        <StatCard label="Success Rate" value={formatNumber(Math.round(asNumber(health.success_rate, 0) * 100)) + "%"} hint="Monitoring overview" />
        <StatCard label="Tracked Signals" value={formatNumber(metrics.total_signals ?? 0)} hint="Live database count" />
        <StatCard label="Active Alerts" value={formatNumber(asNumber(health.active_alerts, 0))} hint="Failed collection alerts" />
      </section>
      <Panel className="space-y-3">
        <div className="text-sm uppercase tracking-[0.2em] text-slate-400">Workflow Snapshot</div>
        <div className="grid gap-3 md:grid-cols-2">
          <Info label="Ingestion rate/min" value={asNumber(health.ingestion_rate_per_min, 0)} />
          <Info label="Total signals" value={asNumber(health.total_signals ?? metrics.total_signals, 0)} />
          <Info label="Source coverage" value={Object.keys(metrics.by_source ?? {}).length} />
          <Info label="Last refresh" value={metrics.generated_at ? new Date(String(metrics.generated_at)).toLocaleString() : "unknown"} />
        </div>
      </Panel>
      <Panel>
        <div className="text-sm text-slate-400">Workflow is driven by the same live PostgreSQL-backed signal store used everywhere else.</div>
      </Panel>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-4">
      <div className="text-xs uppercase tracking-[0.2em] text-slate-400">{label}</div>
      <div className="mt-1 text-base font-semibold text-white">{value}</div>
    </div>
  );
}
