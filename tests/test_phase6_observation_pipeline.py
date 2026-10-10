"""
tests/test_phase6_observation_pipeline.py — Comprehensive Test Suite for APRS Phase 6 Step 2.

Tests the complete observation pipeline foundation:
- Canonical Observation Model (Pydantic validation, serialization, conversions)
- Normalization & Anti-hallucination guardrails (missing fields, malformed, type checks)
- Ingestion Service (Validate -> Normalize -> Provenance -> Deduplicate -> Store)
- Application-level Deduplication (same day, same product, different time, different marketplace)
- Cryptographic Provenance (tamper signatures, payload hashes, integrity checks)
- Truthful Source Status & Health (UNINITIALIZED, UNCONFIGURED, HEALTHY, DEGRADED, FAILED)
- Observation Diff Engine (Price increase/decrease, rating change, review count change, stockout/restock, BSR, no material change)
- Materiality Thresholds (verifying configurable boundaries)
- Amazon Live Scraper Adapter (validation rules, error status classification, no invented BSR)
- Amazon India & Keepa unconfigured / disabled handling
- PRODUCTION SAFETY: Strictly uses :memory: or tmp_path SQLite databases. NEVER mutates production DB.
"""

import os
import sqlite3
import pytest
import datetime
from typing import Dict, Any

from core.research_sources.observation import (
    CanonicalObservation,
    SourceStatus,
    IngestionStatus,
    SourceExecutionResult,
    ObservationIngestionResult
)
from core.research_sources.diff_engine import (
    ObservationDiffEngine,
    ChangeType,
    MaterialityThresholds,
    ObservationDiffReport
)
from core.research_sources.ingestion_service import ObservationIngestionService
from core.research_sources.base import (
    BaseResearchSourceAdapter,
    SourceHealth,
    SignalType,
    EvidenceType,
    NormalizedEvidence
)
from core.research_sources.normalizer import EvidenceNormalizer
from core.research_sources.provenance import ProvenanceTracker
from core.research_sources.amazon_adapter import (
    AmazonResearchAdapter,
    AmazonScrapeStatus
)
from core.research_sources.amazon_india import AmazonIndiaAdapter
from tools.keepa_api_client import KeepaAPIClient


# ─────────────────────────────────────────────────────────────────────────────
# FIXTURES: Isolated In-Memory SQLite Database
# ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def isolated_db(tmp_path):
    """
    Creates an isolated SQLite database file mimicking the production schema.
    Guarantees production DB at data/research_engine.db is NEVER touched.
    """
    db_file = str(tmp_path / "test_research_engine.db")
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()

    # Create tables used in observation pipeline
    cur.execute("""
        CREATE TABLE scraped_listings (
            listing_id INTEGER PRIMARY KEY AUTOINCREMENT,
            asin TEXT NOT NULL,
            marketplace TEXT NOT NULL DEFAULT 'amazon.in',
            price REAL,
            rating REAL,
            review_count INTEGER,
            title TEXT,
            seller TEXT,
            scraped_at TEXT,
            source_url TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE trend_signals (
            signal_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT,
            source TEXT,
            detected_at TEXT,
            current_momentum REAL,
            growth_rate REAL,
            confidence_score REAL,
            keyword TEXT,
            raw_payload_json TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE intelligence_evidence (
            evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT,
            signal_type TEXT,
            conclusion TEXT,
            evidence_status TEXT,
            evidence_details_json TEXT,
            confidence REAL,
            source TEXT,
            source_timestamp TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE source_health (
            source_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name TEXT UNIQUE NOT NULL,
            data_type TEXT,
            last_successful_fetch TEXT,
            failure_count INTEGER DEFAULT 0,
            freshness_status TEXT DEFAULT 'UNINITIALIZED',
            response_time_ms REAL DEFAULT 0.0,
            details_json TEXT,
            updated_at TEXT
        )
    """)
    conn.commit()
    conn.close()
    return db_file


