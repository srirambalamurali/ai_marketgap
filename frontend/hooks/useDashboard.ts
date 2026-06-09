"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import type { DashboardMetricsResponse } from "@/types";

type DashboardScope = "latest" | "report" | "query" | "all";

export function useDashboard(params?: { reportId?: string | null; queryId?: string | null; scope?: DashboardScope | null }) {
  return useQuery({
    queryKey: ["dashboard", params?.scope ?? "latest", params?.reportId ?? null, params?.queryId ?? null],
    queryFn: () =>
      api.dashboard.metrics({
        reportId: params?.reportId ?? null,
        queryId: params?.queryId ?? null,
        scope: params?.scope ?? null,
      }) as Promise<DashboardMetricsResponse>,
  });
}

export function useDashboardByReport(reportId?: string | null, queryId?: string | null, scope?: DashboardScope | null) {
  return useQuery({
    queryKey: ["dashboard", scope ?? "latest", reportId ?? null, queryId ?? null],
    queryFn: () =>
      api.dashboard.metrics({
        reportId: reportId ?? null,
        queryId: queryId ?? null,
        scope: scope ?? null,
      }) as Promise<DashboardMetricsResponse>,
  });
}
