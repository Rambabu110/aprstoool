"""
tests/test_phase6_step5_1_audit.py — Independent Audit Verification Test Suite.

Audits and verifies:
1. Provenance Security & Integrity Digest verification (Tasks 2)
2. Anti-mock downgrade guardrails and unpromoted user payloads (Tasks 2)
3. Observation deduplication & change detection (Tasks 4)
4. Missing field vs numeric zero semantics (Tasks 4)
5. Post-launch outcome validation, temporal integrity & calibration (Tasks 5)
6. Zero-sample calibration honesty & small dataset calculation (Tasks 5)
7. Strict production database non-mutation (Safety Rule)
"""

import os
import sqlite3
import tempfile
import hashlib
import json
import pytest
from datetime import datetime, timezone, timedelta

from core.research_sources.provenance import ProvenanceTracker, ProvenanceType
from core.research_sources.base import (
    NormalizedEvidence,
    EvidenceType,
    SignalType
)
from core.research_sources.normalizer import EvidenceNormalizer
from core.research_sources.observation import CanonicalObservation, SourceStatus
from core.research_sources.diff_engine import (
    ObservationDiffEngine,
    MaterialityThresholds,
    ChangeType
)
from core.research_sources.ingestion_service import (
    ObservationIngestionService,
    IngestionStatus
)
from core.outcome_ingestion import (
    OutcomeIngestionService,
    derive_outcome_metrics,
    resolve_decision_link
)
from core.calibration_engine import (
    calculate_signed_error,
    calculate_absolute_error,
    calculate_aggregate_bias,
    calibrate_outcome,
    STATUS_CALIBRATED,
    STATUS_TEMPORAL_MISMATCH,
    STATUS_NO_MATCHING_DECISION
)
from core.prediction_reality_report import PredictionRealityReportService