# ─────────────────────────────────────────────────────────────────────────────
# 1. NORMALIZATION & VALIDATION TESTS
# ─────────────────────────────────────────────────────────────────────────────
def test_canonical_observation_creation_and_conversion():
    """Verifies that CanonicalObservation creates valid objects and converts to NormalizedEvidence."""
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    obs = CanonicalObservation(
        source_id="google_trends",
        source_type="PUBLIC_API",
        product_id="TEST_PROD_1",
        external_id="ergonomic chair",
        observation_type="TREND",
        signal_type=SignalType.DEMAND,
        evidence_type=EvidenceType.OBSERVED_SIGNAL,
        value=78.5,
        unit="index_0_100",
        confidence=0.88,
        observed_at=now_iso,
        source_url="https://trends.google.com/test",
        adapter_version="1.0.0"
    )

    assert obs.source_id == "google_trends"
    assert obs.value == 78.5
    assert obs.generate_dedup_hash() is not None

    # Conversion to backwards-compatible NormalizedEvidence
    ev = obs.to_normalized_evidence()
    assert isinstance(ev, NormalizedEvidence)
    assert ev.source == "google_trends"
    assert ev.value == 78.5
    assert ev.signal_type == SignalType.DEMAND

    # Roundtrip conversion
    roundtrip = CanonicalObservation.from_normalized_evidence(ev, product_id="TEST_PROD_1")
    assert roundtrip.source_id == "google_trends"
    assert roundtrip.value == 78.5


def test_anti_hallucination_downgrade():
    """Ensures external sources cannot claim verified DECISION or PREDICTION evidence types."""
    obs = CanonicalObservation(
        source_id="external_agent",
        signal_type=SignalType.PRICE,
        evidence_type=EvidenceType.DECISION,  # Speculative claim
        value=999.0,
        observed_at="2026-10-08T12:00:00Z"
    )
    # EvidenceNormalizer & Ingestion Service downgrade external decisions to ESTIMATE
    service = ObservationIngestionService()
    is_valid, _ = service.validate_observation(obs)
    assert is_valid

    # Normalizer downgrade
    norm = EvidenceNormalizer.normalize_record(
        source_name="external_agent",
        source_type="API",
        entity="Widget",
        signal_type=SignalType.PRICE,
        value=999.0,
        unit="USD",
        claimed_evidence_type=EvidenceType.DECISION
    )
    assert norm.evidence_type == EvidenceType.ESTIMATE


def test_validation_rejects_missing_and_malformed():
    """Ensures observations with missing sources, empty timestamps, or negative prices are rejected."""
    service = ObservationIngestionService()

    # Missing source_id
    obs_no_src = CanonicalObservation(
        source_id="",
        signal_type=SignalType.PRICE,
        value=10.0,
        observed_at="2026-10-08T12:00:00Z"
    )
    valid, err = service.validate_observation(obs_no_src)
    assert not valid
    assert "source_id is required" in err

    # Negative price
    obs_neg_price = CanonicalObservation(
        source_id="amazon",
        signal_type=SignalType.PRICE,
        value=-50.0,
        observed_at="2026-10-08T12:00:00Z"
    )
    valid, err = service.validate_observation(obs_neg_price)
    assert not valid
    assert "cannot be negative" in err


# ─────────────────────────────────────────────────────────────────────────────
# 2. DEDUPLICATION & INGESTION TESTS
# ─────────────────────────────────────────────────────────────────────────────
def test_ingestion_and_deduplication(isolated_db):
    """Tests the full 7-stage ingestion pipeline and application-level deduplication."""
    service = ObservationIngestionService()
    now_iso = "2026-10-08T12:00:00Z"

    listing_obs = CanonicalObservation(
        source_id="amazon_scraper",
        source_type="SCRAPER",
        product_id="PROD_101",
        external_id="B08ABC1234",
        marketplace="amazon.in",
        observation_type="LISTING",
        signal_type=SignalType.PRICE,
        value={
            "price": 1499.0,
            "rating": 4.3,
            "review_count": 210,
            "title": "Smart Home Sensor Hub",
            "seller": "CloudRetail"
        },
        unit="INR",
        observed_at=now_iso
    )

    # 1. First ingestion -> ACCEPTED
    res1, diff1 = service.ingest_observation(listing_obs, db_path=isolated_db)
    assert res1.status == IngestionStatus.ACCEPTED
    assert res1.destination_table == "scraped_listings"
    assert res1.row_id == 1

    # Verify written to isolated database
    conn = sqlite3.connect(isolated_db)
    cur = conn.cursor()
    cur.execute("SELECT asin, price, rating, review_count FROM scraped_listings WHERE listing_id = 1")
    row = cur.fetchone()
    assert row == ("B08ABC1234", 1499.0, 4.3, 210)
    conn.close()

    # 2. Duplicate ingestion within same day -> DUPLICATE
    res2, diff2 = service.ingest_observation(listing_obs, db_path=isolated_db)
    assert res2.status == IngestionStatus.DUPLICATE
    assert res2.row_id == 1
    assert "Duplicate observation" in res2.reason

    # 3. Different marketplace -> ACCEPTED as distinct observation
    listing_us = listing_obs.model_copy(update={"marketplace": "amazon.com", "observed_at": "2026-10-08T14:00:00Z"})
    res3, _ = service.ingest_observation(listing_us, db_path=isolated_db)
    assert res3.status == IngestionStatus.ACCEPTED
    assert res3.row_id == 2

    # 4. Different day -> ACCEPTED as subsequent chronological observation
    listing_next_day = listing_obs.model_copy(update={"observed_at": "2026-10-09T12:00:00Z"})
    res4, diff4 = service.ingest_observation(listing_next_day, db_path=isolated_db)
    assert res4.status == IngestionStatus.ACCEPTED
    assert res4.row_id == 3


