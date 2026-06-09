"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import type { ReportDetailResponse } from "@/types";

export function useReportDetail(id: string) {
  return useQuery({
    queryKey: ["reports", id],
    queryFn: () => api.reports.get(id) as Promise<ReportDetailResponse>,
    enabled: Boolean(id),
    placeholderData: keepPreviousData,
  });
}
