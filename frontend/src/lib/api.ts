/**
 * APRS V6 Pro Central API Client
 * Connects directly to FastAPI backend (default: http://localhost:8000)
 * Completely unauthenticated - free direct access to all data.
 */

import {
  HealthResponse,
  DashboardResponse,
  ProductListResponse,
  ProductDetailResponse,
  TrendListResponse,
  OpportunityListResponse,
  EconomicsResponse,
  APIErrorResponse,
  ResearchJobsResponse,
  SupervisorLogsResponse,
  WarRoomDebateResponse,
  DatabaseOverviewResponse,
  TableSchemaResponse,
  TableRowsResponse,
  LaunchpadSummaryResponse,
  PortfolioCalibrationSummary,
  PvRCatalogResponse,
  PvRDossierResponse,
  IntegrationOverviewResponse,
  KeepaTelemetryStatus,
  DaemonStatusResponse,
  ObservationSchedulesResponse,
  ObservationJobItem,
  SchedulerRunOnceSummary,
  WorkerStatsResponse,
  OutcomesListResponse,
  OutcomeSchemaResponse,
  OutcomeValidationResponse,
  ArchiveOverviewResponse,
  PriceCompareResponse,
  WarRoomChatResponse,
  WarRoomHistoryResponse,
  SupplierDirectoryResponse,
  WatchlistMutationResponse,
  AlertDismissResponse,
  AlertsListResponse,
  ConflictResolveResponse,
  ArchiveRestoreResponse,
  ShortlistToggleResponse,
} from "@/types/api";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export class ApiClientError extends Error {
  code: string;
  details?: unknown;
  status: number;

  constructor(message: string, code: string = "API_ERROR", status: number = 500, details?: unknown) {
    super(message);
    this.name = "ApiClientError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  
  try {
    const res = await fetch(url, {
      ...options,
      headers: {
        Accept: "application/json",
        ...options.headers,
      },
      next: { revalidate: 0 },
    });

    if (!res.ok) {
      let errorData: APIErrorResponse | null = null;
      try {
        errorData = await res.json();
      } catch {
        // Response was not JSON
      }

      const code = errorData?.error?.code || `HTTP_${res.status}`;
      const message = errorData?.error?.message || `API request failed with status ${res.status}`;
      throw new ApiClientError(message, code, res.status, errorData?.error?.details);
    }

    return await res.json();
  } catch (err: unknown) {
    if (err instanceof ApiClientError) {
      throw err;
    }
    const message = err instanceof Error ? err.message : "Network error or backend unavailable";
    throw new ApiClientError(
      `Cannot connect to APRS backend at ${API_BASE_URL}: ${message}`,
      "NETWORK_ERROR",
      0
    );
  }
}

export const api = {
  /**
   * Health check endpoint
   */
  async getHealth(): Promise<HealthResponse> {
    return request<HealthResponse>("/health");
  },

  /**
   * Main dashboard metrics
   */
  async getDashboard(): Promise<DashboardResponse> {
    return request<DashboardResponse>("/dashboard");
  },

  /**
   * Products catalog list with pagination and filters
   */
  async getProducts(params?: {
    page?: number;
    pageSize?: number;
    search?: string;
    category?: string;
    region?: string;
    is_shortlisted?: boolean;
    status?: string;
    sort_by?: string;
    sort_order?: "asc" | "desc";
  }): Promise<ProductListResponse> {
    const q = new URLSearchParams();
    if (params?.page) q.set("page", params.page.toString());
    if (params?.pageSize) q.set("page_size", params.pageSize.toString());
    if (params?.search) q.set("search", params.search);
    if (params?.category) q.set("category", params.category);
    if (params?.region) q.set("region", params.region);
    if (params?.is_shortlisted !== undefined) q.set("is_shortlisted", params.is_shortlisted.toString());
    if (params?.status) q.set("status", params.status);
    if (params?.sort_by) q.set("sort_by", params.sort_by);
    if (params?.sort_order) q.set("sort_order", params.sort_order);
    const qs = q.toString() ? `?${q.toString()}` : "";
    return request<ProductListResponse>(`/products${qs}`);
  },

  /**
   * Single product dossier lookup
   */
  async getProduct(productId: string): Promise<ProductDetailResponse> {
    return request<ProductDetailResponse>(`/products/${encodeURIComponent(productId)}`);
  },

  /**
   * Trend signals feed
   */
  async getTrends(params?: {
    page?: number;
    pageSize?: number;
    region?: string;
    platform?: string;
    search?: string;
    status?: string;
    sort_by?: string;
    sort_order?: "asc" | "desc";
  }): Promise<TrendListResponse> {
    const q = new URLSearchParams();
    if (params?.page) q.set("page", params.page.toString());
    if (params?.pageSize) q.set("page_size", params.pageSize.toString());
    if (params?.region) q.set("region", params.region);
    if (params?.platform) q.set("platform", params.platform);
    if (params?.search) q.set("search", params.search);
    if (params?.status) q.set("status", params.status);
    if (params?.sort_by) q.set("sort_by", params.sort_by);
    if (params?.sort_order) q.set("sort_order", params.sort_order);
    const qs = q.toString() ? `?${q.toString()}` : "";
    return request<TrendListResponse>(`/trends${qs}`);
  },

  /**
   * Opportunity evaluation pipeline
   */
  async getOpportunities(params?: {
    page?: number;
    pageSize?: number;
    tri_state?: "SURVIVES" | "KILLED" | "INSUFFICIENT_EVIDENCE";
    region?: string;
    category?: string;
  }): Promise<OpportunityListResponse> {
    const q = new URLSearchParams();
    if (params?.page) q.set("page", params.page.toString());
    if (params?.pageSize) q.set("page_size", params.pageSize.toString());
    if (params?.tri_state) q.set("tri_state", params.tri_state);
    if (params?.region) q.set("region", params.region);
    if (params?.category) q.set("category", params.category);
    const qs = q.toString() ? `?${q.toString()}` : "";
    return request<OpportunityListResponse>(`/opportunities${qs}`);
  },

  /**
   * 15-Factor Unit Economics evaluation
   */
  async getEconomics(
    productId: string,
    params?: {
      fobPrice?: number;
      plannedMsrp?: number;
      region?: string;
    }
  ): Promise<EconomicsResponse> {
    const q = new URLSearchParams();
    if (params?.fobPrice) q.set("fob_price", params.fobPrice.toString());
    if (params?.plannedMsrp) q.set("planned_msrp", params.plannedMsrp.toString());
    if (params?.region) q.set("region", params.region);
    const qs = q.toString() ? `?${q.toString()}` : "";
    return request<EconomicsResponse>(`/economics/${encodeURIComponent(productId)}${qs}`);
  },

  // ── Phase 4 Operations & War Room ─────────────────────────────────────────
  async getResearchJobs(limit: number = 50): Promise<ResearchJobsResponse> {
    return request<ResearchJobsResponse>(`/operations/jobs?limit=${limit}`);
  },

  async getSupervisorLogs(limit = 50): Promise<SupervisorLogsResponse> {
    return request<SupervisorLogsResponse>(`/operations/supervisor-logs?limit=${limit}`);
  },

  async getWarRoomDebate(productId: string): Promise<WarRoomDebateResponse> {
    return request<WarRoomDebateResponse>(`/operations/war-room-debate/${encodeURIComponent(productId)}`);
  },

  // ── Phase 4 Database Explorer ─────────────────────────────────────────────
  async getDbOverview(): Promise<DatabaseOverviewResponse> {
    return request<DatabaseOverviewResponse>("/db-explorer/overview");
  },

  async getDbSchema(tableName: string): Promise<TableSchemaResponse> {
    return request<TableSchemaResponse>(`/db-explorer/schema/${encodeURIComponent(tableName)}`);
  },

  async getDbRows(tableName: string, page = 1, pageSize = 20): Promise<TableRowsResponse> {
    return request<TableRowsResponse>(`/db-explorer/rows/${encodeURIComponent(tableName)}?page=${page}&page_size=${pageSize}`);
  },

  // ── Phase 4 Launchpad ─────────────────────────────────────────────────────
  async getLaunchpadSummary(): Promise<LaunchpadSummaryResponse> {
    return request<LaunchpadSummaryResponse>("/launchpad/summary");
  },

  // ── Phase 4 Calibration ───────────────────────────────────────────────────
  async getCalibrationSummary(): Promise<PortfolioCalibrationSummary> {
    return request<PortfolioCalibrationSummary>("/calibration/portfolio-summary");
  },

  // ── Phase 4 Predictions ───────────────────────────────────────────────────
  async getPredictionsCatalog(limit = 50, offset = 0): Promise<PvRCatalogResponse> {
    return request<PvRCatalogResponse>(`/predictions/catalog?limit=${limit}&offset=${offset}`);
  },

  async getPredictionDossier(productId: string): Promise<PvRDossierResponse> {
    return request<PvRDossierResponse>(`/predictions/dossier/${encodeURIComponent(productId)}`);
  },

  // ── Phase 4 Integrations & Telemetry ──────────────────────────────────────
  async getIntegrationsOverview(): Promise<IntegrationOverviewResponse> {
    return request<IntegrationOverviewResponse>("/integrations/overview");
  },

  async getKeepaTelemetry(): Promise<KeepaTelemetryStatus> {
    return request<KeepaTelemetryStatus>("/telemetry/keepa");
  },

  // ── Phase 4 Scheduler ─────────────────────────────────────────────────────
  async getSchedulerDaemon(): Promise<DaemonStatusResponse> {
    return request<DaemonStatusResponse>("/scheduler/daemon");
  },

  async getObservationMaturity(): Promise<ObservationSchedulesResponse> {
    return request<ObservationSchedulesResponse>("/scheduler/observation-maturity");
  },

  // ── Phase 4 Outcomes ──────────────────────────────────────────────────────
  async getOutcomesList(): Promise<OutcomesListResponse> {
    return request<OutcomesListResponse>("/outcomes/list");
  },

  async getOutcomeSchema(): Promise<OutcomeSchemaResponse> {
    return request<OutcomeSchemaResponse>("/outcomes/schema");
  },

  async validateOutcome(payload: Record<string, unknown>): Promise<OutcomeValidationResponse> {
    return request<OutcomeValidationResponse>("/outcomes/validate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },

  // ── Phase 4 Archive ───────────────────────────────────────────────────────
  async getArchiveOverview(): Promise<ArchiveOverviewResponse> {
    return request<ArchiveOverviewResponse>("/archive/overview");
  },

  // ── Phase 5 Action Pipelines ───────────────────────────────────────────────
  async refreshProduct(productId: string): Promise<Record<string, unknown>> {
    return request<Record<string, unknown>>(`/products/${encodeURIComponent(productId)}/refresh`, {
      method: "POST",
    });
  },

  async ingestOutcome(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
    return request<Record<string, unknown>>("/outcomes/ingest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },

  async triggerObservation(productId: string): Promise<Record<string, unknown>> {
    return request<Record<string, unknown>>(`/scheduler/observe/${encodeURIComponent(productId)}`, {
      method: "POST",
    });
  },

  // ── Phase 6 Observation Jobs ───────────────────────────────────────────────
  async getObservationJobs(params?: {
    status?: string;
    product_id?: string;
    source_id?: string;
    limit?: number;
  }): Promise<ObservationJobItem[]> {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    if (params?.product_id) q.set("product_id", params.product_id);
    if (params?.source_id) q.set("source_id", params.source_id);
    if (params?.limit) q.set("limit", params.limit.toString());
    const qs = q.toString() ? `?${q.toString()}` : "";
    return request<ObservationJobItem[]>(`/scheduler/jobs${qs}`);
  },

  async getDueObservationJobs(limit?: number, as_of?: string): Promise<ObservationJobItem[]> {
    const q = new URLSearchParams();
    if (limit) q.set("limit", limit.toString());
    if (as_of) q.set("as_of", as_of);
    const qs = q.toString() ? `?${q.toString()}` : "";
    return request<ObservationJobItem[]>(`/scheduler/jobs/due${qs}`);
  },

  async createObservationJob(payload: {
    product_id: string;
    source_id: string;
    scheduled_at?: string;
  }): Promise<ObservationJobItem> {
    return request<ObservationJobItem>("/scheduler/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },

  async runDueObservationJobs(
    limit: number = 10,
    dry_run: boolean = false,
    as_of?: string
  ): Promise<SchedulerRunOnceSummary> {
    const q = new URLSearchParams();
    q.set("limit", limit.toString());
    if (dry_run) q.set("dry_run", "true");
    if (as_of) q.set("as_of", as_of);
    return request<SchedulerRunOnceSummary>(`/scheduler/run-once?${q.toString()}`, {
      method: "POST",
    });
  },

  async getObservationWorkerStatus(): Promise<WorkerStatsResponse> {
    return request<WorkerStatsResponse>("/scheduler/worker/status");
  },

  async startObservationWorker(params?: {
    poll_interval_seconds?: number;
    batch_size?: number;
    running_lease_seconds?: number;
  }): Promise<WorkerStatsResponse> {
    return request<WorkerStatsResponse>("/scheduler/worker/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params || {}),
    });
  },

  async stopObservationWorker(timeout: number = 10.0): Promise<WorkerStatsResponse> {
    return request<WorkerStatsResponse>(`/scheduler/worker/stop?timeout=${timeout}`, {
      method: "POST",
    });
  },

  async recoverAbandonedObservationJobs(lease_seconds?: number): Promise<{
    lease_seconds: number;
    cutoff_timestamp: string;
    scanned_count: number;
    recovered_to_retry: number[];
    marked_failed: number[];
    total_recovered: number;
  }> {
    const q = lease_seconds ? `?lease_seconds=${lease_seconds}` : "";
    return request(`/scheduler/worker/recover${q}`, {
      method: "POST",
    });
  },

  // ── Price Comparison ────────────────────────────────────────────────────────
  async getPriceCompare(params: {
    productId?: string;
    query?: string;
    region?: string;
    plannedMsrp?: number;
  }): Promise<PriceCompareResponse> {
    const q = new URLSearchParams();
    if (params.productId) q.set("product_id", params.productId);
    if (params.query) q.set("query", params.query);
    if (params.region) q.set("region", params.region);
    if (params.plannedMsrp !== undefined) q.set("planned_msrp", params.plannedMsrp.toString());
    return request<PriceCompareResponse>(`/price-compare?${q.toString()}`);
  },

  // ── War Room Specialist Chat & Docx ─────────────────────────────────────────
  async sendWarRoomChat(
    queryOrPayload: string | { query: string; targetSpeaker?: string; sessionId?: string },
    targetSpeaker?: string,
    sessionId?: string
  ): Promise<WarRoomChatResponse> {
    const q = typeof queryOrPayload === "string" ? queryOrPayload : queryOrPayload.query;
    const speaker = typeof queryOrPayload === "string" ? (targetSpeaker || "auto") : (queryOrPayload.targetSpeaker || "auto");
    const session = typeof queryOrPayload === "string" ? sessionId : queryOrPayload.sessionId;
    return request<WarRoomChatResponse>("/operations/war-room/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_query: q,
        target_speaker: speaker,
        session_id: session,
      }),
    });
  },

  async getWarRoomHistory(
    sessionId?: string,
    limit: number = 50
  ): Promise<WarRoomHistoryResponse> {
    const q = new URLSearchParams();
    if (sessionId) q.set("session_id", sessionId);
    q.set("limit", limit.toString());
    return request<WarRoomHistoryResponse>(`/operations/war-room/history?${q.toString()}`);
  },

  getWarRoomDocxUrl(sessionId?: string): string {
    const q = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : "";
    return `${API_BASE_URL}/operations/war-room/docx${q}`;
  },

  // ── Supplier Directory ──────────────────────────────────────────────────────
  async getSuppliers(params?: {
    limit?: number;
    offset?: number;
    region?: string;
    productId?: string;
  }): Promise<SupplierDirectoryResponse> {
    const q = new URLSearchParams();
    if (params?.limit) q.set("limit", params.limit.toString());
    if (params?.offset) q.set("offset", params.offset.toString());
    if (params?.region) q.set("region", params.region);
    if (params?.productId) q.set("product_id", params.productId);
    const qs = q.toString() ? `?${q.toString()}` : "";
    return request<SupplierDirectoryResponse>(`/products/suppliers/directory${qs}`);
  },

  // ── Operational State Mutations ─────────────────────────────────────────────
  async addToWatchlist(
    productId: string,
    notes?: string
  ): Promise<WatchlistMutationResponse> {
    return request<WatchlistMutationResponse>(
      `/products/${encodeURIComponent(productId)}/watchlist`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ notes: notes || "" }),
      }
    );
  },

  async removeFromWatchlist(productId: string): Promise<WatchlistMutationResponse> {
    return request<WatchlistMutationResponse>(
      `/products/${encodeURIComponent(productId)}/watchlist`,
      {
        method: "DELETE",
      }
    );
  },

  async getAlerts(limit: number = 50): Promise<AlertsListResponse> {
    return request<AlertsListResponse>(`/operations/alerts?limit=${limit}`);
  },

  async dismissAlert(alertId: number): Promise<AlertDismissResponse> {
    return request<AlertDismissResponse>(`/operations/alerts/${alertId}/dismiss`, {
      method: "POST",
    });
  },

  async resolveConflict(
    conflictId: number,
    status: string = "RESOLVED",
    explanation: string = ""
  ): Promise<ConflictResolveResponse> {
    return request<ConflictResolveResponse>(
      `/operations/conflicts/${conflictId}/resolve`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status, explanation }),
      }
    );
  },

  async restoreArchivedProduct(productId: string): Promise<ArchiveRestoreResponse> {
    return request<ArchiveRestoreResponse>(
      `/archive/${encodeURIComponent(productId)}/restore`,
      {
        method: "POST",
      }
    );
  },

  async toggleShortlist(
    productId: string,
    isShortlisted: boolean = true
  ): Promise<ShortlistToggleResponse> {
    return request<ShortlistToggleResponse>(
      `/products/${encodeURIComponent(productId)}/shortlist`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_shortlisted: isShortlisted }),
      }
    );
  },
};

export const apiClient = api;

