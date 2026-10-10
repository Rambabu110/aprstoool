/**
 * APRS V6 Pro API TypeScript Definitions
 * Accurately mirrors live FastAPI backend schemas from D:\tools\APRS\api
 */

export interface HealthResponse {
  status: string;
  service: string;
  database: string;
  version?: string | null;
  database_mode?: string | null;
  timestamp: string;
}

export interface DashboardStats {
  total_products: number;
  trending_today: number;
  my_shortlist: number;
  ai_recommended: number;
  total_niches?: number;
  active_sources?: number;
  passed_products?: number;
}

export interface ScannerStatus {
  status: string;
  current_niche?: string | null;
  progress_pct: number;
  scanned_count: number;
  new_found: number;
  gates_run: number;
  errors: number;
  next_run_in_min?: number | null;
}

export interface AIModelStatusItem {
  name: string;
  role?: string | null;
  provider?: string | null;
  status: string;
  affects?: string | null;
}

export interface SourceHealthItem {
  source_name: string;
  status: string;
  last_checked?: string | null;
  success_rate_pct?: number | null;
}

export interface DiscoveryDayMetric {
  date: string;
  count: number;
}

export interface TopTrendingItem {
  rank: number;
  product_id: string;
  name: string;
  score: number;
  source: string;
  price?: number | null;
}

export interface DashboardResponse {
  stats: DashboardStats;
  scanner_status: ScannerStatus;
  ai_models_status: AIModelStatusItem[];
  source_health: SourceHealthItem[];
  products_discovered_7d: DiscoveryDayMetric[];
  top_trending: TopTrendingItem[];
  timestamp: string;
}

// ── Trends ──────────────────────────────────────────────────────────────────
export interface TrendItem {
  signal_id?: number | null;
  keyword: string;
  region?: string | null;
  source?: string | null;
  velocity_score?: number | null;
  search_volume_indicator?: string | null;
  trend_type?: string | null;
  first_detected_at?: string | null;
  last_updated_at?: string | null;
  is_active: boolean;
}

