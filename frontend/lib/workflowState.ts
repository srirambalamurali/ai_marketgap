"use client";

export const WORKFLOW_STATE_KEY = "ai_market_gap_workflow_state";
export const DEFAULT_WORKFLOW_QUERY = "Find opportunities in Amazon seller tools";

export type WorkflowSourceStatus = {
  source: string;
  status: string;
  duration_ms?: number;
  signals_collected?: number;
};

export type WorkflowState = {
  latestQuery: string;
  latestReportId: string | null;
  latestQueryId: string | null;
  latestGeneratedOpportunities: Array<Record<string, unknown>>;
  latestEvidenceCount: number;
  latestSourceStatuses: WorkflowSourceStatus[];
  updatedAt: string;
};

function isBrowser() {
  return typeof window !== "undefined" && typeof window.sessionStorage !== "undefined";
}

function normalizeWorkflowState(state: Partial<WorkflowState> | null | undefined): WorkflowState | null {
  if (!state || typeof state !== "object") {
    return null;
  }

  const latestQuery = typeof state.latestQuery === "string" ? state.latestQuery.trim() : "";
  const latestReportId = typeof state.latestReportId === "string" && state.latestReportId.trim() ? state.latestReportId.trim() : null;
  const latestQueryId = typeof state.latestQueryId === "string" && state.latestQueryId.trim() ? state.latestQueryId.trim() : null;
  const latestGeneratedOpportunities = Array.isArray(state.latestGeneratedOpportunities)
    ? state.latestGeneratedOpportunities.filter((item) => Boolean(item) && typeof item === "object") as Array<Record<string, unknown>>
    : [];
  const latestEvidenceCount = Number.isFinite(Number(state.latestEvidenceCount)) ? Number(state.latestEvidenceCount) : 0;
  const latestSourceStatuses = Array.isArray(state.latestSourceStatuses)
    ? state.latestSourceStatuses.filter(
        (item): item is WorkflowSourceStatus => Boolean(item) && typeof item === "object" && typeof (item as WorkflowSourceStatus).source === "string",
      )
    : [];
  const updatedAt = typeof state.updatedAt === "string" && state.updatedAt.trim() ? state.updatedAt.trim() : new Date().toISOString();

  if (!latestQuery && !latestReportId && !latestQueryId && !latestGeneratedOpportunities.length && !latestEvidenceCount && !latestSourceStatuses.length) {
    return null;
  }

  return {
    latestQuery,
    latestReportId,
    latestQueryId,
    latestGeneratedOpportunities,
    latestEvidenceCount,
    latestSourceStatuses,
    updatedAt,
  };
}

export function getWorkflowState(): WorkflowState | null {
  if (!isBrowser()) {
    return null;
  }

  try {
    const raw = window.sessionStorage.getItem(WORKFLOW_STATE_KEY);
    if (!raw) {
      return null;
    }

    const parsed = JSON.parse(raw) as Partial<WorkflowState> | null;
    const state = normalizeWorkflowState(parsed);
    if (process.env.NODE_ENV !== "production") {
      console.log("[workflow] loaded", state);
    }
    return state;
  } catch (error) {
    if (process.env.NODE_ENV !== "production") {
      console.log("[workflow] load failed", error);
    }
    return null;
  }
}

export function saveWorkflowState(state: WorkflowState) {
  if (!isBrowser()) {
    return state;
  }

  const normalized = normalizeWorkflowState(state);
  if (!normalized) {
    return state;
  }

  if (process.env.NODE_ENV !== "production") {
    console.log("[workflow] saving", normalized);
  }

  window.sessionStorage.setItem(WORKFLOW_STATE_KEY, JSON.stringify(normalized));
  return normalized;
}

export function mergeWorkflowState(partialState: Partial<WorkflowState>) {
  const current = getWorkflowState();
  const merged = normalizeWorkflowState({
    latestQuery: partialState.latestQuery ?? current?.latestQuery ?? "",
    latestReportId: partialState.latestReportId ?? current?.latestReportId ?? null,
    latestQueryId: partialState.latestQueryId ?? current?.latestQueryId ?? null,
    latestGeneratedOpportunities: partialState.latestGeneratedOpportunities ?? current?.latestGeneratedOpportunities ?? [],
    latestEvidenceCount: partialState.latestEvidenceCount ?? current?.latestEvidenceCount ?? 0,
    latestSourceStatuses: partialState.latestSourceStatuses ?? current?.latestSourceStatuses ?? [],
    updatedAt: partialState.updatedAt ?? current?.updatedAt ?? new Date().toISOString(),
  });

  if (merged) {
    saveWorkflowState(merged);
  }

  return merged;
}

export function clearWorkflowState() {
  if (!isBrowser()) {
    return;
  }

  if (process.env.NODE_ENV !== "production") {
    console.log("[workflow] clearing");
  }
  window.sessionStorage.removeItem(WORKFLOW_STATE_KEY);
}
