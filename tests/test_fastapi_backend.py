"""
tests/test_fastapi_backend.py — Comprehensive test suite for Phase 1 FastAPI API Layer.

Covers:
1. Application initialization, router registration, OpenAPI schema generation.
2. Safe health check endpoint (/health).
3. Dashboard live metrics query (/dashboard).
4. Product catalog listing, search, pagination, and sorting (/products).
5. Product dossier detail query and 404 handling (/products/{product_id}).
6. Real trending signals query (/trends).
7. Opportunity pipeline with strict tri-state preservation (/opportunities).
8. 15-factor 3-scenario unit economics engine reuse (/economics/{product_id}).
9. Standardized error response handling (404, 422).
10. Unauthenticated direct access verification (NO login, NO credentials required).
"""
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.main import app


@pytest.fixture(scope="module", autouse=True)
def setup_db_env():
    """Ensure APRS_DB_PATH points to an isolated copy of the database during tests, protecting production."""
    import os
    import shutil
    import tempfile

    orig = os.environ.get("APRS_DB_PATH")
    prod_db = PROJECT_ROOT / "data" / "research_engine.db"

    temp_dir = tempfile.TemporaryDirectory()
    test_db = Path(temp_dir.name) / "test_isolated_fastapi.db"
    shutil.copy2(str(prod_db), str(test_db))

    os.environ["APRS_DB_PATH"] = str(test_db)
    yield test_db

    if orig is not None:
        os.environ["APRS_DB_PATH"] = orig
    else:
        os.environ.pop("APRS_DB_PATH", None)
    temp_dir.cleanup()


@pytest.fixture(scope="module")
def client():
    """Shared TestClient instance for API verification."""
    with TestClient(app) as test_client:
        yield test_client


# ── 1. Application & Router Tests ─────────────────────────────────────────────

def test_app_creation_and_metadata():
    """Verify FastAPI instance creation and metadata."""
    assert app.title == "APRS V6 Pro API"
    assert app.version == "6.0.0"


def test_openapi_generation(client):
    """Verify OpenAPI 3 schema generation and endpoint registration."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "paths" in schema
    paths = schema["paths"]
    assert "/health" in paths
    assert "/dashboard" in paths
    assert "/products" in paths
    assert "/products/{product_id}" in paths
    assert "/trends" in paths
    assert "/opportunities" in paths
    assert "/economics/{product_id}" in paths


# ── 2. Health Endpoint Tests ──────────────────────────────────────────────────

def test_health_endpoint_success(client):
    """Verify GET /health returns safe status and tests database connectivity."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "aprs-api"
    assert data["database"] == "ok"
    assert "timestamp" in data
    # Guarantee zero secret leakage
    for secret_keyword in ["key", "secret", "token", "password", "nvapi"]:
        assert secret_keyword not in str(data).lower()


# ── 3. Dashboard Endpoint Tests ───────────────────────────────────────────────

