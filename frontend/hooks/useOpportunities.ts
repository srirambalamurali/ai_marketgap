"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import type { Opportunity } from "@/types";

type ApiListResponse = { opportunities: Opportunity[] };
type ApiSingleResponse = { opportunity: Opportunity };
type ApiEvidenceResponse = { evidence: Array<Record<string, unknown>> };
type ApiTopResponse = { top: Opportunity[] };

export function useOpportunities(limit = 50) {
  return useQuery({
    queryKey: ["opportunities", limit],
    queryFn: () => api.opportunities.list(limit) as Promise<ApiListResponse>,
    placeholderData: keepPreviousData,
  });
}

export function useOpportunitiesByQuery(limit = 50, queryId?: string) {
  return useQuery({
    queryKey: ["opportunities", limit, queryId ?? "all"],
    queryFn: () => api.opportunities.list(limit, queryId) as Promise<ApiListResponse>,
    placeholderData: keepPreviousData,
  });
}

export function useTopOpportunities(limit = 10) {
  return useQuery({
    queryKey: ["opportunities", "top", limit],
    queryFn: () => api.opportunities.top(limit) as Promise<ApiTopResponse>,
    placeholderData: keepPreviousData,
  });
}

export function useOpportunity(id: string) {
  return useQuery({
    queryKey: ["opportunities", id],
    queryFn: () => api.opportunities.detail(id) as Promise<ApiSingleResponse>,
    enabled: !!id,
    placeholderData: keepPreviousData,
  });
}

export function useOpportunityEvidence(id: string) {
  return useQuery({
    queryKey: ["opportunities", id, "evidence"],
    queryFn: () => api.opportunities.evidence(id) as Promise<ApiEvidenceResponse>,
    enabled: !!id,
    placeholderData: keepPreviousData,
  });
}
