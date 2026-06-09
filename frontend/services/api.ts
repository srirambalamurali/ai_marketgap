const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  let res: Response;
  try {
    res = await fetch(url, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
      cache: "no-store",
    });
  } catch (error) {
    const detail =
      process.env.NODE_ENV === "development"
        ? `Failed to fetch ${url}. Check backend CORS, API base URL, and server availability.`
        : "Failed to connect to the backend API.";
    throw new Error(detail);
  }

  if (!res.ok) {
    const text = await res.text();
    try {
      const parsed = text ? JSON.parse(text) : null;
      const message = parsed?.detail || parsed?.message || parsed?.error || text;
      throw new Error(message || `Request failed: ${res.status} for ${url}`);
    } catch {
      throw new Error(text || `Request failed: ${res.status} for ${url}`);
    }
  }

  return res.json() as Promise<T>;
}

export const api = {
  dashboard: {
    metrics: (params?: { reportId?: string | null; queryId?: string | null; scope?: string | null }) => {
      const search = new URLSearchParams();
      if (params?.reportId) search.set("report_id", params.reportId);
      if (params?.queryId) search.set("query_id", params.queryId);
      if (params?.scope) search.set("scope", params.scope);
      const suffix = search.toString() ? `?${search.toString()}` : "";
      return request(`/dashboard${suffix}`);
    },
  },
  opportunities: {
    list: (limit = 50, queryId?: string) => request(`/opportunities?limit=${limit}${queryId ? `&query_id=${encodeURIComponent(queryId)}` : ""}`),
    top: (limit = 10, queryId?: string) => request(`/opportunities/top?limit=${limit}${queryId ? `&query_id=${encodeURIComponent(queryId)}` : ""}`),
    detail: (id: string) => request(`/opportunities/${id}`),
    evidence: (id: string) => request(`/opportunities/${id}/evidence`),
    run: (query = "AI startup productivity gaps") => request("/opportunities/generate", { method: "POST", body: JSON.stringify({ query }) }),
  },
  workflow: {
    run: (query: string) => request("/workflow/run", { method: "POST", body: JSON.stringify({ query }) }),
    monitor: () => request("/workflow"),
  },
  rag: {
    search: (query: string, top_k = 8) => request("/rag/search", { method: "POST", body: JSON.stringify({ query, top_k }) }),
    health: () => request("/rag/health"),
  },
  reports: {
    list: () => request("/reports"),
    get: (id: string) => request(`/reports/${id}`),
  },
  signals: {
    collect: (query: string) => request("/collect/signals", { method: "POST", body: JSON.stringify({ query }) }),
    github: () => request("/collect/signals/github", { method: "POST" }),
    reddit: () => request("/collect/reddit", { method: "POST" }),
    googleTrends: () => request("/collect/google-trends", { method: "POST" }),
    rss: () => request("/collect/rss", { method: "POST" }),
    hackerNews: () => request("/collect/hackernews", { method: "POST" }),
    status: () => request("/collect/status"),
    latest: (limit = 25) => request(`/signals/latest?limit=${limit}`),
    stats: () => request("/signals/stats"),
    bySource: (source: string, limit = 50) => request(`/signals/source/${source}?limit=${limit}`),
  },
};

export { API_BASE };
