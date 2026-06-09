"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";

export function useSignals() {
  return useQuery({
    queryKey: ["signals", "status"],
    queryFn: api.signals.status,
    placeholderData: keepPreviousData,
  });
}