# ─────────────────────────────────────────────────────────────────────────────
# 3. CRYPTOGRAPHIC PROVENANCE TESTS
# ─────────────────────────────────────────────────────────────────────────────
def test_provenance_tamper_signature():
    """Ensures SHA-256 payload digest and tamper signatures are deterministically constructed."""
    raw_payload = {"interest": 92.0, "region": "IN", "query": "air purifier"}
    prov = ProvenanceTracker.create_provenance(
        source_name="google_trends",
        retrieval_method="PUBLIC_API_REST",
        source_url="https://trends.google.com/test",
        raw_payload=raw_payload,
        adapter_version="1.0.0",
        schema_version="1.0.0"
    )

    assert prov["source"] == "google_trends"
    assert prov["payload_sha256"] != "none"
    assert "tamper_sig" in prov
    assert len(prov["tamper_sig"]) == 16

    # Verify matching verification
    ev = NormalizedEvidence(
        source="google_trends",
        source_record_id="rec_1",
        entity="air purifier",
        signal_type=SignalType.DEMAND,
        value=92.0,
        observed_at="2026-10-08T12:00:00Z",
        retrieved_at="2026-10-08T12:00:01Z",
        provenance=prov
    )
    assert ProvenanceTracker.verify_provenance(ev)

    # Tampering source breaks verification
    ev_tampered = ev.model_copy(update={"source": "fake_source"})
    assert not ProvenanceTracker.verify_provenance(ev_tampered)


# ─────────────────────────────────────────────────────────────────────────────
# 4. TRUTHFUL SOURCE STATUS & HEALTH TESTS
# ─────────────────────────────────────────────────────────────────────────────
def test_truthful_source_status_transitions():
    """
    Verifies that unprobed adapters are classified as UNINITIALIZED,
    unconfigured adapters as UNCONFIGURED, and only successful calls become HEALTHY.
    """
    class MockAdapter(BaseResearchSourceAdapter):
        def __init__(self, available=True):
            super().__init__(source_name="mock_source")
            self._available = available

        def is_available(self):
            return self._available

        def _do_fetch_signals(self, query, limit, **kwargs):
            return []

    # 1. Unprobed -> UNINITIALIZED (not Healthy!)
    adapter = MockAdapter(available=True)
    health = adapter.health_check()
    assert health.status == SourceStatus.UNINITIALIZED.value
    assert not health.is_healthy
    assert health.last_successful_run is None

    # 2. Unconfigured -> UNCONFIGURED
    unconf_adapter = MockAdapter(available=False)
    unconf_health = unconf_adapter.health_check()
    assert unconf_health.status == SourceStatus.UNCONFIGURED.value
    assert not unconf_health.is_healthy

    # 3. Successful run -> HEALTHY
    adapter.record_success(count=5, latency_ms=120.0)
    healthy_check = adapter.health_check()
    assert healthy_check.status == SourceStatus.HEALTHY.value
    assert healthy_check.is_healthy
    assert healthy_check.last_successful_run is not None

    # 4. Intermittent error -> DEGRADED
    adapter.record_error("Temporary 503 error")
    degraded_check = adapter.health_check()
    assert degraded_check.status == SourceStatus.DEGRADED.value
    assert degraded_check.consecutive_errors == 1

    # 5. Consecutive failures >= 5 -> FAILED
    for _ in range(4):
        adapter.record_error("Persistent outage")
    failed_check = adapter.health_check()
    assert failed_check.status == SourceStatus.FAILED.value
    assert not failed_check.is_healthy


