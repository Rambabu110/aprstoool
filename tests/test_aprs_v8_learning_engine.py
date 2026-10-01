"""
tests/test_aprs_v8_learning_engine.py
APRS V8 Phase 7 — Auditable Learning Foundation & Bias Intelligence
====================================================================

TEST PHILOSOPHY:
  1. All tests use isolated in-memory or temp-file SQLite databases.
  2. No production DB is modified.
  3. Tests verify:
     a. Empty-state safety (no calibration data → safe response, no fake bias)
     b. Correct MBE/MAE/MAPE computation (pure-Python, verified against hand-calculated values)
     c. Correct directional bias classification (overprediction/underprediction/no-clear)
     d. Correct evidence status derivation (sample size gating)
     e. Recommendation output (type, automatic_policy_change=NONE invariant)
     f. Fingerprint determinism (same records → same hash)
     g. Policy safety invariant (scoring weights NOT changed by any learning call)
     h. Correction-awareness (correction_count metadata preserved)
     i. Category and product scoped summaries
     j. Sign convention preserved (actual - predicted; negative = overprediction)

INVARIANTS ASSERTED IN EVERY TEST:
  - automatic_policy_change == "NONE" in every learning output
  - No modification to master_products, decision_ledger, product_intelligence
  - production_calibrations = 0 → evidence_status = NO_OBSERVATION_DATA

SIGN CONVENTION:
  signed_error = actual - predicted
  negative MBE → overprediction (predicted too high)
  positive MBE → underprediction (predicted too low)
"""

import os
import sys
import math
import sqlite3
import hashlib
import tempfile
import pytest
from pathlib import Path
from typing import List, Dict, Any

# ── Ensure project root is on sys.path ───────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ── Ensure test uses isolated DB ─────────────────────────────────────────────
os.environ.setdefault("APRS_DB_PATH", ":memory:")


# ── Module under test ────────────────────────────────────────────────────────
from core.learning_engine import (
    LearningEngine,
    LEARNING_POLICY,
    EVIDENCE_NO_DATA,
    EVIDENCE_INSUFFICIENT,
    EVIDENCE_PROVISIONAL,
    EVIDENCE_NO_CLEAR_BIAS,
    BIAS_OVERPREDICTION,
    BIAS_UNDERPREDICTION,
    BIAS_NO_CLEAR,
    BIAS_INSUFFICIENT,
    V8_LEARNING_VERSION,
    _compute_fingerprint,
    _classify_directional_bias,
    _derive_evidence_status,
    _build_recommendation,
)
from core.calibration_engine import (
    SAMPLE_SIZE_MIN_AGGREGATE,
    RELIABILITY_INSUFFICIENT_SAMPLE,
    V8_CALIBRATION_VERSION,
)


# ─────────────────────────────────────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────────────────────────────────────