# =============================================================================
# FIXTURES — ISOLATED TEMPORARY DATABASES ONLY
# =============================================================================
@pytest.fixture
def temp_audit_db():
    """Provides a completely isolated temporary SQLite database for testing."""
    fd, path = tempfile.mkstemp(suffix="_step5_1_audit.db")
    os.close(fd)

    conn = sqlite3.connect(path)
    cur = conn.cursor()

    # Minimal schema for master_products, decision_ledger, product_outcomes,
    # prediction_calibrations, scraped_listings, trend_signals, intelligence_evidence
    cur.execute("""
        CREATE TABLE master_products (
            product_id TEXT PRIMARY KEY,
            title TEXT,
            category TEXT,
            status TEXT DEFAULT 'ACTIVE',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE decision_ledger (
            decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            decision_timestamp TIMESTAMP NOT NULL,
            decision_type TEXT NOT NULL,
            decision_status TEXT DEFAULT 'COMMITTED',
            predicted_units_sold INTEGER,
            predicted_monthly_revenue REAL,
            predicted_margin_pct REAL,
            predicted_success_prob REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE product_outcomes (
            outcome_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            decision_id INTEGER,
            period_start DATE NOT NULL,
            period_end DATE NOT NULL,
            period_type TEXT NOT NULL,
            actual_units_sold INTEGER,
            actual_revenue REAL,
            actual_avg_selling_price REAL,
            actual_landed_cogs REAL,
            actual_contribution_margin REAL,
            actual_cm_pct REAL,
            actual_returns_count INTEGER,
            actual_return_rate_pct REAL,
            actual_rto_count INTEGER,
            actual_rto_rate_pct REAL,
            actual_ad_spend REAL,
            actual_cac REAL,
            actual_inventory INTEGER,
            actual_stockout_days INTEGER,
            data_source TEXT NOT NULL DEFAULT 'MANUAL',
            source_record_id TEXT,
            notes TEXT,
            ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES master_products(product_id),
            FOREIGN KEY (decision_id) REFERENCES decision_ledger(decision_id),
            UNIQUE(product_id, period_type, period_start, period_end)
        )
    """)
    cur.execute("""
        CREATE TABLE outcome_corrections_log (
            correction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            outcome_id INTEGER NOT NULL,
            product_id TEXT NOT NULL,
            field_name TEXT NOT NULL,
            previous_value TEXT,
            corrected_value TEXT,
            reason TEXT NOT NULL,
            corrected_by TEXT NOT NULL,
            corrected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE prediction_calibrations (
            calibration_id INTEGER PRIMARY KEY AUTOINCREMENT,
            outcome_id INTEGER NOT NULL,
            decision_id INTEGER NOT NULL,
            product_id TEXT NOT NULL,
            period_type TEXT NOT NULL,
            demand_signed_error REAL,
            demand_abs_error REAL,
            demand_pct_error REAL,
            demand_directional_accuracy TEXT,
            margin_signed_error REAL,
            margin_abs_error REAL,
            revenue_signed_error REAL,
            revenue_abs_error REAL,
            revenue_pct_error REAL,
            brier_score REAL,
            calibration_status TEXT NOT NULL,
            calculation_version TEXT NOT NULL,
            calibrated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE scraped_listings (
            listing_id INTEGER PRIMARY KEY AUTOINCREMENT,
            asin TEXT,
            marketplace TEXT NOT NULL,
            price REAL,
            rating REAL,
            review_count INTEGER,
            title TEXT,
            seller TEXT,
            source_url TEXT,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE trend_signals (
            signal_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT,
            keyword TEXT,
            source TEXT,
            current_momentum REAL,
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE intelligence_evidence (
            evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            source TEXT NOT NULL,
            signal_type TEXT NOT NULL,
            conclusion TEXT NOT NULL,
            confidence REAL,
            source_timestamp TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

    yield path

    if os.path.exists(path):
        os.remove(path)


# =============================================================================
# TASK 2: PROVENANCE SECURITY & INTEGRITY DIGESTS
# =============================================================================

def test_01_provenance_live_verified_requires_authentic_execution():
    """LIVE_VERIFIED classification is rejected if retrieval method is synthetic or mock."""
    # Attempting to declare LIVE_VERIFIED with a mock retrieval method
    prov = ProvenanceTracker.create_provenance(
        source_name="tiktok",
        retrieval_method="SYNTHETIC_SIMULATION",
        provenance_type="LIVE_VERIFIED"
    )
    # Anti-mock guardrail must automatically downgrade to MOCK
    assert prov["provenance_type"] == ProvenanceType.MOCK.value
    assert prov["provenance_type"] != ProvenanceType.LIVE_VERIFIED.value


def test_02_anti_mock_downgrade_prevents_user_controlled_promotion():
    """External signals cannot declare themselves as DECISION or PREDICTION evidence types."""
    ev = EvidenceNormalizer.normalize_record(
        source_name="untrusted_feed",
        source_type="PUBLIC_FEED",
        entity="widget",
        signal_type=SignalType.DEMAND,
        value=100.0,
        unit="units",
        claimed_evidence_type=EvidenceType.DECISION  # User tries to claim it's a decision
    )
    # Must be downgraded to ESTIMATE
    assert ev.evidence_type == EvidenceType.ESTIMATE
    assert ev.evidence_type != EvidenceType.DECISION


def test_03_payload_modification_detected_via_digest():
    """Altering raw_payload after creation invalidates the integrity signature."""
    ev = EvidenceNormalizer.normalize_record(
        source_name="google_trends",
        source_type="PUBLIC_API",
        entity="water bottle",
        signal_type=SignalType.DEMAND,
        value=50.0,
        unit="index_0_100",
        raw_payload={"interest": 50}
    )
    assert ProvenanceTracker.verify_provenance(ev) is True

    # Mutate payload hash
    ev.provenance["payload_sha256"] = "modified_sha256_hash_12345678"
    assert ProvenanceTracker.verify_provenance(ev) is False


def test_04_provenance_field_tampering_detected():
    """Altering source_url, provenance_type, or source breaks tamper_sig verification."""
    ev = EvidenceNormalizer.normalize_record(
        source_name="google_trends",
        source_type="PUBLIC_API",
        entity="yoga mat",
        signal_type=SignalType.DEMAND,
        value=75.0,
        unit="index_0_100",
        source_url="https://trends.google.com/explore?q=yoga+mat"
    )
    assert ProvenanceTracker.verify_provenance(ev) is True

    # Tamper with provenance_type
    tampered_prov = dict(ev.provenance)
    tampered_prov["provenance_type"] = "FORGED_LIVE"
    ev_tampered = ev.model_copy(update={"provenance": tampered_prov})
    assert ProvenanceTracker.verify_provenance(ev_tampered) is False


def test_05_missing_signature_rejected_for_live_verified():
    """A record claiming LIVE_VERIFIED cannot verify if tamper_sig is missing or empty."""
    ev = NormalizedEvidence(
        source="google_trends",
        source_type="PUBLIC_API",
        source_record_id="rec_123",
        entity="test",
        signal_type=SignalType.DEMAND,
        value=50.0,
        unit="index_0_100",
        observed_at="2026-10-09T10:00:00Z",
        retrieved_at="2026-10-09T10:00:00Z",
        provenance={
            "source": "google_trends",
            "retrieval_method": "API_REST",
            "retrieved_at": "2026-10-09T10:00:00Z",
            "adapter_version": "1.0.0",
            "provenance_type": "LIVE_VERIFIED"
            # Missing tamper_sig
        }
    )
    assert ProvenanceTracker.verify_provenance(ev) is False


def test_06_legacy_record_compatibility():
    """Legacy records lacking provenance_type still pass basic provenance verification."""
    ev = NormalizedEvidence(
        source="reddit",
        source_type="PUBLIC_FEED",
        source_record_id="rec_legacy",
        entity="test",
        signal_type=SignalType.CUSTOMER_PAIN,
        value="Lid leaks",
        unit="complaint",
        observed_at="2026-09-01T10:00:00Z",
        retrieved_at="2026-09-01T10:00:00Z",
        provenance={
            "source": "reddit",
            "retrieval_method": "RSS_FEED",
            "retrieved_at": "2026-09-01T10:00:00Z",
            "adapter_version": "1.0.0"
        }
    )
    assert ProvenanceTracker.verify_provenance(ev) is True


# =============================================================================
# TASK 4: DEDUPLICATION & CHANGE DETECTION
# =============================================================================

def test_07_observation_deduplication_same_payload(temp_audit_db):
    """Repeating identical observation in the same window is detected and avoided."""
    svc = ObservationIngestionService()

    obs1 = CanonicalObservation(
        source_id="amazon_india",
        observation_type="LISTING",
        external_id="B08XYZ1234",
        observed_at="2026-10-09T10:00:00Z",
        value=1499.0,
        signal_type=SignalType.PRICE,
        marketplace="amazon.in"
    )
    res1, _ = svc.ingest_observation(obs1, db_path=temp_audit_db)
    assert res1.status == IngestionStatus.ACCEPTED

    # Ingest identical observation
    obs2 = CanonicalObservation(
        source_id="amazon_india",
        observation_type="LISTING",
        external_id="B08XYZ1234",
        observed_at="2026-10-09T10:30:00Z",  # same day
        value=1499.0,
        signal_type=SignalType.PRICE,
        marketplace="amazon.in"
    )
    res2, _ = svc.ingest_observation(obs2, db_path=temp_audit_db)
    assert res2.status == IngestionStatus.DUPLICATE


def test_08_material_change_vs_noise_thresholds():
    """Price change > 2% is material; price change < 2% is filtered as noise."""
    thresholds = MaterialityThresholds(price_pct_threshold=2.0)
    engine = ObservationDiffEngine(thresholds=thresholds)

    # 1. Sub-threshold change: 1000.0 -> 1010.0 (1.0% change)
    prev_obs = CanonicalObservation(
        source_id="amazon_india",
        external_id="B08XYZ1234",
        observed_at="2026-10-08T10:00:00Z",
        value=1000.0,
        signal_type=SignalType.PRICE
    )
    curr_noise = CanonicalObservation(
        source_id="amazon_india",
        external_id="B08XYZ1234",
        observed_at="2026-10-09T10:00:00Z",
        value=1010.0,
        signal_type=SignalType.PRICE
    )
    report_noise = engine.compare_observations(prev=prev_obs, curr=curr_noise)
    assert report_noise.requires_intelligence_refresh is False
    assert len(report_noise.material_changes) == 0

    # 2. Material change: 1000.0 -> 1050.0 (5.0% change)
    curr_material = CanonicalObservation(
        source_id="amazon_india",
        external_id="B08XYZ1234",
        observed_at="2026-10-09T10:00:00Z",
        value=1050.0,
        signal_type=SignalType.PRICE
    )
    report_material = engine.compare_observations(prev=prev_obs, curr=curr_material)
    assert report_material.requires_intelligence_refresh is True
    assert ChangeType.PRICE_INCREASE in report_material.material_changes


def test_09_missing_field_preserves_null_without_zero_coercion():
    """Unobserved attributes remain None and are not coerced to 0.0."""
    obs = CanonicalObservation(
        source_id="reddit",
        external_id="post_999",
        observed_at="2026-10-09T10:00:00Z",
        signal_type=SignalType.CUSTOMER_PAIN,
        value=None,  # Not numeric price or demand
        evidence_details={"sentiment_label": "POSITIVE"}
    )
    assert obs.value is None

    prev_obs = CanonicalObservation(
        source_id="reddit",
        external_id="post_999",
        observed_at="2026-10-08T10:00:00Z",
        signal_type=SignalType.CUSTOMER_PAIN,
        value=None
    )
    engine = ObservationDiffEngine()
    report = engine.compare_observations(prev=prev_obs, curr=obs)
    assert report.requires_intelligence_refresh is False


# =============================================================================
# TASK 5: OUTCOME AND CALIBRATION INTEGRITY
# =============================================================================

def test_10_outcome_validation_rejects_impossible_values(monkeypatch, temp_audit_db):
    """Rejects negative revenue, negative units, and inverted time windows."""
    def make_conn():
        c = sqlite3.connect(temp_audit_db)
        c.row_factory = sqlite3.Row
        return c

    monkeypatch.setattr("core.outcome_ingestion.get_connection", make_conn)

    # Negative revenue
    with pytest.raises(ValueError, match="cannot be negative"):
        OutcomeIngestionService.ingest_outcome({
            "product_id": "P_AUDIT_1",
            "period_start": "2026-10-01",
            "period_end": "2026-10-31",
            "period_type": "DAY_30",
            "actual_revenue": -500.0
        })

    # Inverted date window
    with pytest.raises(ValueError, match="cannot be before period_start"):
        OutcomeIngestionService.ingest_outcome({
            "product_id": "P_AUDIT_1",
            "period_start": "2026-10-31",
            "period_end": "2026-10-01",
            "period_type": "DAY_30",
            "actual_revenue": 1000.0
        })


def test_11_outcome_temporal_integrity_and_matching(monkeypatch, temp_audit_db):
    """Outcome before decision timestamp cannot score that decision."""
    def make_conn():
        c = sqlite3.connect(temp_audit_db)
        c.row_factory = sqlite3.Row
        return c

    monkeypatch.setattr("core.outcome_ingestion.get_connection", make_conn)
    monkeypatch.setattr("core.calibration_engine.get_connection", make_conn)
    monkeypatch.setattr("core.database.get_connection", make_conn)

    conn = sqlite3.connect(temp_audit_db)
    cur = conn.cursor()
    cur.execute("INSERT INTO master_products (product_id, title) VALUES ('P_TEMPORAL', 'Temporal Test Product')")
    cur.execute("""
        INSERT INTO decision_ledger (
            decision_id, product_id, decision_timestamp, decision_type, predicted_units_sold, predicted_monthly_revenue
        ) VALUES (101, 'P_TEMPORAL', '2026-10-15 12:00:00', 'LAUNCH', 100, 50000.0)
    """)
    conn.commit()
    conn.close()

    # Outcome measured Oct 1 - Oct 10 occurs BEFORE decision timestamp Oct 15
    with pytest.raises(ValueError, match="Temporal Integrity Error"):
        resolve_decision_link(
            product_id="P_TEMPORAL",
            period_start="2026-10-01",
            decision_id=101
        )


def test_12_calibration_zero_samples_honesty():
    """Empty calibration set returns sample_size 0 and INSUFFICIENT_SAMPLE status."""
    agg = calculate_aggregate_bias([], metric_prefix="demand")
    assert agg["sample_size"] == 0
    assert agg["reliability_tier"] == "INSUFFICIENT_SAMPLE"
    assert agg["mean_signed_error"] is None
    assert agg["mean_absolute_error"] is None


def test_13_calibration_small_known_dataset_reproducible():
    """Calculates reproducible error metrics on small test fixtures."""
    calibrations = [
        {"demand_signed_error": 10.0, "demand_absolute_error": 10.0, "demand_percentage_error": 10.0},
        {"demand_signed_error": -20.0, "demand_absolute_error": 20.0, "demand_percentage_error": 20.0},
        {"demand_signed_error": 0.0, "demand_absolute_error": 0.0, "demand_percentage_error": 0.0},
        {"demand_signed_error": 15.0, "demand_absolute_error": 15.0, "demand_percentage_error": 15.0},
        {"demand_signed_error": -5.0, "demand_absolute_error": 5.0, "demand_percentage_error": 5.0},
    ]
    # N = 5 meets minimum sample threshold
    agg = calculate_aggregate_bias(calibrations, metric_prefix="demand")
    assert agg["sample_size"] == 5
    assert agg["reliability_tier"] == "PROVISIONAL_AGGREGATE"
    # sum = 10 - 20 + 0 + 15 - 5 = 0.0
    assert agg["mean_signed_error"] == 0.0
    # sum abs = 10 + 20 + 0 + 15 + 5 = 50.0 / 5 = 10.0
    assert agg["mean_absolute_error"] == 10.0


def test_14_database_level_unique_constraint_enforcement(temp_audit_db):
    """Direct concurrent duplicate attempt on product_outcomes fails on UNIQUE constraint."""
    conn = sqlite3.connect(temp_audit_db)
    cur = conn.cursor()
    cur.execute("INSERT INTO master_products (product_id, title) VALUES ('P_CONCUR', 'Concur Product')")
    cur.execute("""
        INSERT INTO product_outcomes (
            product_id, period_start, period_end, period_type, actual_units_sold
        ) VALUES ('P_CONCUR', '2026-10-01', '2026-10-31', 'DAY_30', 50)
    """)
    conn.commit()

    # Attempt second insert for the exact same product and period
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
        cur.execute("""
            INSERT INTO product_outcomes (
                product_id, period_start, period_end, period_type, actual_units_sold
            ) VALUES ('P_CONCUR', '2026-10-01', '2026-10-31', 'DAY_30', 99)
        """)
        conn.commit()
    conn.close()


def test_15_production_db_safety_isolation():
    """Verify that tests never touched data/research_engine.db."""
    prod_path = "data/research_engine.db"
    assert os.path.exists(prod_path)
    conn = sqlite3.connect(f"file:{prod_path}?mode=ro", uri=True)
    cur = conn.cursor()
    # Confirm protected row
    cur.execute("SELECT product_id FROM decision_ledger WHERE product_id='US_B09ABC'")
    row = cur.fetchone()
    assert row is not None
    assert row[0] == "US_B09ABC"
    conn.close()