# ─────────────────────────────────────────────────────────────────────────────
# 5. OBSERVATION DIFF ENGINE TESTS
# ─────────────────────────────────────────────────────────────────────────────
def test_diff_engine_price_changes():
    """Verifies price increase, decrease, and sub-threshold noise filtering."""
    engine = ObservationDiffEngine(MaterialityThresholds(price_pct_threshold=2.0))

    prev_listing = {"price": 1000.0, "rating": 4.2, "review_count": 100, "in_stock": True}

    # Price increase of +5% (above 2% threshold)
    curr_inc = {"price": 1050.0, "rating": 4.2, "review_count": 100, "in_stock": True}
    report_inc = engine.compare_listing_snapshots(prev=prev_listing, curr=curr_inc)
    assert report_inc.requires_intelligence_refresh
    assert ChangeType.PRICE_INCREASE in report_inc.material_changes

    # Price decrease of -4%
    curr_dec = {"price": 960.0, "rating": 4.2, "review_count": 100, "in_stock": True}
    report_dec = engine.compare_listing_snapshots(prev=prev_listing, curr=curr_dec)
    assert report_dec.requires_intelligence_refresh
    assert ChangeType.PRICE_DECREASE in report_dec.material_changes

    # Sub-threshold price change (+0.5% -> non-material)
    curr_noise = {"price": 1005.0, "rating": 4.2, "review_count": 100, "in_stock": True}
    report_noise = engine.compare_listing_snapshots(prev=prev_listing, curr=curr_noise)
    assert not report_noise.requires_intelligence_refresh
    assert len(report_noise.material_changes) == 0


def test_diff_engine_stockouts_and_restock():
    """Tests stockout and restock event detection."""
    engine = ObservationDiffEngine()

    in_stock = {"price": 500.0, "in_stock": True}
    out_of_stock = {"price": 500.0, "in_stock": False}

    # Stockout
    rep_stockout = engine.compare_listing_snapshots(prev=in_stock, curr=out_of_stock)
    assert ChangeType.STOCKOUT in rep_stockout.material_changes
    assert rep_stockout.requires_intelligence_refresh

    # Restock
    rep_restock = engine.compare_listing_snapshots(prev=out_of_stock, curr=in_stock)
    assert ChangeType.RESTOCK in rep_restock.material_changes
    assert rep_restock.requires_intelligence_refresh


def test_diff_engine_bsr_handling():
    """Ensures BSR rank change is only computed when actual BSR data exists, never invented."""
    engine = ObservationDiffEngine(MaterialityThresholds(bsr_pct_threshold=10.0))

    # BSR present
    prev_bsr = {"bsr_rank": 1000, "price": 100.0}
    curr_bsr = {"bsr_rank": 800, "price": 100.0}  # 20% swing
    rep_bsr = engine.compare_listing_snapshots(prev=prev_bsr, curr=curr_bsr)
    assert ChangeType.BSR_CHANGE in rep_bsr.material_changes

    # BSR absent in one or both -> NO BSR change emitted
    prev_no_bsr = {"price": 100.0}
    curr_no_bsr = {"price": 100.0}
    rep_none = engine.compare_listing_snapshots(prev=prev_no_bsr, curr=curr_no_bsr)
    assert not any(d.field_name == "bsr_rank" for d in rep_none.diffs)


# ─────────────────────────────────────────────────────────────────────────────
# 6. AMAZON ADAPTER VALIDATION TESTS
# ─────────────────────────────────────────────────────────────────────────────
def test_amazon_adapter_validation():
    """Validates Amazon product parsing and anti-hallucination checks."""
    valid_raw = {
        "asin": "B09ABC1234",
        "title": "Ergonomic Mechanical Keyboard",
        "price": 3499.0,
        "currency": "INR",
        "domain": "amazon.in"
    }
    is_valid, err = AmazonResearchAdapter.validate_listing(valid_raw)
    assert is_valid
    assert err is None

    # Invalid ASIN (less than 10 characters)
    invalid_asin = {**valid_raw, "asin": "B09ABC"}
    is_valid, err = AmazonResearchAdapter.validate_listing(invalid_asin)
    assert not is_valid
    assert "Invalid or missing ASIN" in err

    # Zero or negative price
    invalid_price = {**valid_raw, "price": 0.0}
    is_valid, err = AmazonResearchAdapter.validate_listing(invalid_price)
    assert not is_valid
    assert "Price must be positive" in err