export interface TrendListResponse {
  items: TrendItem[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
}

// ── Products ────────────────────────────────────────────────────────────────
export interface GateProgressItem {
  gate_number: number;
  status: string; // "PASS", "FAIL", "PENDING", "BLOCKED", etc.
  completed_at?: string | null;
  completed_by?: string | null;
  blocked_reason?: string | null;
  metadata?: Record<string, unknown> | null;
}

export interface MultiPlatformListingItem {
  platform: string;
  title?: string | null;
  url?: string | null;
  price?: number | null;
  rating?: number | null;
  reviews_count?: number | null;
  in_stock?: boolean | null;
}

export interface ProductSummary {
  product_id: string;
  name: string;
  category?: string | null;
  region?: string | null;
  planned_msrp?: number | null;
  landed_cogs?: number | null;
  gross_margin_pct?: number | null;
  net_profit_pct?: number | null;
  status?: string | null;
  overall_score?: number | null;
  is_shortlisted: boolean;
  ai_confidence?: number | null;
  gates_passed: number;
  total_gates: number;
  created_at?: string | null;
  trend_source?: string | null;
}

export interface ProductListResponse {
  items: ProductSummary[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
}

export interface DefectClusterItem {
  cluster_id?: number | null;
  defect_category?: string | null;
  defect_description?: string | null;
  severity?: string | null;
  is_fixable?: boolean | null;
  v2_fix_description?: string | null;
  v2_bom_delta_usd?: number | null;
}

export interface ProductDetailResponse {
  product_id: string;
  name: string;
  category?: string | null;
  region?: string | null;
  planned_msrp?: number | null;
  landed_cogs?: number | null;
  gross_margin_pct?: number | null;
  estimated_cac?: number | null;
  net_profit_pct?: number | null;
  worst_case_stress_margin_pct?: number | null;
  status?: string | null;
  overall_score?: number | null;
  trend_source?: string | null;
  consensus_status?: string | null;
  action_plan?: string | null;
  sourcing_cluster?: string | null;
  marketplace_url?: string | null;
  competitor_3star_flaws?: string | null;
  upgrade_v2_engineering?: string | null;
  bsr_rank?: number | null;
  estimated_daily_units?: number | null;
  human_override_status?: string | null;
  first_discovered_date?: string | null;
  last_evaluated_date?: string | null;
  keepa_price_stability?: number | null;
  helium_monthly_revenue?: number | null;
  factory_cogs?: number | null;
  created_at?: string | null;
  updated_at?: string | null;
  ai_rejection_reason?: string | null;
  ai_reasoning?: string | null;
  ai_confidence?: number | null;
  is_shortlisted: boolean;
  gates: GateProgressItem[];
  listings: MultiPlatformListingItem[];
  defects?: DefectClusterItem[] | null;
  economics_summary?: {
    scenarios?: Array<{
      scenario?: string | null;
      msrp?: number | null;
      fob_cost?: number | null;
      contribution_margin?: number | null;
      contribution_margin_pct?: number | null;
      overall_pass?: number | boolean | null;
      composite_score?: number | null;
    }>;
  } | null;
}

// ── Opportunities ───────────────────────────────────────────────────────────
export interface OpportunityItem {
  product_id: string;
  name: string;
  category?: string | null;
  region?: string | null;
  planned_msrp?: number | null;
  tri_state_status: "SURVIVES" | "KILLED" | "INSUFFICIENT_EVIDENCE";
  current_gate: number;
  overall_score?: number | null;
  action_plan?: string | null;
  arbiter_verdict?: string | null;
  rejection_reason?: string | null;
  gates_summary: Record<string, string>;
  created_at?: string | null;
}

export interface OpportunityListResponse {
  items: OpportunityItem[];
  total: number;
  survives_count: number;
  killed_count: number;
  insufficient_evidence_count: number;
  page: number;
  page_size: number;
  has_next: boolean;
}

// ── Unit Economics ──────────────────────────────────────────────────────────
export interface ScenarioDetail {
  scenario_name: string; // "Conservative" | "Expected" | "Upside"
  planned_msrp: number;
  fob_price: number;
  landed_cogs: number;
  gross_margin_pct: number;
  net_profit_pct: number;
  worst_case_stress_margin_pct: number;
  break_even_units: number;
  is_viable: boolean;
  status: string;
}

export interface EconomicsResponse {
  product_id: string;
  region: string;
  currency: string;
  composite_score: number;
  recommendation: string; // "PASS" | "FAIL"
  is_financially_viable: boolean;
  lead_time_days: number;
  trend_half_life_days: number;
  lead_time_risk_factor: number;
  scenarios: ScenarioDetail[];
  factor_breakdown?: Record<string, unknown> | null;
}

export interface APIErrorResponse {
  error: {
    code: string;
    message: string;
    details?: unknown;
  };
}

// ── Phase 4: Operations & War Room ──────────────────────────────────────────
export interface ResearchJobSummary {
  research_run_id: string;
  run_status: string;
  started_at: string;
  ended_at?: string | null;
  duration_seconds?: number | null;
  products_processed: number;
  sources_consulted_count?: number;
  signals_generated_count: number;
  alerts_generated_count: number;
  gate_transitions_count?: number;
  errors_count: number;
  // Optional backwards compatibility aliases
  run_id?: string;
  target_category?: string | null;
  target_region?: string | null;
  status?: string;
  completed_at?: string | null;
  total_discovered?: number;
  total_shortlisted?: number;
  error_message?: string | null;
}

export type ResearchJobItem = ResearchJobSummary;

export interface ResearchJobsResponse {
  jobs: ResearchJobSummary[];
  total_jobs: number;
  active_jobs_count?: number;
  completed_jobs_count?: number;
  last_successful_run?: string | null;
  active_jobs?: number;
}

export interface SupervisorLogItem {
  log_id: number;
  event_type: string;
  timestamp: string;
  active_tasks?: number;
  total_validations?: number;
  details?: Record<string, unknown> | null;
  agent_name?: string;
  severity?: string;
  message?: string;
  context_data?: Record<string, unknown> | null;
  created_at?: string;
}

export interface SupervisorLogsResponse {
  logs: SupervisorLogItem[];
  total_events: number;
  total_logs?: number;
  unresolved_warnings?: number;
}

export interface AgentDebatePacket {
  agent: string;
  finding: string;
  confidence: number;
  evidence: string[];
  risks: string[];
  missing_data?: string[];
  recommendation: string;
}

export interface AgentVoteItem {
  agent_name: string;
  vote: string;
  score: number;
  confidence: number;
  rationale: string;
}

export interface WarRoomDebateResponse {
  product_id: string;
  product_name: string;
  decision_type: string;
  arbiter_verdict: string;
  agent_packets: AgentDebatePacket[];
  disagreements: string[];
  consensus_score: number;
  disagreement_detected?: boolean;
  disagreement_severity?: string;
  agent_votes?: AgentVoteItem[];
  risk_flags?: string[];
  engine_source?: string;
}

// ── Phase 4: Database Explorer ──────────────────────────────────────────────
export interface TableInfo {
  name: string;
  row_count: number;
}

export interface ColumnInfo {
  cid: number;
  name: string;
  data_type: string;
  notnull: boolean;
  default_value?: string | null;
  pk: boolean;
}

export interface ForeignKeyInfo {
  id: number;
  seq: number;
  table: string;
  from_col: string;
  to_col: string;
}

export interface TableSchemaResponse {
  table_name: string;
  row_count: number;
  columns: ColumnInfo[];
  foreign_keys: ForeignKeyInfo[];
}

export interface DatabaseOverviewResponse {
  database_file: string;
  file_size_bytes: number;
  last_modified: string;
  integrity_status: string;
  foreign_key_violations_count: number;
  total_tables: number;
  tables: TableInfo[];
}

export interface TableRowsResponse {
  table_name: string;
  total_rows: number;
  page: number;
  page_size: number;
  columns: string[];
  rows: Array<Record<string, unknown>>;
}

// ── Phase 4: Launchpad ──────────────────────────────────────────────────────
export interface LaunchpadItem {
  item_id: number;
  product_id: string;
  product_name: string;
  launch_status: string;
  target_launch_date?: string | null;
  target_moq: number;
  target_fob: number;
  confirmed_factory_name?: string | null;
  sample_ordered: boolean;
  sample_approved: boolean;
  qc_aql_standard?: string | null;
  compliance_checklist_passed: boolean;
  purchase_order_generated: boolean;
  updated_at: string;
  category?: string | null;
  region?: string | null;
  planned_msrp?: number | null;
  landed_cogs?: number | null;
  gross_margin_pct?: number | null;
}

export interface LaunchpadSummaryResponse {
  total_items: number;
  status_counts: Record<string, number>;
  items: LaunchpadItem[];
}

// ── Phase 4: Calibration & Learning ────────────────────────────────────────
export interface PortfolioCalibrationSummary {
  total_master_products: number;
  products_with_decisions: number;
  products_with_outcomes: number;
  products_awaiting_observation: number;
  products_with_partial_observations: number;
  products_with_calibrations: number;
  total_decisions: number;
  total_outcomes: number;
  total_calibrations: number;
  total_corrections: number;
  total_observed_units?: number | null;
  total_observed_revenue?: number | null;
  demand_bias_mbe?: number | null;
  demand_mae?: number | null;
  demand_mape?: number | null;
  price_bias_mbe?: number | null;
  directional_accuracy_counts: Record<string, number>;
  calibration_reliability: string;
  sample_size: number;
  structural_readiness: unknown;
  maturity_summary: Record<string, unknown>;
}

// ── Phase 4: Predictions ────────────────────────────────────────────────────
export interface PvRCatalogItem {
  product_id: string;
  name: string;
  category?: string | null;
  status?: string | null;
  decision_count: number;
  latest_decision_timestamp?: string | null;
  outcome_count: number;
  latest_period_end?: string | null;
  calibration_count: number;
  latest_directional_accuracy: string;
  launch_status?: string | null;
  target_launch_date?: string | null;
  coverage_status: string;
}

export interface PvRCatalogResponse {
  total: number;
  items: PvRCatalogItem[];
}

export interface PvRDossierResponse {
  product_id: string;
  exists: boolean;
  coverage_status: string;
  master?: Record<string, unknown> | null;
  current_intelligence?: Record<string, unknown> | null;
  decisions: Array<Record<string, unknown>>;
  outcomes: Array<Record<string, unknown>>;
  calibrations: Array<Record<string, unknown>>;
  comparisons: Array<Record<string, unknown>>;
  observation_schedule?: Record<string, unknown> | null;
  decision?: Record<string, unknown> | null;
  outcome?: Record<string, unknown> | null;
  comparison?: Record<string, unknown> | null;
}

// ── Phase 4: Integrations & Telemetry ───────────────────────────────────────
export interface SourceHealthItem {
  source_name: string;
  status: string;
  last_success?: string | null;
  last_error?: string | null;
  consecutive_failures: number;
  latency_ms?: number | null;
  category: string;
}

export interface MarketplaceConfigItem {
  marketplace_id: string;
  name: string;
  region: string;
  currency: string;
  is_active: boolean;
  min_margin_pct: number;
  max_return_rate_pct: number;
}

export interface LLMClusterStatus {
  default_model: string;
  supervisor_model: string;
  temperature: number;
  provider_configured: boolean;
  provider_type: string;
}

export interface IntegrationOverviewResponse {
  sources: SourceHealthItem[];
  marketplaces: MarketplaceConfigItem[];
  llm_cluster: LLMClusterStatus;
  total_sources: number;
  healthy_sources: number;
}

export interface KeepaTelemetryStatus {
  configured: boolean;
  api_key_present: boolean;
  domain_id: number;
  tokens_left?: number | null;
  refill_rate?: number | null;
  total_products_with_keepa_data: number;
  average_price_stability: number;
  status_message: string;
}

// ── Phase 4: Scheduler ──────────────────────────────────────────────────────
export interface DaemonStatusResponse {
  daemon_name: string;
  is_running: boolean;
  last_heartbeat?: string | null;
  pid?: number | null;
  poll_interval_seconds: number;
  mode: string;
  message: string;
}

export interface ScheduledProductItem {
  product_id: string;
  decision_date: string;
  first_expected_date?: string | null;
  observation_window_days: number;
  status: string;
  next_expected_observation?: unknown;
}

export interface ObservationSchedulesResponse {
  total_scheduled: number;
  ready_for_observation: number;
  pending_observation: number;
  products: ScheduledProductItem[];
}

// ── Phase 6: Observation Jobs ────────────────────────────────────────────────
export interface ObservationJobItem {
  job_id: number;
  product_id: string;
  source_id: string;
  scheduled_at: string;
  status: "PENDING" | "RUNNING" | "SUCCESS" | "FAILED" | "SKIPPED" | "RETRY";
  attempt_count: number;
  last_attempt_at?: string | null;
  last_success_at?: string | null;
  next_run_at?: string | null;
  last_error?: string | null;
  created_at: string;
  updated_at: string;
}

export interface SchedulerRunOnceSummary {
  dry_run: boolean;
  requested_limit: number;
  due_jobs_count?: number;
  found_due?: number;
  eligible_count?: number;
  skipped_count?: number;
  executed: number;
  succeeded: number;
  failed: number;
  skipped: number;
  jobs: unknown;
}

export interface WorkerStatsResponse {
  worker_id: string;
  state: "STOPPED" | "STARTING" | "IDLE" | "PROCESSING" | "STOPPING" | "ERROR";
  is_running: boolean;
  thread_alive: boolean;
  started_at?: string | null;
  stopped_at?: string | null;
  last_heartbeat?: string | null;
  last_cycle_at?: string | null;
  cycle_count: number;
  total_jobs_executed: number;
  total_jobs_succeeded: number;
  total_jobs_failed: number;
  total_jobs_skipped: number;
  recovered_jobs_count: number;
  last_error?: string | null;
  consecutive_errors: number;
  poll_interval_seconds: number;
  batch_size: number;
  running_lease_seconds: number;
  last_cycle_summary?: Record<string, unknown> | null;
}

// ── Phase 4: Outcomes ───────────────────────────────────────────────────────
export interface OutcomeItem {
  outcome_id: number;
  product_id: string;
  observation_date: string;
  window_days: number;
  actual_units_sold?: number | null;
  actual_revenue?: number | null;
  actual_cac?: number | null;
  actual_cogs?: number | null;
  actual_cm_pct?: number | null;
  status: string;
  created_at: string;
}

export interface OutcomesListResponse {
  outcomes: OutcomeItem[];
  total: number;
  windows_breakdown: Record<string, number>;
}

export interface OutcomeSchemaRule {
  field_name: string;
  field_type: string;
  required: boolean;
  description: string;
}

export interface OutcomeSchemaResponse {
  schema_version: string;
  supported_windows: number[];
  allowed_sources: string[];
  rules: OutcomeSchemaRule[];
}

export interface OutcomeValidationResponse {
  is_valid: boolean;
  errors: string[];
  warnings: string[];
  derived_metrics?: Record<string, unknown> | null;
}

// ── Phase 4: Archive ────────────────────────────────────────────────────────
export interface DecisionLedgerRecord {
  decision_id: number;
  product_id: string;
  product_name: string;
  decision_timestamp: string;
  metrics: Record<string, unknown>;
  model_version: string;
  kill_status: string;
  opportunity_score: number;
  confidence: number;
  policy_version?: string | null;
}

export interface MeetingAuditLogRecord {
  message_id: number;
  session_id: string;
  timestamp: string;
  speaker_name: string;
  speaker_role: string;
  avatar?: string | null;
  user_prompt?: string | null;
  response_text?: string | null;
}

export interface ArchivedProductRecord {
  product_id: string;
  name: string;
  category?: string | null;
  region?: string | null;
  delete_reason?: string | null;
  soft_deleted_at?: string | null;
  planned_msrp?: number | null;
  overall_score?: number | null;
}

export interface ArchiveOverviewResponse {
  decision_ledger_records: DecisionLedgerRecord[];
  meeting_audit_logs: MeetingAuditLogRecord[];
  archived_products?: ArchivedProductRecord[];
  total_archived_decisions: number;
  total_meeting_logs: number;
  total_defect_clusters: number;
  total_data_conflicts: number;
  total_soft_deleted?: number;
}


// ── Price Comparison ────────────────────────────────────────────────────────
export interface MarketplaceListingItem {
  platform: string;
  badge: string;
  color: string;
  url: string;
  price: number;
  currency: string;
  delivery: string;
  note: string;
  is_lowest: boolean;
  savings_vs_highest: number;
}

export interface WholesalerContactInfo {
  factory_name: string;
  contact_person: string;
  contact_details: string;
  email?: string | null;
  phone?: string | null;
  fob_unit_price?: string | null;
  moq_units?: number | null;
  sourcing_cluster?: string | null;
  directory_url?: string | null;
}

export interface PriceCompareResponse {
  product_id?: string | null;
  product_name: string;
  region: string;
  benchmark_msrp: number;
  currency: string;
  marketplaces: MarketplaceListingItem[];
  lowest_price: number;
  highest_price: number;
  arbitrage_savings: number;
  arbitrage_pct: number;
  wholesaler?: WholesalerContactInfo | null;
}

// ── War Room Specialist Chat ────────────────────────────────────────────────
export interface WarRoomReply {
  agent_id: string;
  agent_name: string;
  title: string;
  avatar: string;
  message: string;
  cached: boolean;
  latency_sec: number;
}

export interface WarRoomChatResponse {
  session_id: string;
  replies: WarRoomReply[];
}

export interface WarRoomHistoryItem {
  message_id: number;
  session_id: string;
  speaker_name: string;
  speaker_role: string;
  avatar?: string | null;
  user_prompt: string;
  response_text: string;
  timestamp: string;
}

export interface WarRoomHistoryResponse {
  total: number;
  messages: WarRoomHistoryItem[];
  session_id?: string | null;
  turns?: MeetingAuditLogRecord[];
}

// ── Supplier Directory ──────────────────────────────────────────────────────
export interface SupplierDirectoryItem {
  supplier_id: number;
  product_id: string;
  product_name: string;
  region: string;
  factory_name: string;
  supplier_type?: string | null;
  industrial_address?: string | null;
  contact_person?: string | null;
  contact_details?: string | null;
  platform_profile_url?: string | null;
  fob_unit_price?: string | null;
  moq_units?: number | null;
  sample_cost_leadtime?: string | null;
  certifications?: string | null;
}

export interface SupplierDirectoryResponse {
  total: number;
  suppliers: SupplierDirectoryItem[];
}

// ── Operational State Mutations ─────────────────────────────────────────────
export interface WatchlistMutationResponse {
  product_id: string;
  in_watchlist: boolean;
  status: string;
  message: string;
}

export interface AlertItem {
  alert_id: number;
  product_id?: string | null;
  severity: string;
  title: string;
  what_happened: string;
  why_it_matters: string;
  recommended_action: string;
  is_dismissed: number;
  created_at: string;
}

export interface AlertsListResponse {
  total: number;
  alerts: AlertItem[];
}

export interface AlertDismissResponse {
  alert_id: number;
  success?: boolean;
  is_dismissed?: boolean;
  message: string;
}


export interface ConflictResolveResponse {
  conflict_id: number;
  status: string;
  message: string;
}

export interface ArchiveRestoreResponse {
  product_id: string;
  is_deleted?: number;
  restored?: boolean;
  message: string;
}

export interface ShortlistToggleResponse {
  product_id: string;
  is_shortlisted: boolean;
  message: string;
}