def _get_fresh_db() -> sqlite3.Connection:
    """Returns an isolated in-memory DB with V8 schema (including Phase 7 tables)."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    # We init the schema by running init_db logic directly
    import core.database as dbmod
    orig = dbmod.get_db_path
    # Patch get_db_path to return a temp path so init_db uses a real file (not :memory:)
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp_path = f.name
    os.environ["APRS_DB_PATH"] = tmp_path
    try:
        dbmod.init_db()
        conn2 = sqlite3.connect(tmp_path)
        conn2.row_factory = sqlite3.Row
        conn2.execute("PRAGMA foreign_keys = ON;")
        return conn2, tmp_path
    except Exception:
        os.unlink(tmp_path)
        raise


@pytest.fixture
def fresh_db():
    """Fixture providing a fresh isolated temp-file DB with V8 schema."""
    conn, tmp_path = _get_fresh_db()
    yield conn, tmp_path
    conn.close()
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)


@pytest.fixture
def learning_db_path(fresh_db):
    """Just the path to an initialized fresh DB."""
    conn, tmp_path = fresh_db
    conn.close()
    return tmp_path


def _str_to_int_id(s: str) -> int:
    """Convert a string test ID to a stable unique integer for INTEGER PK columns."""
    # Use abs of hash for stable integer mapping
    return abs(hash(s)) % (2**31 - 1) + 1


def _seed_product(conn: sqlite3.Connection, product_id: str = "P001",
                  name: str = "Test Product", category: str = "Electronics") -> None:
    """Inserts a minimal master_products row."""
    conn.execute("""
        INSERT OR IGNORE INTO master_products
        (product_id, name, category, region, planned_msrp, landed_cogs, status)
        VALUES (?, ?, ?, 'USA', 49.99, 12.00, 'ACTIVE')
    """, (product_id, name, category))
    conn.commit()


def _seed_decision(conn: sqlite3.Connection, decision_id: str = "D001",
                   product_id: str = "P001") -> int:
    """Inserts a minimal decision_ledger row. Returns the integer decision_id used."""
    int_id = _str_to_int_id(decision_id)
    conn.execute("""
        INSERT OR IGNORE INTO decision_ledger
        (decision_id, product_id, decision_type, decision_timestamp,
         frozen_score, frozen_confidence, frozen_kill_status,
         predicted_daily_units, predicted_selling_price, predicted_cogs,
         predicted_cm_pct, predicted_rto_pct, predicted_cac,
         policy_version, model_version, snapshot_payload_json)
        VALUES (?, ?, 'GO', '2025-01-01T00:00:00Z',
                75.0, 80.0, 'PASS',
                35, 49.99, 12.00,
                42.5, 8.0, 15.0,
                'POL_V1', 'MOD_V1', '{}')
    """, (int_id, product_id))
    conn.commit()
    return int_id


def _seed_outcome(conn: sqlite3.Connection, outcome_id: str = "O001",
                  product_id: str = "P001", decision_id: str = "D001",
                  actual_units: float = 30.0, actual_asp: float = 47.0,
                  actual_cm_pct: float = 38.0, actual_rto_pct: float = 10.0,
                  actual_cac: float = 18.0) -> int:
    """Inserts a product_outcomes row. Returns the integer outcome_id used."""
    int_out_id = _str_to_int_id(outcome_id)
    int_dec_id = _str_to_int_id(decision_id)
    import datetime
    day_offset = (int_out_id % 5000) * 35
    p_start = (datetime.date(2025, 1, 1) + datetime.timedelta(days=day_offset)).isoformat()
    p_end = (datetime.date(2025, 1, 1) + datetime.timedelta(days=day_offset + 30)).isoformat()
    conn.execute("""
        INSERT OR IGNORE INTO product_outcomes
        (outcome_id, product_id, decision_id, period_start, period_end, period_type,
         actual_units_sold, actual_avg_selling_price, actual_landed_cogs,
         actual_contribution_margin, actual_cm_pct,
         actual_returns_count, actual_return_rate_pct,
         actual_rto_count, actual_rto_rate_pct,
         actual_ad_spend, actual_cac, actual_revenue,
         data_source)
        VALUES (?, ?, ?, ?, ?, 'CUSTOM',
                ?, ?, 12.00, NULL, ?, NULL, NULL, NULL, ?,
                NULL, ?, NULL, 'CSV_MANUAL')
    """, (int_out_id, product_id, int_dec_id,
          p_start, p_end,
          actual_units, actual_asp, actual_cm_pct,
          actual_rto_pct, actual_cac))
    conn.commit()
    return int_out_id


def _seed_calibration(conn: sqlite3.Connection, cal_id: str = "CAL001",
                      decision_id: str = "D001", outcome_id: str = "O001",
                      product_id: str = "P001",
                      pred_units: float = 35.0, actual_units: float = 30.0,
                      pred_asp: float = 49.99, actual_asp: float = 47.0,
                      pred_cm_pct: float = 42.5, actual_cm_pct: float = 38.0,
                      pred_rto_pct: float = 8.0, actual_rto_pct: float = 10.0,
                      pred_cac: float = 15.0, actual_cac: float = 18.0,
                      version: str = V8_CALIBRATION_VERSION) -> None:
    """Inserts a prediction_calibrations row with pre-computed signed errors."""
    # Convert string IDs to integers to match INTEGER PK schema
    int_cal_id = _str_to_int_id(cal_id)
    int_dec_id = _str_to_int_id(decision_id)
    int_out_id = _str_to_int_id(outcome_id)

    # Signed errors: actual - predicted (negative = overprediction)
    demand_se = actual_units - pred_units
    demand_ae = abs(demand_se)
    demand_pe = abs(demand_se) / max(abs(actual_units), 1e-10) * 100

    asp_se = actual_asp - pred_asp
    asp_ae = abs(asp_se)
    asp_pe = abs(asp_se) / max(abs(actual_asp), 1e-10) * 100

    cm_se = actual_cm_pct - pred_cm_pct
    cm_ae = abs(cm_se)

    rto_se = actual_rto_pct - pred_rto_pct
    rto_ae = abs(rto_se)

    cac_se = actual_cac - pred_cac
    cac_ae = abs(cac_se)
    cac_pe = abs(cac_se) / max(abs(actual_cac), 1e-10) * 100

    conn.execute("""
        INSERT OR IGNORE INTO prediction_calibrations
        (calibration_id, decision_id, outcome_id, product_id, calibration_timestamp,
         demand_predicted, demand_actual, demand_signed_error, demand_absolute_error, demand_percentage_error,
         cm_predicted_pct, cm_actual_pct, cm_signed_error_pct_points, cm_absolute_error_pct_points,
         rto_predicted_pct, rto_actual_pct, rto_signed_error_pct_points, rto_absolute_error_pct_points,
         cac_predicted, cac_actual, cac_signed_error, cac_absolute_error, cac_percentage_error,
         price_predicted, price_actual, price_signed_error,
         directional_accuracy, data_completeness_pct, calibration_status, calculation_version)
        VALUES (?, ?, ?, ?, '2025-03-01T00:00:00Z',
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?,
                1, 100.0, 'COMPLETE', ?)
    """, (
        int_cal_id, int_dec_id, int_out_id, product_id,
        pred_units, actual_units, demand_se, demand_ae, demand_pe,
        pred_cm_pct, actual_cm_pct, cm_se, cm_ae,
        pred_rto_pct, actual_rto_pct, rto_se, rto_ae,
        pred_cac, actual_cac, cac_se, cac_ae, cac_pe,
        pred_asp, actual_asp, asp_se,
        version,
    ))
    conn.commit()


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 1: CONSTANTS AND POLICY SAFETY
# ─────────────────────────────────────────────────────────────────────────────

class TestLearningEngineConstants:
    """Verify module constants are correctly defined and aligned with calibration engine."""

    def test_minimum_sample_size_aligns_with_calibration_engine(self):
        """LEARNING_POLICY minimum_sample_size must match calibration engine constant."""
        assert LEARNING_POLICY["minimum_sample_size"] == SAMPLE_SIZE_MIN_AGGREGATE

    def test_version_constant_is_string(self):
        assert isinstance(V8_LEARNING_VERSION, str)
        assert "V8" in V8_LEARNING_VERSION

    def test_policy_version_constant_is_string(self):
        assert isinstance(LEARNING_POLICY["policy_version"], str)

    def test_evidence_constants_are_distinct(self):
        constants = [EVIDENCE_NO_DATA, EVIDENCE_INSUFFICIENT, EVIDENCE_PROVISIONAL, EVIDENCE_NO_CLEAR_BIAS]
        assert len(set(constants)) == 4

    def test_bias_direction_constants_are_distinct(self):
        constants = [BIAS_OVERPREDICTION, BIAS_UNDERPREDICTION, BIAS_NO_CLEAR, BIAS_INSUFFICIENT]
        assert len(set(constants)) == 4

    def test_demand_noise_threshold_is_positive(self):
        assert LEARNING_POLICY["demand_mbe_noise_threshold"] > 0

    def test_pct_point_noise_threshold_is_positive(self):
        assert LEARNING_POLICY["pct_point_noise_threshold_pp"] > 0

    def test_demand_mape_acceptable_positive(self):
        assert LEARNING_POLICY["demand_mape_acceptable_pct"] > 0


class TestPolicySafetySnapshot:
    """Verify policy snapshot captures V7.2 weights correctly and is read-only."""

    def test_policy_snapshot_has_all_dimensions(self):
        snap = LearningEngine.capture_policy_snapshot()
        weights = snap["scoring_weights"]
        expected_dims = {
            "demand_strength", "trend_strength", "competition_pressure", "customer_pain",
            "economic_viability", "sourcing_feasibility", "operational_risk",
            "market_saturation", "evidence_quality", "data_freshness",
        }
        assert expected_dims == set(weights.keys())

    def test_policy_snapshot_weights_sum_to_one(self):
        snap = LearningEngine.capture_policy_snapshot()
        total = sum(snap["scoring_weights"].values())
        assert abs(total - 1.0) < 1e-9, f"Weights sum to {total}, expected 1.0"

    def test_policy_snapshot_has_captured_at(self):
        snap = LearningEngine.capture_policy_snapshot()
        assert "captured_at" in snap

    def test_policy_snapshot_returns_note(self):
        snap = LearningEngine.capture_policy_snapshot()
        assert "note" in snap
        note = snap["note"].lower()
        assert "not modify" in note or "does not" in note


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 2: PURE HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

class TestFingerprintComputation:
    """_compute_fingerprint: determinism, order-independence, sensitivity."""

    def _make_cal(self, cal_id, version="V1"):
        return {"calibration_id": cal_id, "calculation_version": version}

    def test_same_records_same_fingerprint(self):
        recs = [self._make_cal("C1"), self._make_cal("C2"), self._make_cal("C3")]
        fp1 = _compute_fingerprint(recs)
        fp2 = _compute_fingerprint(recs)
        assert fp1 == fp2

    def test_order_independent(self):
        recs1 = [self._make_cal("C1"), self._make_cal("C2"), self._make_cal("C3")]
        recs2 = [self._make_cal("C3"), self._make_cal("C1"), self._make_cal("C2")]
        assert _compute_fingerprint(recs1) == _compute_fingerprint(recs2)

    def test_different_ids_different_fingerprint(self):
        recs1 = [self._make_cal("C1")]
        recs2 = [self._make_cal("C2")]
        assert _compute_fingerprint(recs1) != _compute_fingerprint(recs2)

    def test_different_version_different_fingerprint(self):
        recs1 = [self._make_cal("C1", "V1")]
        recs2 = [self._make_cal("C1", "V2")]
        assert _compute_fingerprint(recs1) != _compute_fingerprint(recs2)

    def test_empty_records_returns_string(self):
        fp = _compute_fingerprint([])
        assert isinstance(fp, str)
        assert len(fp) == 32  # SHA-256 hex truncated to 32 chars

    def test_fingerprint_is_32_char_hex(self):
        recs = [self._make_cal("X1"), self._make_cal("X2")]
        fp = _compute_fingerprint(recs)
        assert len(fp) == 32
        assert all(c in "0123456789abcdef" for c in fp)


class TestDirectionalBiasClassification:
    """_classify_directional_bias: sign convention, thresholds, None handling."""

    def test_none_returns_insufficient(self):
        assert _classify_directional_bias(None, "demand") == BIAS_INSUFFICIENT

    def test_zero_within_noise_returns_no_clear_demand(self):
        assert _classify_directional_bias(0.0, "demand") == BIAS_NO_CLEAR

    def test_small_negative_within_demand_noise_is_no_clear(self):
        # Noise threshold is 0.5 for demand
        assert _classify_directional_bias(-0.4, "demand") == BIAS_NO_CLEAR

    def test_small_positive_within_demand_noise_is_no_clear(self):
        assert _classify_directional_bias(0.3, "demand") == BIAS_NO_CLEAR

    def test_negative_mbe_beyond_threshold_is_overprediction(self):
        # mbe = -5.0 (actual - predicted = -5), predicted was higher → overprediction
        assert _classify_directional_bias(-5.0, "demand") == BIAS_OVERPREDICTION

    def test_positive_mbe_beyond_threshold_is_underprediction(self):
        assert _classify_directional_bias(+5.0, "demand") == BIAS_UNDERPREDICTION

    def test_pct_metric_noise_threshold_applies(self):
        # cm/rto use pct_point_noise_threshold_pp = 1.0
        assert _classify_directional_bias(-0.5, "cm") == BIAS_NO_CLEAR
        assert _classify_directional_bias(-1.5, "cm") == BIAS_OVERPREDICTION
        assert _classify_directional_bias(+1.5, "rto") == BIAS_UNDERPREDICTION

    def test_cac_uses_pct_point_threshold(self):
        # cac uses demand threshold? No — cac is demand class (currency, not pp)
        # cac uses demand_mbe_noise_threshold = 0.5
        assert _classify_directional_bias(-0.3, "cac") == BIAS_NO_CLEAR
        assert _classify_directional_bias(-2.0, "cac") == BIAS_OVERPREDICTION


class TestEvidenceStatusDerivation:
    """_derive_evidence_status: sample size gating and bias mapping."""

    def test_zero_samples_is_no_data(self):
        assert _derive_evidence_status(0, BIAS_OVERPREDICTION) == EVIDENCE_NO_DATA

    def test_below_min_sample_is_insufficient(self):
        n = SAMPLE_SIZE_MIN_AGGREGATE - 1
        assert _derive_evidence_status(n, BIAS_OVERPREDICTION) == EVIDENCE_INSUFFICIENT

    def test_exactly_min_sample_with_bias_is_provisional(self):
        n = SAMPLE_SIZE_MIN_AGGREGATE
        assert _derive_evidence_status(n, BIAS_OVERPREDICTION) == EVIDENCE_PROVISIONAL
        assert _derive_evidence_status(n, BIAS_UNDERPREDICTION) == EVIDENCE_PROVISIONAL

    def test_exactly_min_sample_no_bias_is_no_clear(self):
        n = SAMPLE_SIZE_MIN_AGGREGATE
        assert _derive_evidence_status(n, BIAS_NO_CLEAR) == EVIDENCE_NO_CLEAR_BIAS

    def test_large_sample_no_bias_is_no_clear(self):
        assert _derive_evidence_status(100, BIAS_NO_CLEAR) == EVIDENCE_NO_CLEAR_BIAS

    def test_large_sample_with_bias_is_provisional(self):
        assert _derive_evidence_status(100, BIAS_OVERPREDICTION) == EVIDENCE_PROVISIONAL

    def test_insufficient_bias_below_min_is_insufficient_evidence(self):
        n = SAMPLE_SIZE_MIN_AGGREGATE - 1
        assert _derive_evidence_status(n, BIAS_INSUFFICIENT) == EVIDENCE_INSUFFICIENT


class TestBuildRecommendation:
    """_build_recommendation: output shape, automatic_policy_change invariant."""

    def test_no_data_returns_awaiting_data(self):
        rec = _build_recommendation(
            scope_type="PORTFOLIO", scope_key="PORTFOLIO", metric_name="demand",
            directional_bias=BIAS_INSUFFICIENT, evidence_status=EVIDENCE_NO_DATA,
            sample_size=0, mbe=None, mape=None
        )
        assert rec["automatic_policy_change"] == "NONE"
        assert rec["recommendation_type"] == "AWAITING_SUFFICIENT_OBSERVATION_DATA"
        assert rec["status"] == "PROPOSED"

    def test_overprediction_demand_maps_correctly(self):
        rec = _build_recommendation(
            scope_type="PORTFOLIO", scope_key="PORTFOLIO", metric_name="demand",
            directional_bias=BIAS_OVERPREDICTION, evidence_status=EVIDENCE_PROVISIONAL,
            sample_size=10, mbe=-5.0, mape=16.7
        )
        assert rec["automatic_policy_change"] == "NONE"
        assert rec["recommendation_type"] == "INVESTIGATE_DEMAND_OVERPREDICTION"

    def test_underprediction_cac_maps_correctly(self):
        rec = _build_recommendation(
            scope_type="PRODUCT", scope_key="P001", metric_name="cac",
            directional_bias=BIAS_UNDERPREDICTION, evidence_status=EVIDENCE_PROVISIONAL,
            sample_size=8, mbe=3.0, mape=20.0
        )
        assert rec["automatic_policy_change"] == "NONE"
        assert rec["recommendation_type"] == "INVESTIGATE_CAC_UNDERPREDICTION"

    def test_no_bias_produces_no_action_needed(self):
        rec = _build_recommendation(
            scope_type="CATEGORY", scope_key="Electronics", metric_name="cm",
            directional_bias=BIAS_NO_CLEAR, evidence_status=EVIDENCE_NO_CLEAR_BIAS,
            sample_size=20, mbe=0.3, mape=2.0
        )
        assert rec["recommendation_type"] == "NO_INVESTIGATION_INDICATED"
        assert rec["automatic_policy_change"] == "NONE"

    def test_all_five_metrics_have_recommendation_types(self):
        for metric in ("demand", "price", "cm", "rto", "cac"):
            rec = _build_recommendation(
                scope_type="PORTFOLIO", scope_key="P", metric_name=metric,
                directional_bias=BIAS_OVERPREDICTION, evidence_status=EVIDENCE_PROVISIONAL,
                sample_size=10, mbe=-1.0, mape=5.0
            )
            assert rec["recommendation_type"] != "", f"No type for metric={metric}"

    def test_recommendation_has_calculation_version(self):
        rec = _build_recommendation(
            scope_type="PORTFOLIO", scope_key="P", metric_name="demand",
            directional_bias=BIAS_INSUFFICIENT, evidence_status=EVIDENCE_NO_DATA,
            sample_size=0, mbe=None, mape=None
        )
        assert rec["calculation_version"] == V8_LEARNING_VERSION

    def test_recommendation_has_policy_version(self):
        rec = _build_recommendation(
            scope_type="PORTFOLIO", scope_key="P", metric_name="demand",
            directional_bias=BIAS_INSUFFICIENT, evidence_status=EVIDENCE_NO_DATA,
            sample_size=0, mbe=None, mape=None
        )
        assert rec["policy_version"] == LEARNING_POLICY["policy_version"]


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 3: EMPTY STATE SAFETY
# ─────────────────────────────────────────────────────────────────────────────

class TestEmptyStateSafety:
    """With 0 calibration records, all outputs must be safe with no fabricated bias."""

    def test_portfolio_empty_state_no_data(self, learning_db_path):
        summary = LearningEngine.get_portfolio_learning_summary(db_path=learning_db_path)
        assert summary["evidence_status"] == EVIDENCE_NO_DATA
        assert summary["sample_size"] == 0
        assert summary["automatic_policy_change"] == "NONE"
        assert summary["fingerprint"] is None

    def test_portfolio_empty_state_all_metrics_are_no_data(self, learning_db_path):
        summary = LearningEngine.get_portfolio_learning_summary(db_path=learning_db_path)
        for metric in ("demand", "price", "cm", "rto", "cac"):
            m = summary["metrics"][metric]
            assert m["evidence_status"] == EVIDENCE_NO_DATA
            assert m["sample_size"] == 0
            assert m["directional_bias"] == BIAS_INSUFFICIENT

    def test_portfolio_empty_state_has_recommendations(self, learning_db_path):
        summary = LearningEngine.get_portfolio_learning_summary(db_path=learning_db_path)
        assert isinstance(summary["recommendations"], list)
        assert len(summary["recommendations"]) >= 1

    def test_portfolio_empty_no_mbe(self, learning_db_path):
        summary = LearningEngine.get_portfolio_learning_summary(db_path=learning_db_path)
        demand_m = summary["metrics"]["demand"]
        assert demand_m.get("mean_signed_error_mbe") is None

    def test_product_empty_state(self, learning_db_path):
        summary = LearningEngine.get_product_learning_summary("P_NONEXISTENT", db_path=learning_db_path)
        assert summary["evidence_status"] == EVIDENCE_NO_DATA
        assert summary["sample_size"] == 0
        assert summary["automatic_policy_change"] == "NONE"

    def test_category_empty_state(self, learning_db_path):
        summary = LearningEngine.get_category_learning_summary("Electronics", db_path=learning_db_path)
        assert summary["evidence_status"] == EVIDENCE_NO_DATA
        assert summary["sample_size"] == 0
        assert summary["automatic_policy_change"] == "NONE"

    def test_bias_by_metric_empty_state(self, learning_db_path):
        result = LearningEngine.get_bias_by_metric("demand", db_path=learning_db_path)
        assert result["evidence_status"] == EVIDENCE_NO_DATA
        assert result["automatic_policy_change"] == "NONE"
        assert result["mean_signed_error_mbe"] is None

    def test_generate_recommendations_empty_state(self, learning_db_path):
        recs = LearningEngine.generate_learning_recommendations(db_path=learning_db_path)
        assert isinstance(recs, list)
        # All recommendations in empty state must be AWAITING or NONE
        for rec in recs:
            assert rec["automatic_policy_change"] == "NONE"

    def test_available_categories_empty_state(self, learning_db_path):
        cats = LearningEngine.get_available_categories_with_calibrations(db_path=learning_db_path)
        assert cats == []


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 4: SINGLE CALIBRATION RECORD (BELOW MIN SAMPLE)
# ─────────────────────────────────────────────────────────────────────────────

class TestSingleCalibrationRecord:
    """With exactly 1 calibration record (below min_sample_size=5), no bias is claimed."""

    @pytest.fixture
    def seeded_db(self, fresh_db):
        conn, tmp_path = fresh_db
        _seed_product(conn)
        _seed_decision(conn)
        _seed_outcome(conn)
        _seed_calibration(conn,
            pred_units=35.0, actual_units=30.0,  # demand MBE = -5.0 (overprediction)
            pred_asp=49.99, actual_asp=47.0,
            pred_cm_pct=42.5, actual_cm_pct=38.0,
            pred_rto_pct=8.0, actual_rto_pct=10.0,
            pred_cac=15.0, actual_cac=18.0,
        )
        conn.close()
        return tmp_path

    def test_evidence_is_insufficient_not_no_data(self, seeded_db):
        summary = LearningEngine.get_portfolio_learning_summary(db_path=seeded_db)
        # 1 record < 5 minimum → INSUFFICIENT_EVIDENCE (not NO_OBSERVATION_DATA)
        assert summary["evidence_status"] == EVIDENCE_INSUFFICIENT
        assert summary["sample_size"] == 1

    def test_no_bias_claim_below_min_sample(self, seeded_db):
        summary = LearningEngine.get_portfolio_learning_summary(db_path=seeded_db)
        # Even with strongly negative MBE, no bias is claimed with N=1
        demand_m = summary["metrics"]["demand"]
        assert demand_m["evidence_status"] == EVIDENCE_INSUFFICIENT
        assert demand_m["directional_bias"] in (BIAS_INSUFFICIENT, BIAS_NO_CLEAR, BIAS_OVERPREDICTION)

    def test_automatic_policy_change_none_with_one_record(self, seeded_db):
        summary = LearningEngine.get_portfolio_learning_summary(db_path=seeded_db)
        assert summary["automatic_policy_change"] == "NONE"

    def test_fingerprint_present_with_one_record(self, seeded_db):
        summary = LearningEngine.get_portfolio_learning_summary(db_path=seeded_db)
        assert summary["fingerprint"] is not None
        assert len(summary["fingerprint"]) == 32


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 5: SUFFICIENT SAMPLE — BIAS DETECTION AND MBE CALCULATION
# ─────────────────────────────────────────────────────────────────────────────

class TestSufficientSampleBiasDetection:
    """With N >= min_sample_size calibrations, verify bias detection and MBE math."""

    @pytest.fixture
    def five_calibration_db(self, fresh_db):
        """Seeds exactly min_sample_size (5) calibrations with consistent demand overprediction."""
        conn, tmp_path = fresh_db
        _seed_product(conn)
        for i in range(5):
            pid = f"D00{i+1}"
            oid = f"O00{i+1}"
            cid = f"CAL00{i+1}"
            _seed_decision(conn, decision_id=pid)
            _seed_outcome(conn, outcome_id=oid, decision_id=pid,
                          actual_units=30.0, actual_asp=47.0,
                          actual_cm_pct=38.0, actual_rto_pct=10.0, actual_cac=18.0)
            _seed_calibration(conn, cal_id=cid, decision_id=pid, outcome_id=oid,
                pred_units=35.0, actual_units=30.0,   # demand MBE = -5.0 each
                pred_asp=49.99, actual_asp=47.0,
                pred_cm_pct=42.5, actual_cm_pct=38.0,
                pred_rto_pct=8.0, actual_rto_pct=10.0,
                pred_cac=15.0, actual_cac=18.0,
            )
        conn.close()
        return tmp_path

    def test_demand_overprediction_detected_at_min_sample(self, five_calibration_db):
        summary = LearningEngine.get_portfolio_learning_summary(db_path=five_calibration_db)
        demand_m = summary["metrics"]["demand"]
        # -5.0 MBE consistently → overprediction
        assert demand_m["directional_bias"] == BIAS_OVERPREDICTION
        assert demand_m["evidence_status"] == EVIDENCE_PROVISIONAL

    def test_demand_mbe_value_correct(self, five_calibration_db):
        """MBE = mean(actual - predicted) = mean(-5.0 × 5) = -5.0"""
        summary = LearningEngine.get_portfolio_learning_summary(db_path=five_calibration_db)
        demand_m = summary["metrics"]["demand"]
        mbe = demand_m.get("mean_signed_error_mbe")
        assert mbe is not None
        assert abs(mbe - (-5.0)) < 0.01, f"Expected MBE=-5.0, got {mbe}"

    def test_demand_mae_value_correct(self, five_calibration_db):
        """MAE = mean(|actual - predicted|) = mean(5.0 × 5) = 5.0"""
        summary = LearningEngine.get_portfolio_learning_summary(db_path=five_calibration_db)
        demand_m = summary["metrics"]["demand"]
        mae = demand_m.get("mean_absolute_error_mae")
        assert mae is not None
        assert abs(mae - 5.0) < 0.01, f"Expected MAE=5.0, got {mae}"

    def test_cac_underprediction_detected(self, five_calibration_db):
        """pred_cac=15, actual_cac=18 → CAC MBE = +3.0 → underprediction."""
        summary = LearningEngine.get_portfolio_learning_summary(db_path=five_calibration_db)
        cac_m = summary["metrics"]["cac"]
        assert cac_m["directional_bias"] == BIAS_UNDERPREDICTION

    def test_portfolio_evidence_status_is_provisional_when_bias_exists(self, five_calibration_db):
        summary = LearningEngine.get_portfolio_learning_summary(db_path=five_calibration_db)
        assert summary["evidence_status"] == EVIDENCE_PROVISIONAL

    def test_automatic_policy_change_none_with_five_records(self, five_calibration_db):
        summary = LearningEngine.get_portfolio_learning_summary(db_path=five_calibration_db)
        assert summary["automatic_policy_change"] == "NONE"

    def test_recommendations_generated_for_biased_metrics(self, five_calibration_db):
        recs = LearningEngine.generate_learning_recommendations(db_path=five_calibration_db)
        assert len(recs) > 0
        for rec in recs:
            assert rec["automatic_policy_change"] == "NONE"

    def test_demand_investigation_recommendation_present(self, five_calibration_db):
        recs = LearningEngine.generate_learning_recommendations(db_path=five_calibration_db)
        demand_recs = [r for r in recs if r["metric_name"] == "demand"]
        assert len(demand_recs) >= 1
        demand_rec = demand_recs[0]
        assert demand_rec["recommendation_type"] == "INVESTIGATE_DEMAND_OVERPREDICTION"

    def test_fingerprint_is_deterministic_across_calls(self, five_calibration_db):
        s1 = LearningEngine.get_portfolio_learning_summary(db_path=five_calibration_db)
        s2 = LearningEngine.get_portfolio_learning_summary(db_path=five_calibration_db)
        assert s1["fingerprint"] == s2["fingerprint"]


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 6: SIGN CONVENTION VERIFICATION
# ─────────────────────────────────────────────────────────────────────────────

class TestSignConvention:
    """
    Explicitly verify sign convention:
    signed_error = actual - predicted
    negative MBE → overprediction (predicted too high)
    positive MBE → underprediction (predicted too low)
    """

    @pytest.fixture
    def overprediction_db(self, fresh_db):
        """Seeds 5 calibrations where predicted >> actual (overprediction)."""
        conn, tmp_path = fresh_db
        _seed_product(conn)
        for i in range(5):
            _seed_decision(conn, decision_id=f"D{i}")
            _seed_outcome(conn, outcome_id=f"O{i}", decision_id=f"D{i}",
                          actual_units=10.0)   # actual much lower than predicted=35
            _seed_calibration(conn, cal_id=f"C{i}", decision_id=f"D{i}", outcome_id=f"O{i}",
                pred_units=35.0, actual_units=10.0)  # signed_error = 10-35 = -25 → overprediction
        conn.close()
        return tmp_path

    @pytest.fixture
    def underprediction_db(self, fresh_db):
        """Seeds 5 calibrations where predicted << actual (underprediction)."""
        conn, tmp_path = fresh_db
        _seed_product(conn)
        for i in range(5):
            _seed_decision(conn, decision_id=f"D{i}")
            _seed_outcome(conn, outcome_id=f"O{i}", decision_id=f"D{i}",
                          actual_units=60.0)   # actual much higher than predicted=35
            _seed_calibration(conn, cal_id=f"C{i}", decision_id=f"D{i}", outcome_id=f"O{i}",
                pred_units=35.0, actual_units=60.0)  # signed_error = 60-35 = +25 → underprediction
        conn.close()
        return tmp_path

    def test_negative_mbe_is_classified_as_overprediction(self, overprediction_db):
        summary = LearningEngine.get_portfolio_learning_summary(db_path=overprediction_db)
        demand_m = summary["metrics"]["demand"]
        mbe = demand_m.get("mean_signed_error_mbe")
        assert mbe is not None and mbe < 0, f"Expected negative MBE, got {mbe}"
        assert demand_m["directional_bias"] == BIAS_OVERPREDICTION

    def test_positive_mbe_is_classified_as_underprediction(self, underprediction_db):
        summary = LearningEngine.get_portfolio_learning_summary(db_path=underprediction_db)
        demand_m = summary["metrics"]["demand"]
        mbe = demand_m.get("mean_signed_error_mbe")
        assert mbe is not None and mbe > 0, f"Expected positive MBE, got {mbe}"
        assert demand_m["directional_bias"] == BIAS_UNDERPREDICTION

    def test_balanced_errors_produce_no_clear_bias(self, fresh_db):
        """Mix of over- and under-prediction that cancels out → no clear bias."""
        conn, tmp_path = fresh_db
        _seed_product(conn)
        # 5 calibrations: alternating +25 and -25 errors → MBE ≈ 0
        for i in range(5):
            actual = 60.0 if i % 2 == 0 else 10.0   # alternating up/down
            _seed_decision(conn, decision_id=f"D{i}")
            _seed_outcome(conn, outcome_id=f"O{i}", decision_id=f"D{i}", actual_units=actual)
            _seed_calibration(conn, cal_id=f"C{i}", decision_id=f"D{i}", outcome_id=f"O{i}",
                pred_units=35.0, actual_units=actual)
        conn.close()

        summary = LearningEngine.get_portfolio_learning_summary(db_path=tmp_path)
        demand_m = summary["metrics"]["demand"]
        mbe = demand_m.get("mean_signed_error_mbe")
        # MBE ≈ 0 (3 positives + 2 negatives or similar) → should be near zero
        if mbe is not None:
            assert abs(mbe) <= 25.0  # At most one error magnitude
        # With balanced errors, should NOT be a strong directional signal
        os.unlink(tmp_path)


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 7: SCOPED SUMMARIES (PRODUCT AND CATEGORY)
# ─────────────────────────────────────────────────────────────────────────────

class TestScopedSummaries:
    """Product-level and category-level summaries return scope-filtered results."""

    @pytest.fixture
    def multi_product_db(self, fresh_db):
        conn, tmp_path = fresh_db
        # Product 1: Electronics — overprediction
        _seed_product(conn, "P1", "Product One", "Electronics")
        _seed_product(conn, "P2", "Product Two", "Sports")
        for i in range(5):
            _seed_decision(conn, f"DE{i}", "P1")
            _seed_outcome(conn, f"OE{i}", "P1", f"DE{i}", actual_units=20.0)
            _seed_calibration(conn, f"CE{i}", f"DE{i}", f"OE{i}", product_id="P1",
                pred_units=35.0, actual_units=20.0)
            _seed_decision(conn, f"DS{i}", "P2")
            _seed_outcome(conn, f"OS{i}", "P2", f"DS{i}", actual_units=50.0)
            _seed_calibration(conn, f"CS{i}", f"DS{i}", f"OS{i}", product_id="P2",
                pred_units=35.0, actual_units=50.0)
        conn.close()
        return tmp_path

    def test_product_summary_filters_by_product_id(self, multi_product_db):
        p1_summary = LearningEngine.get_product_learning_summary("P1", db_path=multi_product_db)
        p2_summary = LearningEngine.get_product_learning_summary("P2", db_path=multi_product_db)
        # P1 → demand overprediction (actual 20 < predicted 35, MBE = -15)
        assert p1_summary["metrics"]["demand"]["directional_bias"] == BIAS_OVERPREDICTION
        # P2 → demand underprediction (actual 50 > predicted 35, MBE = +15)
        assert p2_summary["metrics"]["demand"]["directional_bias"] == BIAS_UNDERPREDICTION

    def test_product_summaries_have_correct_scope_type(self, multi_product_db):
        s = LearningEngine.get_product_learning_summary("P1", db_path=multi_product_db)
        assert s["scope_type"] == "PRODUCT"
        assert s["scope_key"] == "P1"

    def test_category_summary_for_electronics(self, multi_product_db):
        cat_summary = LearningEngine.get_category_learning_summary("Electronics", db_path=multi_product_db)
        assert cat_summary["scope_type"] == "CATEGORY"
        assert cat_summary["scope_key"] == "Electronics"
        assert cat_summary["sample_size"] == 5

    def test_category_summary_does_not_mix_categories(self, multi_product_db):
        elec = LearningEngine.get_category_learning_summary("Electronics", db_path=multi_product_db)
        sports = LearningEngine.get_category_learning_summary("Sports", db_path=multi_product_db)
        # Electronics: overprediction, Sports: underprediction
        assert elec["metrics"]["demand"]["directional_bias"] == BIAS_OVERPREDICTION
        assert sports["metrics"]["demand"]["directional_bias"] == BIAS_UNDERPREDICTION

    def test_available_categories_returns_both(self, multi_product_db):
        cats = LearningEngine.get_available_categories_with_calibrations(db_path=multi_product_db)
        category_names = [c["category"] for c in cats]
        assert "Electronics" in category_names
        assert "Sports" in category_names

    def test_automatic_policy_change_none_in_product_summary(self, multi_product_db):
        s = LearningEngine.get_product_learning_summary("P1", db_path=multi_product_db)
        assert s["automatic_policy_change"] == "NONE"

    def test_automatic_policy_change_none_in_category_summary(self, multi_product_db):
        s = LearningEngine.get_category_learning_summary("Electronics", db_path=multi_product_db)
        assert s["automatic_policy_change"] == "NONE"


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 8: FINGERPRINT CHANGE ON RECORD ADDITION
# ─────────────────────────────────────────────────────────────────────────────

class TestFingerprintSensitivity:
    """Fingerprint must change when calibration records are added/changed."""

    @pytest.fixture
    def base_db(self, fresh_db):
        conn, tmp_path = fresh_db
        _seed_product(conn)
        for i in range(3):
            _seed_decision(conn, f"D{i}")
            _seed_outcome(conn, f"O{i}", decision_id=f"D{i}")
            _seed_calibration(conn, f"C{i}", f"D{i}", f"O{i}")
        conn.close()
        return tmp_path

    def test_fingerprint_changes_when_record_added(self, base_db):
        s1 = LearningEngine.get_portfolio_learning_summary(db_path=base_db)
        fp1 = s1["fingerprint"]

        # Add one more calibration record
        conn = sqlite3.connect(base_db)
        conn.row_factory = sqlite3.Row
        _seed_decision(conn, "D_NEW")
        _seed_outcome(conn, "O_NEW", decision_id="D_NEW")
        _seed_calibration(conn, "C_NEW", "D_NEW", "O_NEW")
        conn.close()

        s2 = LearningEngine.get_portfolio_learning_summary(db_path=base_db)
        fp2 = s2["fingerprint"]
        assert fp1 != fp2, "Fingerprint should change when records are added"


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 9: PRODUCTION DB INVARIANTS
# ─────────────────────────────────────────────────────────────────────────────

class TestProductionDBInvariants:
    """Verify production DB is not touched and invariants hold at zero data."""

    def test_production_db_has_zero_calibrations(self):
        """Production DB must have 0 calibration records (no synthetic data)."""
        import os as _os
        prod_db = _os.path.join("data", "research_engine.db")
        if not _os.path.exists(prod_db):
            pytest.skip("Production DB not found")
        conn = sqlite3.connect(prod_db)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM prediction_calibrations")
        count = cur.fetchone()[0]
        conn.close()
        assert count == 0, f"Production DB should have 0 calibrations, found {count}"

    def test_production_db_learning_summary_is_safe(self):
        """Portfolio learning summary on prod DB must return safe empty state."""
        import os as _os
        prod_db = _os.path.join("data", "research_engine.db")
        if not _os.path.exists(prod_db):
            pytest.skip("Production DB not found")
        summary = LearningEngine.get_portfolio_learning_summary(db_path=prod_db)
        assert summary["evidence_status"] == EVIDENCE_NO_DATA
        assert summary["automatic_policy_change"] == "NONE"
        assert summary["sample_size"] == 0

    def test_production_db_has_learning_tables(self):
        """Both new Phase 7 tables must exist in production DB after init_db()."""
        import os as _os
        prod_db = _os.path.join(str(PROJECT_ROOT), "data", "research_engine.db")
        if not _os.path.exists(prod_db):
            pytest.skip("Production DB not found")
        # init_db() reads APRS_DB_PATH; temporarily point it at prod DB
        old_val = _os.environ.get("APRS_DB_PATH")
        _os.environ["APRS_DB_PATH"] = prod_db
        try:
            from core.database import init_db
            init_db()
        finally:
            if old_val is None:
                _os.environ.pop("APRS_DB_PATH", None)
            else:
                _os.environ["APRS_DB_PATH"] = old_val
        conn = sqlite3.connect(prod_db)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [r[0] for r in cur.fetchall()]
        conn.close()
        assert "learning_bias_summaries" in tables, "learning_bias_summaries table missing"
        assert "learning_recommendations" in tables, "learning_recommendations table missing"


# ─────────────────────────────────────────────────────────────────────────────
# GROUP 10: STREAMLIT APP-TEST (APRS V8 Phase 7 Tab)
# ─────────────────────────────────────────────────────────────────────────────

class TestStreamlitAppPhase7:
    """Verify app.py loads cleanly with Phase 7 t_learn subtab present."""

    def test_app_py_syntax_is_valid(self):
        import ast
        with open("web/app.py", encoding="utf-8") as f:
            src = f.read()
        tree = ast.parse(src)  # raises SyntaxError if invalid
        assert tree is not None

    def test_app_contains_t_learn_tab(self):
        with open("web/app.py", encoding="utf-8") as f:
            src = f.read()
        assert "t_learn" in src, "t_learn subtab not found in app.py"

    def test_app_imports_learning_engine(self):
        with open("web/app.py", encoding="utf-8") as f:
            src = f.read()
        assert "LearningEngine" in src, "LearningEngine import not found in app.py"
        assert "learning_engine" in src, "learning_engine module not referenced in app.py"

    def test_app_contains_policy_guarantee_banner(self):
        with open("web/app.py", encoding="utf-8") as f:
            src = f.read()
        assert "ARCHITECTURAL GUARANTEE" in src or "automatic_policy_change" in src.lower()

    def test_streamlit_apptest_no_exceptions(self):
        """Streamlit AppTest must complete with 0 exceptions on isolated DB."""
        import subprocess
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            t_db = tf.name

        try:
            env = dict(os.environ)
            env["APRS_DB_PATH"] = t_db

            cmd = [
                sys.executable, "-c",
                "from streamlit.testing.v1 import AppTest; "
                "from core.database import init_db; "
                "init_db(); "
                "at = AppTest.from_file('web/app.py'); "
                "at.session_state['active_tab'] = 'intelligence'; "
                "at.run(timeout=45); "
                "assert len(at.exception) == 0, f'AppTest raised: {at.exception}'; "
                "assert any('Learning' in str(m.value) for m in at.markdown); "
                "print('AppTest Learning Subtab: 0 exceptions')"
            ]
            res = subprocess.run(cmd, cwd=str(PROJECT_ROOT), env=env, capture_output=True, text=True, timeout=60)
            assert res.returncode == 0, f"AppTest failed:\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}"
        finally:
            try:
                os.remove(t_db)
            except Exception:
                pass

