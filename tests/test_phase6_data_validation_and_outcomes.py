"""
tests/test_phase6_data_validation_and_outcomes.py — Isolated Test Suite for Phase 6 Step 5.

Verifies:
1. Provenance correctness & tamper signatures.
2. Genuine vs Mock source classification.
3. Observation deduplication & strict NULL preservation.
4. Material change detection & noise filtering.
5. Missing field handling (preserves NULL, no zero conversion, no false refresh).
6. Source failure isolation & graceful degradation.
7. Post-launch outcome validation & pre-launch proxy rejection.
8. Prediction/outcome linkage & temporal integrity.
9. Calibration zero-samples honesty (N=0 samples means NO calibrated accuracy claimed).
10. Calibration with small known dataset (deterministic signed error, MAE, MAPE).
11. FastAPI endpoints (/outcomes/ingest, /outcomes/validate, /calibration/summary, /integrations/overview).
12. Strict production database immutability (data/research_engine.db untouched).
"""

import os
import json
import sqlite3
import pytest
import datetime
import hashlib
from pathlib import Path
from fastapi.testclient import TestClient

from core.database import (
    init_db,
    get_connection,
    record_product_evaluation,
    record_decision_snapshot,
    validate_outcome_payload
)
from core.research_sources.provenance import (
    ProvenanceType,
    ProvenanceTracker
)
from core.research_sources.observation import (
    CanonicalObservation,
    SignalType,
    SourceStatus,
    SourceExecutionResult
)
from core.research_sources.diff_engine import (
    ObservationDiffEngine,
    ChangeType,
    FieldDiff,
    MaterialityThresholds
)
from core.research_sources.ingestion_service import (
    ObservationIngestionService
)
from core.research_sources.registry import (
    ResearchSourceRegistry
)
from core.research_sources.tiktok import TikTokResearchAdapter
from core.research_sources.rivalsearch import RivalSearchAdapter
from core.research_sources.google_trends import GoogleTrendsAdapter
from core.research_sources.gdelt import GDELTResearchAdapter
from core.outcome_ingestion import (
    OutcomeIngestionService,
    derive_outcome_metrics,
    resolve_decision_link
)
from core.prediction_reality_report import (
    PredictionRealityReportService
)
from api.main import create_app
from api.services.integrations_service import IntegrationsService