# ─────────────────────────────────────────────────────────────────────────────
# 7. UNCONFIGURED / DISABLED ADAPTERS TESTS
# ─────────────────────────────────────────────────────────────────────────────
def test_amazon_india_requires_decodo_in_production(monkeypatch):
    """Verifies that AmazonIndiaAdapter reports UNCONFIGURED when DECODO_AUTH is missing."""
    monkeypatch.delenv("DECODO_AUTH", raising=False)
    monkeypatch.delenv("APRS_RESEARCH_MOCK", raising=False)

    adapter = AmazonIndiaAdapter()
    assert not adapter.is_available()
    health = adapter.health_check()
    assert health.status == SourceStatus.UNCONFIGURED.value


def test_keepa_disabled_without_api_key(monkeypatch):
    """Verifies that KeepaAPIClient reports disabled and returns None without raising errors."""
    monkeypatch.delenv("KEEPA_API_KEY", raising=False)

    client = KeepaAPIClient()
    assert not client._enabled
    res = client.get_product("B09ABC1234")
    assert res is None


def test_ingest_batch(isolated_db):
    """Verifies that batch ingestion processes multiple items and reports results correctly."""
    service = ObservationIngestionService()
    now_iso = "2026-10-08T15:00:00Z"
    observations = [
        CanonicalObservation(
            source_id="google_trends",
            signal_type=SignalType.DEMAND,
            value=85.0,
            observed_at=now_iso,
            product_id=f"BATCH_PROD_{i}"
        )
        for i in range(3)
    ]
    results = service.ingest_batch(observations, db_path=isolated_db)
    assert len(results) == 3
    assert all(r.status == IngestionStatus.ACCEPTED for r in results)


def test_compare_canonical_observations():
    """Verifies direct comparison of two CanonicalObservation instances."""
    engine = ObservationDiffEngine()
    obs_old = CanonicalObservation(
        source_id="amazon",
        signal_type=SignalType.PRICE,
        value=500.0,
        observed_at="2026-10-08T10:00:00Z"
    )
    obs_new = CanonicalObservation(
        source_id="amazon",
        signal_type=SignalType.PRICE,
        value=550.0,  # +10%
        observed_at="2026-10-08T11:00:00Z"
    )
    report = engine.compare_observations(obs_old, obs_new)
    assert report.requires_intelligence_refresh
    assert ChangeType.PRICE_INCREASE in report.material_changes


