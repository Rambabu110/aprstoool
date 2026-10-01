# HARDCODED, FAKE, MOCK & SYNTHETIC DATA AUDIT

Total suspicious pattern matches in core/tools/web: 1429

| File | Line | Classification Category | Code Snippet |
|---|---|---|---|
| `core\intelligence_engine.py` | 372 | Hardcoded weighting dict | `weights = {` |
| `core\learning_engine.py` | 412 | Mock / Fake / Synthetic keywords | `No fake data, no fabricated bias claims.` |
| `core\learning_engine.py` | 894 | Hardcoded weighting dict | `scoring_weights = {` |
| `core\learning_engine.py` | 921 | Mock / Fake / Synthetic keywords | `Never fabricates bias claims or fake evidence.` |
| `core\models.py` | 29 | Default policy / constant declaration | `raw_signal_json: Dict[str, Any] = Field(default_factory=dict)` |
| `core\models.py` | 57 | Default policy / constant declaration | `platforms_seen: List[str] = Field(default_factory=list)` |
| `core\models.py` | 58 | Default policy / constant declaration | `root_cause_hypotheses: List[str] = Field(default_factory=list)` |
| `core\orchestrator.py` | 694 | Mock / Fake / Synthetic keywords | `# Create a mock item for the existing pipeline` |
| `core\prediction_reality_report.py` | 19 | Mock / Fake / Synthetic keywords | `4. NO FAKE DATA: Returns structural readiness indicators when 0 outcomes exist` |
| `core\prediction_reality_report.py` | 20 | Mock / Fake / Synthetic keywords | `without fabricating charts, estimates, or synthetic records.` |
| `core\prediction_reality_report.py` | 91 | Default policy / constant declaration | `return format_metric(val, metric_type="currency", default_str=default_str)` |
| `core\prediction_reality_report.py` | 95 | Default policy / constant declaration | `return format_metric(val, metric_type="percentage", default_str=default_str)` |
| `core\prediction_reality_report.py` | 99 | Default policy / constant declaration | `return format_metric(val, metric_type="pp", default_str=default_str)` |
| `core\subscription_service.py` | 73 | Mock / Fake / Synthetic keywords | `logger.warning("Razorpay not configured - payments will be mocked")` |
| `core\subscription_service.py` | 304 | Mock / Fake / Synthetic keywords | `# Mock mode for development` |
| `core\subscription_service.py` | 305 | Mock / Fake / Synthetic keywords | `mock_order_id = f"order_mock_{secrets.token_hex(8)}"` |
| `core\subscription_service.py` | 306 | Mock / Fake / Synthetic keywords | `update_payment(payment_id, provider_order_id=mock_order_id)` |
| `core\subscription_service.py` | 310 | Mock / Fake / Synthetic keywords | `"razorpay_order_id": mock_order_id,` |
| `core\subscription_service.py` | 313 | Mock / Fake / Synthetic keywords | `"key_id": RAZORPAY_KEY_ID or "rzp_test_mock",` |
| `core\subscription_service.py` | 315 | Mock / Fake / Synthetic keywords | `"mock": True` |
| `core\subscription_service.py` | 323 | Mock / Fake / Synthetic keywords | `# Mock mode - always verify` |
| `core\supabase_subscription_service.py` | 477 | Mock / Fake / Synthetic keywords | `"""Create a payment order (Razorpay or mock)."""` |
| `core\supabase_subscription_service.py` | 506 | Mock / Fake / Synthetic keywords | `"key_id": os.getenv("RAZORPAY_KEY_ID", "rzp_test_mock"),` |
| `core\supabase_subscription_service.py` | 508 | Mock / Fake / Synthetic keywords | `"mock": not bool(os.getenv("RAZORPAY_KEY_ID"))` |
| `core\supabase_subscription_service.py` | 516 | Mock / Fake / Synthetic keywords | `# For now, mock mode always verifies` |
| `core\utils.py` | 115 | Mock / Fake / Synthetic keywords | `"""Check if a marketplace URL is genuine or an invented fake seed placeholder."""` |
| `core\utils.py` | 118 | Mock / Fake / Synthetic keywords | `# Reject known fake demo patterns and fake seed ASINs` |
| `core\utils.py` | 119 | Mock / Fake / Synthetic keywords | `fake_patterns = [` |
| `core\utils.py` | 126 | Mock / Fake / Synthetic keywords | `for fp in fake_patterns:` |
| `core\outcome_adapters\base.py` | 106 | Default policy / constant declaration | `errors: List[str] = field(default_factory=list)` |
| `core\outcome_adapters\base.py` | 228 | Default policy / constant declaration | `successful: List[NormalizedOutcome] = field(default_factory=list)` |
| `core\outcome_adapters\base.py` | 229 | Default policy / constant declaration | `failed: List[BatchItemError] = field(default_factory=list)` |
| `core\outcome_adapters\manual_csv_adapter.py` | 167 | Default policy / constant declaration | `errors: List[CsvRowError] = field(default_factory=list)` |
| `core\outcome_adapters\manual_csv_adapter.py` | 168 | Default policy / constant declaration | `duplicate_source_ids: List[str] = field(default_factory=list)` |
| `core\outcome_adapters\manual_csv_adapter.py` | 169 | Default policy / constant declaration | `ignored_columns: List[str] = field(default_factory=list)` |
| `core\outcome_adapters\manual_csv_adapter.py` | 170 | Default policy / constant declaration | `conflicting_records: List[Dict[str, Any]] = field(default_factory=list)` |
| `core\outcome_adapters\manual_csv_adapter.py` | 184 | Default policy / constant declaration | `errors: List[CsvRowError] = field(default_factory=list)` |
| `core\outcome_adapters\manual_csv_adapter.py` | 185 | Default policy / constant declaration | `row_results: List[Dict[str, Any]] = field(default_factory=list)` |
| `tools\ai_supervisor.py` | 85 | Default policy / constant declaration | `data_collected: Dict = field(default_factory=dict)` |
| `tools\ai_supervisor.py` | 86 | Default policy / constant declaration | `validation_results: List[Dict] = field(default_factory=list)` |
| `tools\ai_supervisor.py` | 87 | Default policy / constant declaration | `ai_feedback: List[str] = field(default_factory=list)` |
| `tools\ai_supervisor.py` | 88 | Default policy / constant declaration | `improvements_applied: List[str] = field(default_factory=list)` |
| `tools\ai_supervisor.py` | 106 | Default policy / constant declaration | `validated_at: datetime = field(default_factory=datetime.now)` |
| `tools\ai_supervisor.py` | 323 | Mock / Fake / Synthetic keywords | `6. BUSINESS VIABILITY: Price allows margins, not obvious test/fake data?` |
| `tools\ai_supervisor.py` | 332 | Mock / Fake / Synthetic keywords | `"rejection_category": "missing_data\|invalid_price\|invalid_url\|unrealistic_data\|duplicate\|marketplace_mismatch\|fake_da...` |
| `tools\ai_supervisor.py` | 994 | Mock / Fake / Synthetic keywords | `def dummy_scrape(query):` |
| `tools\ai_supervisor.py` | 997 | Mock / Fake / Synthetic keywords | `result = run_under_supervision("scrape", "test query", dummy_scrape, "amazon", "India")` |
| `tools\browser_use_cloud.py` | 11 | Mock / Fake / Synthetic keywords | `- Mock mode support for zero-spend unit tests` |
| `tools\browser_use_cloud.py` | 28 | Default policy / constant declaration | `DEFAULT_MODEL = os.getenv("BROWSER_USE_LLM", "gpt-5.6-luna")` |
| `tools\browser_use_cloud.py` | 29 | Default policy / constant declaration | `DEFAULT_MAX_COST_USD = float(os.getenv("BROWSER_USE_MAX_COST_USD", "1.00"))` |
| `tools\browser_use_cloud.py` | 42 | Mock / Fake / Synthetic keywords | `mock_mode: bool = False` |
| `tools\browser_use_cloud.py` | 45 | Default policy / constant declaration | `self.default_model = default_model` |
| `tools\browser_use_cloud.py` | 47 | Mock / Fake / Synthetic keywords | `self.mock_mode = mock_mode` |
| `tools\browser_use_cloud.py` | 50 | Mock / Fake / Synthetic keywords | `if not self.mock_mode and self.api_key:` |
| `tools\browser_use_cloud.py` | 55 | Mock / Fake / Synthetic keywords | `logger.warning("browser-use-sdk not installed; falling back to mock mode.")` |
| `tools\browser_use_cloud.py` | 56 | Mock / Fake / Synthetic keywords | `self.mock_mode = True` |
| `tools\browser_use_cloud.py` | 82 | Mock / Fake / Synthetic keywords | `# Mock Mode execution (used for tests to avoid live spending)` |
| `tools\browser_use_cloud.py` | 83 | Mock / Fake / Synthetic keywords | `if self.mock_mode or not self.api_key:` |
| `tools\browser_use_cloud.py` | 84 | Mock / Fake / Synthetic keywords | `logger.info("Running Browser-Use Cloud in mock mode (no live spending).")` |
| `tools\browser_use_cloud.py` | 86 | Mock / Fake / Synthetic keywords | `"task_id": "mock-task-12345",` |
| `tools\browser_use_cloud.py` | 87 | Mock / Fake / Synthetic keywords | `"session_id": "mock-session-67890",` |
| `tools\browser_use_cloud.py` | 90 | Mock / Fake / Synthetic keywords | `"output": "Mock browser-use execution completed successfully.",` |
| `tools\browser_use_cloud.py` | 93 | Mock / Fake / Synthetic keywords | `"mock": True` |
| `tools\keepa_api_client.py` | 23 | Default policy / constant declaration | `last_update: datetime = Field(default_factory=datetime.utcnow)` |
| `tools\review_reddit_defect_harvester.py` | 9 | Mock / Fake / Synthetic keywords | `No mocked data. No hardcoded strings. Every field comes from a real network call` |
| `tools\review_reddit_defect_harvester.py` | 189 | Mock / Fake / Synthetic keywords | `Falls back to a placeholder only if NIM is unavailable (all 3 keys fail).` |
| `tools\review_reddit_defect_harvester.py` | 246 | Mock / Fake / Synthetic keywords | `# NIM unavailable or parse failed — return placeholder that is honest about it` |
| `tools\seed_market_data.py` | 575 | Mock / Fake / Synthetic keywords | `# 1. Clean existing dummy records (clean child tables first to satisfy FOREIGN KEY constraints)` |
| `tools\seed_market_data.py` | 593 | Mock / Fake / Synthetic keywords | `# Convert any synthetic /dp/ URL to guaranteed live URL` |
| `tools\seed_market_data.py` | 826 | Mock / Fake / Synthetic keywords | `print("[WARNING] SEEDING SYNTHETIC DEMO DATASET FOR APRS")` |
| `tools\seed_market_data.py` | 833 | Mock / Fake / Synthetic keywords | `print("To load synthetic demo data for testing, run:")` |
| `tools\browser-use\browser_use\config.py` | 249 | Default policy / constant declaration | `id: str = Field(default_factory=lambda: str(uuid4()))` |
| `tools\browser-use\browser_use\config.py` | 251 | Default policy / constant declaration | `created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())` |
| `tools\browser-use\browser_use\config.py` | 286 | Default policy / constant declaration | `browser_profile: dict[str, BrowserProfileEntry] = Field(default_factory=dict)` |
| `tools\browser-use\browser_use\config.py` | 287 | Default policy / constant declaration | `llm: dict[str, LLMEntry] = Field(default_factory=dict)` |
| `tools\browser-use\browser_use\config.py` | 288 | Default policy / constant declaration | `agent: dict[str, AgentEntry] = Field(default_factory=dict)` |
| `tools\browser-use\browser_use\init_cmd.py` | 267 | Default policy / constant declaration | `default_template_names = ['default', 'advanced', 'tools']` |
| `tools\browser-use\browser_use\init_cmd.py` | 286 | Default policy / constant declaration | `default_templates = [(name, INIT_TEMPLATES[name]) for name in default_template_names if name in INIT_TEMPLATES]` |
| `tools\browser-use\browser_use\init_cmd.py` | 410 | Mock / Fake / Synthetic keywords | `# Replace placeholders` |
| `tools\browser-use\browser_use\utils.py` | 28 | Mock / Fake / Synthetic keywords | `def is_placeholder_url(url: str) -> bool:` |
| `tools\browser-use\browser_use\utils.py` | 29 | Mock / Fake / Synthetic keywords | `"""Return True for mock placeholder hostnames like https://XXX.XX."""` |
| `tools\browser-use\browser_use\utils.py` | 60 | Mock / Fake / Synthetic keywords | `"""Flatten legacy and domain-scoped sensitive data into placeholder -> value mappings."""` |
| `tools\browser-use\browser_use\utils.py` | 77 | Mock / Fake / Synthetic keywords | `"""Replace sensitive values with placeholders, longest matches first to avoid partial leaks."""` |
| `tools\browser-use\scripts\sync_browser_harness_skill.py` | 11 | Default policy / constant declaration | `DEFAULT_SOURCE_URL = 'https://raw.githubusercontent.com/browser-use/browser-harness/refs/heads/main/SKILL.md'` |
| `tools\browser-use\scripts\sync_browser_harness_skill.py` | 12 | Default policy / constant declaration | `DEFAULT_REPO_OUTPUT_PATH = ROOT / 'skills' / 'browser-use' / 'SKILL.md'` |
| `tools\browser-use\scripts\sync_browser_harness_skill.py` | 13 | Default policy / constant declaration | `DEFAULT_PACKAGE_OUTPUT_PATH = ROOT / 'browser_use' / 'skills' / 'browser-use' / 'SKILL.md'` |
| `tools\browser-use\browser_use\agent\cloud_events.py` | 64 | Default policy / constant declaration | `id: str = Field(default_factory=uuid7str)` |
| `tools\browser-use\browser_use\agent\cloud_events.py` | 71 | Default policy / constant declaration | `created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))` |
| `tools\browser-use\browser_use\agent\cloud_events.py` | 119 | Default policy / constant declaration | `id: str = Field(default_factory=uuid7str)` |
| `tools\browser-use\browser_use\agent\cloud_events.py` | 122 | Default policy / constant declaration | `created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))` |
| `tools\browser-use\browser_use\agent\cloud_events.py` | 189 | Default policy / constant declaration | `id: str = Field(default_factory=uuid7str)` |
| `tools\browser-use\browser_use\agent\cloud_events.py` | 199 | Default policy / constant declaration | `started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))` |
| `tools\browser-use\browser_use\agent\cloud_events.py` | 201 | Default policy / constant declaration | `agent_state: dict = Field(default_factory=dict)` |
| `tools\browser-use\browser_use\agent\cloud_events.py` | 232 | Default policy / constant declaration | `id: str = Field(default_factory=uuid7str)` |
| `tools\browser-use\browser_use\agent\cloud_events.py` | 241 | Default policy / constant declaration | `browser_state: dict = Field(default_factory=dict)` |
| `tools\browser-use\browser_use\agent\gif.py` | 11 | Mock / Fake / Synthetic keywords | `from browser_use.browser.views import PLACEHOLDER_4PX_SCREENSHOT` |
| `tools\browser-use\browser_use\agent\gif.py` | 64 | Mock / Fake / Synthetic keywords | `# Get all screenshots from history (including None placeholders)` |
| `tools\browser-use\browser_use\agent\gif.py` | 71 | Mock / Fake / Synthetic keywords | `# Find the first non-placeholder screenshot` |
| `tools\browser-use\browser_use\agent\gif.py` | 72 | Mock / Fake / Synthetic keywords | `# A screenshot is considered a placeholder if:` |
| `tools\browser-use\browser_use\agent\gif.py` | 73 | Mock / Fake / Synthetic keywords | `# 1. It's the exact 4px placeholder for about:blank pages, OR` |