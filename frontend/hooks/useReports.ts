"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";

export function useReports() {
  return useQuery({
    queryKey: ["reports"],
    queryFn: api.reports.list,
    placeholderData: keepPreviousData,
  });
}