def test_dashboard_real_metrics(client):
    """Verify GET /dashboard returns real, non-fabricated metrics from SSOT."""
    response = client.get("/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert "stats" in data
    stats = data["stats"]
    assert stats["total_products"] > 0
    assert stats["trending_today"] >= 0
    assert stats["my_shortlist"] >= 0
    assert stats["ai_recommended"] >= 0
    assert stats["total_niches"] >= 0
    assert stats["active_sources"] >= 0

    assert "scanner_status" in data
    assert "ai_models_status" in data
    assert isinstance(data["ai_models_status"], list)
    assert len(data["ai_models_status"]) > 0

    assert "source_health" in data
    assert "products_discovered_7d" in data
    assert "top_trending" in data
    assert len(data["top_trending"]) <= 5


# ── 4. Products Endpoint Tests ────────────────────────────────────────────────

def test_products_listing_and_pagination(client):
    """Verify GET /products returns real items with valid pagination."""
    response = client.get("/products?page=1&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["page_size"] == 10
    assert data["total"] > 0
    assert len(data["items"]) == 10
    assert data["has_next"] is True

    first = data["items"][0]
    assert "product_id" in first
    assert "name" in first
    assert "gates_passed" in first
    assert "total_gates" in first


def test_products_filtering(client):
    """Verify GET /products supports category and search filters."""
    # Test text search
    response = client.get("/products?search=Wireless&page_size=5")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["items"], list)

    # Test sorting
    resp_sorted = client.get("/products?sort_by=overall_score&sort_order=desc&page_size=5")
    assert resp_sorted.status_code == 200
    sorted_items = resp_sorted.json()["items"]
    if len(sorted_items) >= 2:
        assert (sorted_items[0]["overall_score"] or 0) >= (sorted_items[1]["overall_score"] or 0)


def test_product_detail_success(client):
    """Verify GET /products/{product_id} returns enriched product dossier."""
    # First get a valid product_id from the list
    list_resp = client.get("/products?page_size=1")
    product_id = list_resp.json()["items"][0]["product_id"]

    response = client.get(f"/products/{product_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["product_id"] == product_id
    assert "name" in data
    assert "gates" in data
    assert isinstance(data["gates"], list)
    assert "listings" in data


def test_product_detail_not_found(client):
    """Verify GET /products/{product_id} returns 404 for unknown product."""
    response = client.get("/products/NON_EXISTENT_ID_99999")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "PRODUCT_NOT_FOUND"


# ── 5. Trending Endpoint Tests ────────────────────────────────────────────────

def test_trends_listing_real_data(client):
    """Verify GET /trends returns real signals from trend_signals table."""
    response = client.get("/trends?page=1&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] > 0
    assert len(data["items"]) <= 10
    first = data["items"][0]
    assert "keyword" in first
    assert "velocity_score" in first


def test_trends_filter_by_region(client):
    """Verify GET /trends filters properly by region."""
    response = client.get("/trends?region=India&page_size=5")
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["region"] == "India"


# ── 6. Opportunities Endpoint Tests ───────────────────────────────────────────

def test_opportunities_tri_state_preservation(client):
    """Verify GET /opportunities preserves strict tri-state logic without collapsing."""
    response = client.get("/opportunities?page=1&page_size=20")
    assert response.status_code == 200
    data = response.json()
    assert "survives_count" in data
    assert "killed_count" in data
    assert "insufficient_evidence_count" in data

    # Verify every returned item has a valid tri-state status
    valid_tri_states = {"SURVIVES", "KILLED", "INSUFFICIENT_EVIDENCE"}
    for item in data["items"]:
        assert item["tri_state_status"] in valid_tri_states


def test_opportunities_filter_by_tri_state(client):
    """Verify filtering by specific tri_state."""
    response = client.get("/opportunities?tri_state=SURVIVES")
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["tri_state_status"] == "SURVIVES"


# ── 7. Economics Endpoint Tests ───────────────────────────────────────────────

def test_economics_calculation_reuse(client):
    """Verify GET /economics/{product_id} evaluates 15-factor 3-scenario economics."""
    list_resp = client.get("/products?page_size=1")
    product_id = list_resp.json()["items"][0]["product_id"]

    response = client.get(f"/economics/{product_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["product_id"] == product_id
    assert "scenarios" in data
    assert len(data["scenarios"]) == 3
    scenario_names = [s["scenario_name"] for s in data["scenarios"]]
    assert "Conservative" in scenario_names
    assert "Expected" in scenario_names
    assert "Upside" in scenario_names
    assert data["recommendation"] in ["PASS", "FAIL"]
    assert "composite_score" in data
    assert "factor_breakdown" in data


def test_economics_not_found(client):
    """Verify GET /economics/{product_id} returns 404 for unknown product."""
    response = client.get("/economics/NON_EXISTENT_ID_99999")
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "PRODUCT_NOT_FOUND"


# ── 8. Error Handling Tests ───────────────────────────────────────────────────

def test_validation_error_format(client):
    """Verify unparseable parameters return 422 with standardized error wrapper."""
    response = client.get("/products?page=0")  # page ge=1 violated
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "details" in data["error"]


# ── 9. Product Access Guarantee: Unauthenticated Direct Access ────────────────

def test_direct_access_no_credentials_required(client):
    """
    CRITICAL ARCHITECTURAL CONTRACT:
    APRS V6 Pro is a free application with direct access.
    No login, no authorization headers, and no session cookies are required.
    All normal endpoints must respond with HTTP 200 without credentials.
    """
    endpoints = [
        "/health",
        "/dashboard",
        "/products",
        "/trends",
        "/opportunities",
    ]
    for endpoint in endpoints:
        # Request completely without Authorization header or cookies
        response = client.get(endpoint)
        assert response.status_code == 200, f"Endpoint {endpoint} unexpectedly rejected unauthenticated access!"


# ── 11. Phase 4 Advanced Engine & Operations Tests ────────────────────────────

def test_operations_jobs(client):
    """Verify /operations/jobs returns real historical and active research runs."""
    resp = client.get("/operations/jobs")
    assert resp.status_code == 200
    data = resp.json()
    assert "jobs" in data
    assert "total_jobs" in data
    assert data["total_jobs"] >= 10
    assert len(data["jobs"]) > 0


def test_operations_supervisor_logs(client):
    """Verify /operations/supervisor-logs returns real supervisor events."""
    resp = client.get("/operations/supervisor-logs?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert "logs" in data
    assert "total_events" in data
    assert data["total_events"] > 20000


def test_operations_war_room_debate(client):
    """Verify /operations/war-room-debate/{product_id} executes 5-agent debate logic."""
    resp = client.get("/operations/war-room-debate/IN_B08KLT")
    assert resp.status_code == 200
    data = resp.json()
    assert data["product_id"] == "IN_B08KLT"
    assert "agent_packets" in data
    assert len(data["agent_packets"]) >= 4
    agent_names = [p["agent"] for p in data["agent_packets"]]
    assert "Trend Scout" in agent_names
    assert "Defect Analyst" in agent_names
    assert "Economics Auditor" in agent_names


def test_db_explorer_overview(client):
    """Verify /db-explorer/overview returns all table row counts and integrity check."""
    resp = client.get("/db-explorer/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["integrity_status"] == "ok"
    assert data["total_tables"] >= 30
    table_names = [t["name"] for t in data["tables"]]
    assert "master_products" in table_names
    assert "launchpad_items" in table_names
    assert "decision_ledger" in table_names


def test_db_explorer_schema_and_rows(client):
    """Verify /db-explorer/schema and /db-explorer/rows for allowlisted table."""
    schema_resp = client.get("/db-explorer/schema/master_products")
    assert schema_resp.status_code == 200
    schema_data = schema_resp.json()
    assert schema_data["table_name"] == "master_products"
    assert schema_data["row_count"] == 315

    rows_resp = client.get("/db-explorer/rows/master_products?page=1&page_size=10")
    assert rows_resp.status_code == 200
    rows_data = rows_resp.json()
    assert len(rows_data["rows"]) == 10
    assert rows_data["total_rows"] == 315

    # Safe allowlist rejection
    bad_resp = client.get("/db-explorer/schema/malicious_non_table")
    assert bad_resp.status_code == 404


def test_launchpad_summary(client):
    """Verify /launchpad/summary returns real launchpad items."""
    resp = client.get("/launchpad/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_items"] == 8
    statuses = data["status_counts"]
    assert "PO_ISSUED" in statuses or "SAMPLE_APPROVED" in statuses
    item_ids = [it["item_id"] for it in data["items"]]
    assert 101 in item_ids


def test_calibration_and_predictions(client):
    """Verify /calibration and /predictions endpoints."""
    cal_resp = client.get("/calibration/summary")
    assert cal_resp.status_code == 200
    cal_data = cal_resp.json()
    assert cal_data["total_master_products"] == 315
    assert cal_data["total_decisions"] == 1

    pred_resp = client.get("/predictions/catalog")
    assert pred_resp.status_code == 200
    pred_data = pred_resp.json()
    assert pred_data["total"] >= 1

    dossier_resp = client.get("/predictions/dossier/US_B09ABC")
    assert dossier_resp.status_code == 200
    dossier_data = dossier_resp.json()
    assert dossier_data["exists"] is True
    assert len(dossier_data["decisions"]) >= 1


def test_integrations_and_telemetry(client):
    """Verify /integrations/overview and /telemetry/keepa/status endpoints."""
    int_resp = client.get("/integrations/overview")
    assert int_resp.status_code == 200
    int_data = int_resp.json()
    # Supports both legacy 11 sources and expanded 22 sources (including synchronized research adapters)
    assert len(int_data["sources"]) in (11, 22)
    assert len(int_data["marketplaces"]) == 6
    assert int_data["llm_cluster"]["local_ollama_present"] is False

    keepa_resp = client.get("/telemetry/keepa/status")
    assert keepa_resp.status_code == 200
    keepa_data = keepa_resp.json()
    assert "supported_domains" in keepa_data
    assert keepa_data["monitored_products_count"] > 0


def test_scheduler_daemon_and_maturity(client):
    """Verify /scheduler/daemon and /scheduler/observation-maturity endpoints."""
    daemon_resp = client.get("/scheduler/daemon")
    assert daemon_resp.status_code == 200
    daemon_data = daemon_resp.json()
    assert "is_paused" in daemon_data
    assert "thread_alive" in daemon_data

    obs_resp = client.get("/scheduler/observation-maturity")
    assert obs_resp.status_code == 200
    obs_data = obs_resp.json()
    assert obs_data["maturity_summary"]["total_launched_products"] >= 1
    assert len(obs_data["schedules"]) >= 1


def test_outcomes_and_archive(client):
    """Verify /outcomes endpoints and /archive/overview."""
    out_resp = client.get("/outcomes")
    assert out_resp.status_code == 200
    out_data = out_resp.json()
    assert "total" in out_data

    schema_resp = client.get("/outcomes/schema")
    assert schema_resp.status_code == 200
    schema_data = schema_resp.json()
    assert "DAY_30" in schema_data["period_types"]

    # Dry run validation test
    val_resp = client.post("/outcomes/validate", json={
        "product_id": "IN_B08KLT",
        "period_start": "2026-10-01",
        "period_end": "2026-10-30",
        "period_type": "DAY_30",
        "actual_units_sold": 100,
        "actual_revenue": 79900.0,
        "actual_landed_cogs": 20000.0
    })
    assert val_resp.status_code == 200
    val_data = val_resp.json()
    assert val_data["is_valid"] is True
    assert "actual_avg_selling_price" in val_data["derived_metrics"]

    # Archive
    arch_resp = client.get("/archive/overview")
    assert arch_resp.status_code == 200
    arch_data = arch_resp.json()
    assert arch_data["total_archived_decisions"] == 1
    assert len(arch_data["meeting_audit_logs"]) == 6


# ── Phase 5 Action Pipelines & Ingestion Tests ───────────────────────────────

def test_phase5_product_refresh(client):
    """Verify explicit POST /products/{product_id}/refresh action endpoint."""
    # Successful refresh on existing product
    resp = client.post("/products/IN_B08KLT/refresh")
    assert resp.status_code == 200
    data = resp.json()
    assert data["product_id"] == "IN_B08KLT"
    assert data["success"] is True
    assert "evidence_count" in data
    assert data["refreshed_at"] is not None

    # 404 for non-existent product
    resp_404 = client.post("/products/NONEXISTENT_XYZ_999/refresh")
    assert resp_404.status_code == 404


def test_phase5_outcome_ingest(client):
    """Verify explicit POST /outcomes/ingest mutation endpoint."""
    valid_payload = {
        "product_id": "IN_B08KLT",
        "period_start": "2026-10-01",
        "period_end": "2026-10-30",
        "period_type": "DAY_30",
        "actual_units_sold": 120,
        "actual_revenue": 95880.0,
        "actual_landed_cogs": 24000.0,
        "actual_ad_spend": 12000.0,
        "data_source": "test_phase5_adapter"
    }
    resp = client.post("/outcomes/ingest", json=valid_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert isinstance(data["outcome_id"], int)
    assert data["product_id"] == "IN_B08KLT"

    # Reject invalid payload missing required fields
    invalid_payload = {
        "product_id": "IN_B08KLT",
        # missing period_start, period_end, period_type
        "actual_units_sold": 100
    }
    resp_inv = client.post("/outcomes/ingest", json=invalid_payload)
    assert resp_inv.status_code in (400, 422)


def test_phase5_scheduler_observe(client):
    """Verify explicit POST /scheduler/observe/{product_id} maturity check action."""
    # Observe launched product
    resp = client.post("/scheduler/observe/US_B09ABC")
    assert resp.status_code == 200
    data = resp.json()
    assert data["product_id"] == "US_B09ABC"
    assert "observation_job_state" in data
    assert data["observation_job_state"] in (
        "QUEUED_FOR_INGESTION",
        "SKIPPED_NOT_LAUNCHED",
        "COMPLETED",
        "SCHEDULED_NOT_DUE"
    )

    # 404 for non-existent product
    resp_404 = client.post("/scheduler/observe/UNKNOWN_PROD_12345")
    assert resp_404.status_code == 404