def test_api_observe_product_endpoint(isolated_db, monkeypatch):
    """Verifies the explicit POST /products/{product_id}/observe API endpoint."""
    from fastapi.testclient import TestClient
    from api.main import app

    # Point DB to isolated test db
    monkeypatch.setenv("APRS_DB_PATH", isolated_db)
    monkeypatch.setenv("APRS_RESEARCH_MOCK", "1")

    # Insert test product in master_products
    conn = sqlite3.connect(isolated_db)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS master_products (
            product_id TEXT PRIMARY KEY,
            name TEXT,
            target_region TEXT,
            is_deleted INTEGER DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS product_intelligence (
            product_id TEXT PRIMARY KEY,
            overall_score REAL,
            kill_status TEXT,
            computed_at TEXT
        )
    """)
    cur.execute("""
        INSERT INTO master_products (product_id, name, target_region)
        VALUES ('TEST_PRODUCT_OBS', 'Ergonomic Desk', 'India')
    """)
    conn.commit()
    conn.close()

    client = TestClient(app)
    resp = client.post("/products/TEST_PRODUCT_OBS/observe")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["product_id"] == "TEST_PRODUCT_OBS"
    assert "pipeline_summary" in data
    assert "executed_at" in data


def test_observe_pipeline_never_writes_production_db(tmp_path, monkeypatch):
    """
    Dedicated Phase 6.2.1 Regression Test:
    Guarantees that POST /products/{product_id}/observe NEVER mutates production DB.
    1. Snapshots production DB SHA256, size, and table row counts.
    2. Sets APRS_DB_PATH to temporary isolated test DB.
    3. Calls POST /products/{product_id}/observe via TestClient.
    4. Verifies test DB received expected writes.
    5. Proves production DB SHA256 is unchanged.
    6. Proves production DB size is unchanged.
    7. Proves production DB row counts are unchanged.
    """
    import hashlib
    from pathlib import Path
    from fastapi.testclient import TestClient
    from api.main import app

    prod_db = Path("data/research_engine.db")
    assert prod_db.exists(), "Production database must exist for immutability regression test."

    # 1. Snapshot production DB before test
    size_before = prod_db.stat().st_size
    sha_before = hashlib.sha256(prod_db.read_bytes()).hexdigest()

    conn_prod = sqlite3.connect(str(prod_db))
    cur_prod = conn_prod.cursor()
    tables = [t[0] for t in cur_prod.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';").fetchall()]
    counts_before = {t: cur_prod.execute(f'SELECT count(*) FROM "{t}";').fetchone()[0] for t in tables}
    conn_prod.close()

    # 2. Setup isolated test database in tmp_path
    test_db = str(tmp_path / "isolated_observe_regression.db")
    conn_test = sqlite3.connect(test_db)
    cur_test = conn_test.cursor()
    cur_test.execute("""
        CREATE TABLE master_products (
            product_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            target_region TEXT,
            is_deleted INTEGER DEFAULT 0
        );
    """)
    cur_test.execute("""
        CREATE TABLE intelligence_evidence (
            evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            signal_type TEXT NOT NULL,
            conclusion TEXT NOT NULL,
            evidence_status TEXT DEFAULT 'VERIFIED',
            evidence_details_json TEXT,
            confidence REAL DEFAULT 0.0,
            source TEXT,
            source_timestamp TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cur_test.execute("""
        CREATE TABLE source_health (
            source_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name TEXT UNIQUE NOT NULL,
            data_type TEXT,
            last_successful_fetch TIMESTAMP,
            failure_count INTEGER DEFAULT 0,
            freshness_status TEXT DEFAULT 'UNINITIALIZED',
            response_time_ms REAL DEFAULT 0.0,
            details_json TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cur_test.execute("""
        CREATE TABLE scraped_listings (
            listing_id INTEGER PRIMARY KEY AUTOINCREMENT,
            asin TEXT NOT NULL,
            marketplace TEXT NOT NULL DEFAULT 'amazon.in',
            price REAL,
            rating REAL,
            review_count INTEGER,
            title TEXT,
            seller TEXT,
            scraped_at TEXT,
            source_url TEXT
        );
    """)
    cur_test.execute("""
        CREATE TABLE trend_signals (
            signal_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT,
            source TEXT,
            detected_at TEXT,
            current_momentum REAL,
            growth_rate REAL,
            confidence_score REAL,
            keyword TEXT,
            raw_payload_json TEXT
        );
    """)
    cur_test.execute("""
        INSERT INTO master_products (product_id, name, target_region)
        VALUES ('REGRESSION_PROD_99', 'Ergonomic Desk', 'India');
    """)
    conn_test.commit()
    conn_test.close()

    # 3. Route APRS_DB_PATH to isolated test DB
    monkeypatch.setenv("APRS_DB_PATH", test_db)
    monkeypatch.setenv("APRS_RESEARCH_MOCK", "1")

    # 4. Invoke the observation endpoint
    client = TestClient(app)
    response = client.post("/products/REGRESSION_PROD_99/observe")
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["success"] is True
    assert res_data["product_id"] == "REGRESSION_PROD_99"

    # 5. Verify isolated test DB received the writes
    conn_test_check = sqlite3.connect(test_db)
    cur_test_check = conn_test_check.cursor()
    test_evidence = cur_test_check.execute(
        "SELECT COUNT(*) FROM intelligence_evidence WHERE product_id = 'REGRESSION_PROD_99';"
    ).fetchone()[0]
    test_health = cur_test_check.execute(
        "SELECT COUNT(*) FROM source_health;"
    ).fetchone()[0]
    conn_test_check.close()
    assert test_evidence > 0, "Test DB must have received evidence records."
    assert test_health > 0, "Test DB must have received source_health records."

    # 6. Verify production DB is 100% UNTOUCHED
    size_after = prod_db.stat().st_size
    sha_after = hashlib.sha256(prod_db.read_bytes()).hexdigest()

    conn_prod_after = sqlite3.connect(str(prod_db))
    cur_prod_after = conn_prod_after.cursor()
    counts_after = {t: cur_prod_after.execute(f'SELECT count(*) FROM "{t}";').fetchone()[0] for t in tables}
    conn_prod_after.close()

    assert size_after == size_before, f"Production DB size mutated! Before={size_before}, After={size_after}"
    assert sha_after == sha_before, f"Production DB SHA256 mutated! Before={sha_before}, After={sha_after}"
    assert counts_after == counts_before, f"Production DB counts mutated! Diffs: {set(counts_after.items()) ^ set(counts_before.items())}"