# ─────────────────────────────────────────────────────────────────────────────
# FIXTURES: Isolated SQLite Database
# ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """
    Creates an isolated temporary SQLite database for testing.
    Guarantees production DB at data/research_engine.db is NEVER touched.
    """
    db_file = str(tmp_path / "test_phase6_step5.db")
    monkeypatch.setenv("APRS_DB_PATH", db_file)
    monkeypatch.setenv("APRS_RESEARCH_MOCK", "1")

    # Initialize full schema
    init_db()

    # Seed test product in master_products via authoritative helper
    prod = {
        "id": "TEST_P5",
        "name": "Ergonomic Mechanical Keyboard",
        "category": "Electronics",
        "region": "India",
        "retail_msrp": 2999.0,
        "factory_cogs": 800.0,
        "est_cac": 200.0,
        "bsr_rank": 150,
        "estimated_daily_units": 20,
        "ad_active_days": 10,
        "sourcing_hub": "Shenzhen",
        "marketplace_url": "https://www.amazon.in/dp/TEST_P5",
        "competitor_flaw": "Key chatter",
        "upgrade_v2": "Hot-swappable optical switches",
        "suppliers": []
    }
    econ = {
        "status": "PASS",
        "score": 85.0,
        "landed_cogs": 800.0,
        "gross_margin_pct": 73.0,
        "net_profit_pct": 28.0,
        "worst_case_stress_margin_pct": 15.0,
        "consensus_status": "CONSENSUS_PASS",
        "action_plan": "Proceed to sourcing"
    }
    record_product_evaluation(prod, econ)

    return db_file


@pytest.fixture
def api_client(isolated_db):
    app = create_app()
    with TestClient(app) as client:
        yield client


# ─────────────────────────────────────────────────────────────────────────────
# 1. PROVENANCE CORRECTNESS & TAMPER SIGNATURES
# ─────────────────────────────────────────────────────────────────────────────
def test_01_provenance_type_enumeration_and_tamper_signature():
    """Validates provenance types, signature calculation, tampering detection, and anti-mock live guardrail."""
    # Enums check
    assert ProvenanceType.LIVE_VERIFIED == "LIVE_VERIFIED"
    assert ProvenanceType.CACHED == "CACHED"
    assert ProvenanceType.MOCK == "MOCK"
    assert ProvenanceType.TEST == "TEST"
    assert ProvenanceType.UNVERIFIED == "UNVERIFIED"
    assert ProvenanceType.NOT_CONFIGURED == "NOT_CONFIGURED"
    assert ProvenanceType.FAILED == "FAILED"

    # Create provenance for live observation
    prov = ProvenanceTracker.create_provenance(
        source_name="google_trends",
        retrieval_method="live_api",
        provenance_type=ProvenanceType.LIVE_VERIFIED.value,
        source_url="https://trends.google.com",
        raw_payload={"keyword": "keyboard", "interest": 75}
    )

    assert prov["provenance_type"] == "LIVE_VERIFIED"
    assert "tamper_sig" in prov
    assert prov["source"] == "google_trends"
    assert prov["payload_sha256"] != "none"

    # Mock evidence wrapper for verification
    class DummyEvidence:
        source = "google_trends"
        provenance = prov

    assert ProvenanceTracker.verify_provenance(DummyEvidence()) is True

    # Tampering test: modify source
    class TamperedSourceEvidence:
        source = "tiktok"
        provenance = dict(prov)

    assert ProvenanceTracker.verify_provenance(TamperedSourceEvidence()) is False

    # Tampering test: modify payload hash without updating sig
    tampered_prov = dict(prov)
    tampered_prov["payload_sha256"] = "modified_hash"
    class TamperedHashEvidence:
        source = "google_trends"
        provenance = tampered_prov

    assert ProvenanceTracker.verify_provenance(TamperedHashEvidence()) is False

    # Anti-mock guardrail: cannot create LIVE_VERIFIED for known mock adapter without valid live token
    mock_prov = ProvenanceTracker.create_provenance(
        source_name="tiktok",
        retrieval_method="mock_stub",
        provenance_type=ProvenanceType.LIVE_VERIFIED.value,  # invalid claim
        source_url=None,
        raw_payload={"query": "keyboard"}
    )
    # Must be downgraded to MOCK or rejected from LIVE_VERIFIED
    assert mock_prov["provenance_type"] in ("MOCK", "UNVERIFIED")


# ─────────────────────────────────────────────────────────────────────────────
# 2. GENUINE VS MOCK SOURCE CLASSIFICATION
# ─────────────────────────────────────────────────────────────────────────────
def test_02_genuine_vs_mock_source_classification(isolated_db):
    """Verifies that mock adapters are classified as MOCK, while real adapters are not."""
    tiktok = TikTokResearchAdapter()
    rival = RivalSearchAdapter()
    trends = GoogleTrendsAdapter()
    gdelt = GDELTResearchAdapter()

    assert tiktok.is_mock is True
    assert rival.is_mock is True
    assert getattr(trends, "is_mock", False) is False
    assert getattr(gdelt, "is_mock", False) is False

    # Ingesting TikTok signals classifies them truthfully as MOCK
    obs = tiktok.fetch_canonical_observations(query="keyboard", limit=2)
    assert len(obs.observations) > 0
    for o in obs.observations:
        assert o.provenance_type == ProvenanceType.MOCK

    # Check IntegrationsService truthfulness
    overview = IntegrationsService.get_overview()
    source_map = {s.source_name: s for s in overview.sources}
    if "tiktok" in source_map:
        assert source_map["tiktok"].provenance_status == "MOCK/TEST"
        assert source_map["tiktok"].is_mock is True


# ─────────────────────────────────────────────────────────────────────────────
# 3. OBSERVATION DEDUPLICATION & NULL PRESERVATION
# ─────────────────────────────────────────────────────────────────────────────
def test_03_observation_deduplication_and_null_preservation(isolated_db):
    """Verifies deduplication prevents redundant evidence insertion, preserving NULLs."""
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    service = ObservationIngestionService()

    obs1 = CanonicalObservation(
        product_id="TEST_P5",
        source_id="amazon_scraper",
        signal_type=SignalType.PRICE,
        value=1999.0,
        unit="INR",
        observed_at=now_iso,
        source_url="https://amazon.in/dp/B001",
        provenance_type=ProvenanceType.TEST
    )

    # First ingestion -> ACCEPTED
    res1, diff1 = service.ingest_observation(obs1, db_path=isolated_db, run_diff=True)
    assert res1.status == "ACCEPTED"
    assert res1.row_id is not None

    # Exact duplicate ingestion -> DUPLICATE
    res2, diff2 = service.ingest_observation(obs1, db_path=isolated_db, run_diff=True)
    assert res2.status == "DUPLICATE"
    assert res2.row_id == res1.row_id

    # Observation with missing / NULL price must preserve NULL, never become 0.0
    obs_null = CanonicalObservation(
        product_id="TEST_P5",
        source_id="amazon_scraper",
        signal_type=SignalType.PRICE,
        value=None,  # missing price
        unit="INR",
        observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        provenance_type=ProvenanceType.TEST
    )
    res_null, diff_null = service.ingest_observation(obs_null, db_path=isolated_db, run_diff=True)
    assert res_null.status in ("ACCEPTED", "DUPLICATE")

    # Verify database does not contain 0.0 for this observation
    conn = sqlite3.connect(isolated_db)
    cur = conn.cursor()
    cur.execute("SELECT evidence_details_json FROM intelligence_evidence WHERE product_id = 'TEST_P5' ORDER BY evidence_id DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()
    if row and row[0]:
        details = json.loads(row[0])
        val = details.get("value")
        assert val is None or val == 1999.0  # never 0.0


# ─────────────────────────────────────────────────────────────────────────────
# 4. MATERIAL CHANGE DETECTION & NOISE FILTERING
# ─────────────────────────────────────────────────────────────────────────────
def test_04_material_change_detection_and_noise_filtering():
    """Verifies diff engine catches significant market movements and ignores minor noise."""
    engine = ObservationDiffEngine(MaterialityThresholds(
        price_pct_threshold=2.0,
        trend_momentum_threshold=5.0
    ))
    t0 = "2026-06-01T10:00:00Z"
    t1 = "2026-06-01T11:00:00Z"

    # 1. Unchanged observations -> No material change
    obs_prev = CanonicalObservation(
        product_id="P1", source_id="src1", signal_type=SignalType.PRICE,
        value=1000.0, observed_at=t0
    )
    obs_curr = CanonicalObservation(
        product_id="P1", source_id="src1", signal_type=SignalType.PRICE,
        value=1000.0, observed_at=t1
    )
    diff = engine.compare_observations(obs_prev, obs_curr)
    assert diff.requires_intelligence_refresh is False
    assert len(diff.material_changes) == 0

    # 2. Sub-threshold price noise (+1.0%, threshold 2.0%) -> Ignored
    obs_noise = CanonicalObservation(
        product_id="P1", source_id="src1", signal_type=SignalType.PRICE,
        value=1010.0, observed_at=t1
    )
    diff_noise = engine.compare_observations(obs_prev, obs_noise)
    assert diff_noise.requires_intelligence_refresh is False
    assert len(diff_noise.material_changes) == 0

    # 3. Material price jump (+10.0%) -> PRICE_INCREASE
    obs_jump = CanonicalObservation(
        product_id="P1", source_id="src1", signal_type=SignalType.PRICE,
        value=1100.0, observed_at=t1
    )
    diff_jump = engine.compare_observations(obs_prev, obs_jump)
    assert diff_jump.requires_intelligence_refresh is True
    assert ChangeType.PRICE_INCREASE in diff_jump.material_changes

    # 4. Trend momentum shift (+15.0 points, threshold 5.0) -> TREND_ACCELERATION
    trend_prev = CanonicalObservation(
        product_id="P1", source_id="trends", signal_type=SignalType.DEMAND,
        value=50.0, observed_at=t0
    )
    trend_curr = CanonicalObservation(
        product_id="P1", source_id="trends", signal_type=SignalType.DEMAND,
        value=65.0, observed_at=t1
    )
    diff_trend = engine.compare_observations(trend_prev, trend_curr)
    assert diff_trend.requires_intelligence_refresh is True
    assert ChangeType.TREND_ACCELERATION in diff_trend.material_changes

    # 5. Listing stockout -> STOCKOUT
    list_prev = {"price": 1000, "in_stock": True}
    list_curr = {"price": 1000, "in_stock": False}
    diff_stock = engine.compare_listing_snapshots(list_prev, list_curr)
    assert diff_stock.requires_intelligence_refresh is True
    assert ChangeType.STOCKOUT in diff_stock.material_changes


# ─────────────────────────────────────────────────────────────────────────────
# 5. MISSING FIELDS PRESERVE NULL
# ─────────────────────────────────────────────────────────────────────────────
def test_05_missing_fields_preserve_null():
    """Verifies that missing fields in new observations do not trigger false price drops."""
    engine = ObservationDiffEngine()

    obs_prev = CanonicalObservation(
        product_id="P1", source_id="src1", signal_type=SignalType.PRICE,
        value=1000.0, observed_at="2026-06-01T10:00:00Z"
    )
    obs_curr = CanonicalObservation(
        product_id="P1", source_id="src1", signal_type=SignalType.PRICE,
        value=None,  # missing field
        observed_at="2026-06-01T11:00:00Z"
    )

    diff = engine.compare_observations(obs_prev, obs_curr)
    assert diff.requires_intelligence_refresh is False
    assert len(diff.material_changes) == 0
    # Must explicitly record non-material diff preserving NULL
    assert any(d.field_name == "price" and d.new_value is None for d in diff.diffs)


# ─────────────────────────────────────────────────────────────────────────────
# 6. SOURCE FAILURE ISOLATION
# ─────────────────────────────────────────────────────────────────────────────
def test_06_source_failure_isolation(isolated_db):
    """Verifies that a failing source is isolated and does not crash the pipeline."""
    registry = ResearchSourceRegistry()
    # Execute pipeline requesting non-existent adapter
    res = registry.execute_observation_pipeline(
        query="wireless mouse",
        sources=["non_existent_source"],
        db_path=isolated_db
    )

    assert "non_existent_source" in res["source_results"]
    assert res["source_results"]["non_existent_source"]["status"] in ("UNCONFIGURED", "UNAVAILABLE")
    assert res["requires_intelligence_refresh"] is False


# ─────────────────────────────────────────────────────────────────────────────
# 7. POST-LAUNCH OUTCOME VALIDATION & PROXIES REJECTION
# ─────────────────────────────────────────────────────────────────────────────
def test_07_outcome_validation_and_proxies_rejection():
    """Verifies outcome validation rejects corrupt dates, negative values, and scraped proxies."""
    valid_base = {
        "product_id": "TEST_P5",
        "period_start": "2026-06-01",
        "period_end": "2026-06-30",
        "period_type": "DAY_30",
        "actual_units_sold": 150,
        "actual_revenue": 75000.0,
        "data_source": "MANUAL_CSV"
    }

    # Valid payload passes
    validated = validate_outcome_payload(valid_base)
    assert validated["actual_units_sold"] == 150

    # 1. Invalid date order (end < start)
    with pytest.raises(ValueError, match="period_end .* cannot be before period_start"):
        corrupt_dates = dict(valid_base, period_start="2026-06-30", period_end="2026-06-01")
        validate_outcome_payload(corrupt_dates)

    # 2. Negative units sold
    with pytest.raises(ValueError, match="cannot be negative"):
        negative_units = dict(valid_base, actual_units_sold=-10)
        validate_outcome_payload(negative_units)

    # 3. Returns > Units sold
    with pytest.raises(ValueError, match="actual_returns_count .* cannot exceed actual_units_sold"):
        excess_returns = dict(valid_base, actual_units_sold=100, actual_returns_count=150)
        validate_outcome_payload(excess_returns)

    # 4. Stockouts > observation days
    with pytest.raises(ValueError, match="actual_stockout_days .* cannot exceed observation period days"):
        excess_stockout = dict(valid_base, actual_stockout_days=45)
        validate_outcome_payload(excess_stockout)

    # 5. Pre-launch scraped research proxies rejected as post-launch outcomes
    for proxy_src in ["GOOGLE_TRENDS", "COMPETITOR_BSR", "SCRAPED_ESTIMATE", "HELIUM_ESTIMATE"]:
        with pytest.raises(ValueError, match="represents pre-launch research/scraped estimates"):
            proxy_payload = dict(valid_base, data_source=proxy_src)
            validate_outcome_payload(proxy_payload)


# ─────────────────────────────────────────────────────────────────────────────
# 8. PREDICTION / OUTCOME LINKAGE & TEMPORAL INTEGRITY
# ─────────────────────────────────────────────────────────────────────────────
def test_08_prediction_outcome_linkage_and_temporal_integrity(isolated_db):
    """Verifies that outcomes link only to decisions that predate or match period_start."""
    # Seed decision in isolated db
    dec_id = record_decision_snapshot(
        product_id="TEST_P5",
        decision_timestamp="2026-06-01 12:00:00",
        override_predictions={
            "predicted_daily_units": 10.0,
            "predicted_selling_price": 500.0,
            "predicted_cm_pct": 25.0
        }
    )

    # Outcome with period_start on or after decision succeeds
    linked_id = resolve_decision_link(
        product_id="TEST_P5",
        period_start="2026-06-15",
        decision_id=dec_id
    )
    assert linked_id == dec_id

    # Outcome predating decision fails with Temporal Integrity Error
    with pytest.raises(ValueError, match="Temporal Integrity Error"):
        resolve_decision_link(
            product_id="TEST_P5",
            period_start="2026-05-15",
            decision_id=dec_id
        )


# ─────────────────────────────────────────────────────────────────────────────
# 9. CALIBRATION ZERO SAMPLES HONESTY
# ─────────────────────────────────────────────────────────────────────────────
def test_09_calibration_zero_samples_honesty(isolated_db):
    """Verifies that an uncalibrated database reports zero samples and no fabricated metrics."""
    summary = PredictionRealityReportService.get_portfolio_summary(db_path=isolated_db)

    assert summary["sample_size"] == 0
    assert summary["total_calibrations"] == 0
    assert summary["calibration_reliability"] == "NO_CALIBRATIONS"
    assert summary["demand_bias_mbe"] is None
    assert summary["demand_mae"] is None
    assert summary["demand_mape"] is None
    assert summary["price_bias_mbe"] is None


# ─────────────────────────────────────────────────────────────────────────────
# 10. CALIBRATION WITH SMALL KNOWN DATASET
# ─────────────────────────────────────────────────────────────────────────────
def test_10_calibration_with_small_known_dataset(isolated_db):
    """Verifies deterministic prediction vs reality error calculation on known outcome."""
    # Seed decision
    dec_id = record_decision_snapshot(
        product_id="TEST_P5",
        decision_timestamp="2026-06-01 10:00:00",
        override_predictions={
            "predicted_daily_units": 10.0,
            "predicted_selling_price": 500.0,
            "predicted_cm_pct": 30.0
        }
    )

    # Ingest outcome matching predictions exactly: 300 units in 30 days = 10 units/day
    outcome_payload = {
        "product_id": "TEST_P5",
        "decision_id": dec_id,
        "period_start": "2026-06-02",
        "period_end": "2026-07-01",
        "period_type": "DAY_30",
        "actual_units_sold": 300,
        "actual_revenue": 150000.0,
        "actual_avg_selling_price": 500.0,
        "actual_cm_pct": 30.0,
        "data_source": "SELLER_CENTRAL_CSV",
        "source_record_id": "ORDER_BATCH_1001"
    }

    res = OutcomeIngestionService.ingest_outcome(outcome_payload, auto_calibrate=True)
    assert res["status"] in ("CREATED", "UPDATED")
    assert res["calibrated"] is True
    assert res["calibration_id"] is not None

    # Check calibration record in isolated DB
    calib = res["calibration"]
    assert calib is not None
    assert calib["demand_signed_error"] == 0.0
    assert calib["demand_absolute_error"] == 0.0
    assert calib["directional_accuracy"] == "EXACT"
    assert calib["price_signed_error"] == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# 11. OUTCOMES AND CALIBRATION API ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────
def test_11_outcomes_and_calibration_api_endpoints(api_client, isolated_db):
    """Verifies API endpoints for outcomes validation, ingestion, and calibration summary."""
    # 1. Validation dry-run
    val_resp = api_client.post("/outcomes/validate", json={
        "product_id": "TEST_P5",
        "period_start": "2026-06-01",
        "period_end": "2026-06-30",
        "period_type": "DAY_30",
        "actual_units_sold": 100,
        "actual_revenue": 50000.0
    })
    assert val_resp.status_code == 200
    val_data = val_resp.json()
    assert val_data["is_valid"] is True
    assert val_data["derived_metrics"]["actual_avg_selling_price"] == 500.0

    # 2. Ingest outcome
    ing_resp = api_client.post("/outcomes/ingest", json={
        "product_id": "TEST_P5",
        "period_start": "2026-06-01",
        "period_end": "2026-06-30",
        "period_type": "DAY_30",
        "actual_units_sold": 100,
        "actual_revenue": 50000.0,
        "actual_inventory": 400,
        "actual_stockout_days": 0,
        "actual_conversion_rate_pct": 3.5,
        "provenance": "LIVE_VERIFIED_OPERATOR",
        "source_record_id": "API_INGEST_001"
    })
    assert ing_resp.status_code == 200
    ing_data = ing_resp.json()
    assert ing_data["success"] is True
    assert ing_data["outcome_id"] > 0

    # 3. List outcomes
    list_resp = api_client.get("/outcomes/list")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["total"] >= 1
    assert list_data["items"][0]["actual_inventory"] == 400

    # 4. Calibration summary
    calib_resp = api_client.get("/calibration/summary")
    assert calib_resp.status_code == 200
    calib_data = calib_resp.json()
    assert "sample_size" in calib_data


# ─────────────────────────────────────────────────────────────────────────────
# 12. NO PRODUCTION DB MUTATION GUARANTEE
# ─────────────────────────────────────────────────────────────────────────────
def test_12_no_production_db_mutation_guarantee(tmp_path, monkeypatch):
    """Calculates SHA256 of production DB before and after tests, proving zero contamination."""
    prod_db = Path("data/research_engine.db")
    if not prod_db.exists():
        pytest.skip("Production database does not exist.")

    def calc_sha(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    sha_before = calc_sha(prod_db)
    mtime_before = prod_db.stat().st_mtime
    size_before = prod_db.stat().st_size

    # Run complete workflow against temporary database
    temp_db = str(tmp_path / "guarantee_test.db")
    monkeypatch.setenv("APRS_DB_PATH", temp_db)
    monkeypatch.setenv("APRS_RESEARCH_MOCK", "1")
    init_db()

    prod = {
        "id": "TMP_PROD",
        "name": "Test Widget",
        "category": "Electronics",
        "region": "India",
        "retail_msrp": 1000.0,
        "factory_cogs": 300.0,
        "est_cac": 100.0,
        "bsr_rank": 200,
        "estimated_daily_units": 10,
        "ad_active_days": 10,
        "sourcing_hub": "Delhi",
        "marketplace_url": "https://www.amazon.in/dp/TMP_PROD",
        "competitor_flaw": "None",
        "upgrade_v2": "V2",
        "suppliers": []
    }
    econ = {
        "status": "PASS",
        "score": 80.0,
        "landed_cogs": 300.0,
        "gross_margin_pct": 70.0,
        "net_profit_pct": 20.0,
        "worst_case_stress_margin_pct": 10.0,
        "consensus_status": "CONSENSUS_PASS",
        "action_plan": "Proceed"
    }
    record_product_evaluation(prod, econ)

    record_decision_snapshot(
        product_id="TMP_PROD",
        decision_timestamp="2026-06-01 00:00:00",
        override_predictions={"predicted_daily_units": 5.0}
    )

    OutcomeIngestionService.ingest_outcome({
        "product_id": "TMP_PROD",
        "period_start": "2026-06-02",
        "period_end": "2026-07-01",
        "period_type": "DAY_30",
        "actual_units_sold": 150,
        "actual_revenue": 30000.0,
        "data_source": "MANUAL_TEST"
    })

    # Check production DB again
    sha_after = calc_sha(prod_db)
    mtime_after = prod_db.stat().st_mtime
    size_after = prod_db.stat().st_size

    assert sha_after == sha_before, "CRITICAL: Production DB SHA256 was mutated during test!"
    assert size_after == size_before, "CRITICAL: Production DB size changed during test!"
    assert mtime_after == mtime_before, "CRITICAL: Production DB modification time changed during test!"
