export type Opportunity = {
  id: string;
  query_id?: string | null;
  report_id?: string | null;
  startup_name: string;
  name?: string;
  problem: string;
  market_gap?: string;
  solution: string;
  market_score: number;
  opportunity_score?: number;
  confidence_score: number;
  evidence_score?: number;
  demand_score: number;
  pain_score: number;
  growth_score: number;
  competition_score: number;
  whitespace_score?: number;
  feasibility_score: number;
  query_relevance_score?: number;
  competition_level: "Low" | "Medium" | "High" | "Unknown" | string;
  emergence_date?: string | null;
  last_signal_at?: string | null;
  signal_growth_30d: number;
  trend_acceleration: number;
  market_momentum: number;
  sources?: string[];
  target_user?: string;
  evidence: {
    signals: Array<{
      source: string;
      signal_id: string;
      title: string;
      url: string;
      collected_at?: string | null;
      source_type: string;
    }>;
    sources: string[];
  };
  explanation: {
    why_this_opportunity_exists: string;
    which_signals_created_it: Array<Record<string, unknown>>;
    why_demand_is_growing: string;
  };
  target_customers: string;
  revenue_model: string;
  mvp_features: { items: string[] };
  go_to_market: string;
  created_at?: string | null;
};

export type Signal = {
  id: string;
  query_id?: string | null;
  query_domain?: string | null;
  source: string;
  source_type: string;
  source_id: string;
  title: string;
  content: string;
  url: string;
  author: string;
  score: number;
  comments_count: number;
  credibility_score: number;
  query_relevance_score?: number;
  domain_relevance_score?: number;
  status?: "accepted" | "rejected" | string;
  accepted_status?: "accepted" | "rejected" | string;
  rejection_reason?: string | null;
  created_at?: string | null;
  collected_at?: string | null;
  extra_metadata: Record<string, unknown>;
};

export type DashboardMetrics = Record<string, unknown> & {
  total_signals?: number;
  opportunity_summary?: {
    total_opportunities: number;
    top_opportunities?: Array<{ id: string; startup_name: string; market_score?: number; opportunity_score?: number; confidence_score?: number; competition_level?: string; evidence_count?: number; demand_score?: number; competition_score?: number; query_relevance_score?: number }>;
    by_competition_level: Record<string, number>;
  };
};

export type DashboardSummary = {
  total_signals: number;
  total_documents: number;
  total_opportunities: number;
  total_evidence_links: number;
  top_opportunity_score: number;
  rag_status: string;
  active_sources: string[];
  run_source?: string;
};

export type DashboardChartPoint = {
  label?: string;
  count?: number;
  source?: string;
  name?: string;
  score?: number;
  level?: "Low" | "Medium" | "High" | string;
  status?: string;
  message?: string;
};

export type DashboardCharts = {
  signals_over_time: DashboardChartPoint[];
  signals_over_time_status?: {
    status?: "healthy" | "low_activity" | "empty" | string;
    message?: string;
  };
  source_distribution: DashboardChartPoint[];
  opportunity_score_distribution: DashboardChartPoint[];
  competition_levels: Array<{ level: "Low" | "Medium" | "High"; count: number }>;
};

export type DashboardMetricsResponse = DashboardMetrics & {
  scope?: "latest" | "report" | "query" | "all" | string;
  analysis_selected?: boolean;
  state?: "empty" | "success" | "error";
  message?: string;
  selected_report_id?: string | null;
  selected_query_id?: string | null;
  selected_query?: string | null;
  selected_analysis?: {
    id?: string;
    report_id?: string;
    title?: string;
    query?: string;
    query_id?: string | null;
    created_at?: string | null;
    market_confidence_score?: number;
    run_source?: string;
    source_statuses?: Array<Record<string, unknown>>;
    evidence_links?: Array<Record<string, unknown>>;
    top_opportunities?: Array<Record<string, unknown>>;
    top_pain_points?: Array<Record<string, unknown>>;
    top_market_gaps?: Array<Record<string, unknown>>;
    top_trends?: Array<Record<string, unknown>>;
    rag_status?: Record<string, unknown>;
    metadata?: Record<string, unknown>;
  } | null;
  recent_reports?: Array<{
    id: string;
    title?: string;
    query?: string;
    query_id?: string | null;
    created_at?: string | null;
    market_confidence_score?: number;
  }>;
  total_documents?: number;
  total_opportunities?: number;
  top_opportunity_score?: number;
  run_source?: string;
  last_collection_time?: string | null;
  rag_status?: string;
  chromadb_connected?: boolean;
  collection_exists?: boolean;
  embedded_documents?: number;
  opportunity_summary?: DashboardMetrics["opportunity_summary"];
  source_distribution?: {
    labels: string[];
    values: number[];
  };
  signal_velocity?: {
    last_hour: number;
    last_day: number;
    last_week: number;
  };
  recent_signals?: Signal[];
  collection_health?: Record<string, unknown>;
  generated_at?: string;
  summary?: DashboardSummary;
  charts?: DashboardCharts;
  top_opportunities?: Array<{
    id: string;
    name?: string;
    problem?: string;
    opportunity_score?: number;
    demand_score?: number;
    competition_score?: number;
    competition_level?: string;
    query_relevance_score?: number;
    evidence_count?: number;
    sources?: string[];
  }>;
};

export type WorkflowRun = {
  source?: string;
  success?: boolean;
  timestamp?: string;
  signals_collected?: number;
  signals_ingested?: number;
  quality_filtered?: number;
  vectors_created?: number;
  collection_latency_ms?: number;
  ingestion_latency_ms?: number;
};

export type RagResult = {
  content: string;
  score: number;
  source?: string | null;
  url?: string | null;
  timestamp?: string | null;
  metadata: Record<string, unknown>;
};

export type ReportsListResponse = {
  success: boolean;
  reports: Array<{
    id: string;
    title?: string;
    query: string;
    query_id?: string | null;
    created_at?: string | null;
    market_confidence_score?: number;
  }>;
};

export type ReportDetailResponse = {
  success: boolean;
  report?: Record<string, unknown> | null;
  error?: string;
};

export type SignalsLatestResponse = {
  success: boolean;
  count: number;
  signals: Signal[];
};

export type SignalsStatsResponse = {
  success: boolean;
  total: number;
  query_id?: string | null;
  report_id?: string | null;
  query_domain?: string | null;
  by_source: Record<string, number>;
  by_type: Record<string, number>;
  by_day: Record<string, number>;
  top_score: number;
};

export type SignalsSourceResponse = {
  success: boolean;
  source: string;
  count: number;
  query_id?: string | null;
  report_id?: string | null;
  query_domain?: string | null;
  signals: Signal[];
};
