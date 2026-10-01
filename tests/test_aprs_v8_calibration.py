"""
APRS V8 Phase 2 — Prediction Calibration & Error Engine Test Suite
===================================================================
Forensic validation of:
1. Pure mathematical error functions (signed, absolute, percentage, percentage-point)
2. Zero-prediction safety (no division by zero; NULL returned; zero actual -> -100%)
3. NULL propagation (NULL remains NULL; no false zeroes)
4. Directional accuracy classification (UNDERPREDICTED, OVERPREDICTED, EXACT, UNKNOWN)
5. Metric calibrations: Demand, Contribution Margin (pp), RTO (pp), CAC, Selling Price
6. Data completeness % & Calibration status (CALIBRATED, PARTIAL_DATA, INSUFFICIENT_DATA, etc.)
7. Decision-to-outcome matching & strict temporal integrity (rejecting future decisions)
8. Ambiguity prevention (multiple candidate decisions -> NO_UNAMBIGUOUS_DECISION)
9. Idempotency & database persistence (UNIQUE constraint, no duplicates)
10. Sample-size safeguards (N < 5 INSUFFICIENT_SAMPLE vs N >= 5 PROVISIONAL_AGGREGATE)
11. Aggregate bias calculations (Mean Signed Error / MBE, MAE, MAPE with undefined percentage exclusions)
12. Schema migrations, index existence, foreign key cascades, and zero FK violations.
"""

import unittest
import os
import sys
import tempfile
import sqlite3
import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.database import (
    init_db,
    get_connection,
    record_product_evaluation,
    save_product_intelligence,
    record_decision_snapshot,
    get_decision_snapshot,
    record_product_outcome,
    get_outcome_by_id,
    save_prediction_calibration,
    get_calibration_by_id,
    get_calibrations_for_product,
    get_all_calibrations
)

from core.calibration_engine import (
    V8_CALIBRATION_VERSION,
    DIRECTION_UNDERPREDICTED,
    DIRECTION_OVERPREDICTED,
    DIRECTION_EXACT,
    DIRECTION_UNKNOWN,
    STATUS_CALIBRATED,
    STATUS_PARTIAL_DATA,
    STATUS_INSUFFICIENT_DATA,
    STATUS_NO_MATCHING_DECISION,
    STATUS_NO_UNAMBIGUOUS_DECISION,
    STATUS_TEMPORAL_MISMATCH,
    STATUS_INVALID_INPUT,
    STATUS_NOT_CALCULABLE,
    SAMPLE_SIZE_MIN_AGGREGATE,
    RELIABILITY_INSUFFICIENT_SAMPLE,
    RELIABILITY_PROVISIONAL_AGGREGATE,
    calculate_signed_error,
    calculate_absolute_error,
    calculate_percentage_error,
    calculate_percentage_point_error,
    classify_prediction_direction,
    calculate_data_completeness,
    calculate_prediction_calibration,
    match_decision_for_outcome,
    calculate_aggregate_bias,
    calibrate_outcome,
    calibrate_all_uncalibrated_outcomes,
    get_calibration_summary_for_product
)


class TestAPRSV8CalibrationEngine(unittest.TestCase):

    def setUp(self):
        # Create an isolated temporary SQLite database for each test
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_v8_calibration.db"
        os.environ["APRS_DB_PATH"] = str(self.db_path)
        init_db()
        self.conn = get_connection()

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    def _create_dummy_product(self, product_id="PROD_CALIB_001", name="Wireless Smart Lamp", msrp=1299.0, cogs=350.0):
        """Helper to create a valid master product."""
        prod = {
            "id": product_id,
            "name": name,
            "category": "Home & Kitchen",
            "region": "India",
            "retail_msrp": msrp,
            "factory_cogs": cogs,
            "est_cac": 120.0,
            "bsr_rank": 450,
            "estimated_daily_units": 20,
            "ad_active_days": 14,
            "sourcing_hub": "Surat Cluster",
            "marketplace_url": f"https://www.amazon.in/dp/{product_id}",
            "competitor_flaw": "Weak mist",
            "upgrade_v2": "Ultrasonic dual-nozzle",
            "suppliers": []
        }
        econ = {
            "status": "PASS",
            "score": 88.0,
            "landed_cogs": cogs,
            "gross_margin_pct": 73.0,
            "net_profit_pct": 28.5,
            "worst_case_stress_margin_pct": 14.2,
            "consensus_status": "CONSENSUS_PASS",
            "action_plan": "Proceed to sourcing"
        }
        record_product_evaluation(prod, econ)
        return product_id

    # -------------------------------------------------------------
    # 1. PURE MATHEMATICAL ERROR FUNCTIONS & DEMAND CALCULATIONS
    # -------------------------------------------------------------

    def test_demand_exact_prediction(self):
        """Exact prediction (actual == predicted) yields signed 0, abs 0, pct 0, direction EXACT."""
        pred = 20
        act = 20
        signed = calculate_signed_error(act, pred)
        absolute = calculate_absolute_error(act, pred)
        pct = calculate_percentage_error(act, pred)
        direction = classify_prediction_direction(act, pred)

        self.assertEqual(signed, 0.0)
        self.assertEqual(absolute, 0.0)
        self.assertEqual(pct, 0.0)
        self.assertEqual(direction, DIRECTION_EXACT)

    def test_demand_overprediction(self):
        """
        Overprediction: APRS predicted 20, actual was 14.
        Signed error: 14 - 20 = -6.0.
        Absolute error: 6.0.
        Percentage error: ((14 - 20) / 20) * 100 = -30.0%.
        Direction: OVERPREDICTED.
        """
        pred = 20
        act = 14
        signed = calculate_signed_error(act, pred)
        absolute = calculate_absolute_error(act, pred)
        pct = calculate_percentage_error(act, pred)
        direction = classify_prediction_direction(act, pred)

        self.assertEqual(signed, -6.0)
        self.assertEqual(absolute, 6.0)
        self.assertEqual(pct, -30.0)
        self.assertEqual(direction, DIRECTION_OVERPREDICTED)

    def test_demand_underprediction(self):
        """
        Underprediction: APRS predicted 15, actual was 21.
        Signed error: 21 - 15 = +6.0.
        Absolute error: 6.0.
        Percentage error: ((21 - 15) / 15) * 100 = +40.0%.
        Direction: UNDERPREDICTED.
        """
        pred = 15
        act = 21
        signed = calculate_signed_error(act, pred)
        absolute = calculate_absolute_error(act, pred)
        pct = calculate_percentage_error(act, pred)
        direction = classify_prediction_direction(act, pred)

        self.assertEqual(signed, 6.0)
        self.assertEqual(absolute, 6.0)
        self.assertEqual(pct, 40.0)
        self.assertEqual(direction, DIRECTION_UNDERPREDICTED)

    def test_signed_error_convention(self):
        """Signed error must strictly follow actual - predicted; negative = overprediction, positive = underprediction."""
        self.assertEqual(calculate_signed_error(10, 15), -5.0)
        self.assertEqual(calculate_signed_error(15, 10), 5.0)
        self.assertEqual(calculate_signed_error(0, 5), -5.0)
        self.assertEqual(calculate_signed_error(5, 0), 5.0)

    def test_absolute_error_magnitude(self):
        """Absolute error must always be non-negative."""
        self.assertEqual(calculate_absolute_error(10, 15), 5.0)
        self.assertEqual(calculate_absolute_error(15, 10), 5.0)
        self.assertEqual(calculate_absolute_error(0, 0), 0.0)

    # -------------------------------------------------------------
    # 2. ZERO-PREDICTION & ZERO-ACTUAL SAFETY
    # -------------------------------------------------------------

    def test_zero_actual_observation(self):
        """
        Zero actual with positive prediction:
        Predicted = 10, Actual = 0.
        Signed = 0 - 10 = -10.0.
        Absolute = 10.0.
        Percentage = ((0 - 10) / 10) * 100 = -100.0%.
        Zero actual is a genuine, valid commercial observation.
        """
        pred = 10
        act = 0
        signed = calculate_signed_error(act, pred)
        absolute = calculate_absolute_error(act, pred)
        pct = calculate_percentage_error(act, pred)
        direction = classify_prediction_direction(act, pred)

        self.assertEqual(signed, -10.0)
        self.assertEqual(absolute, 10.0)
        self.assertEqual(pct, -100.0)
        self.assertEqual(direction, DIRECTION_OVERPREDICTED)

    def test_zero_prediction_safety_with_positive_actual(self):
        """
        CRITICAL: If predicted = 0 and actual = 5:
        Signed error = +5.
        Absolute error = 5.
        Percentage error = None (NULL).
        DO NOT divide by zero or fabricate an arbitrary percentage.
        """
        pred = 0
        act = 5
        signed = calculate_signed_error(act, pred)
        absolute = calculate_absolute_error(act, pred)
        pct = calculate_percentage_error(act, pred)
        direction = classify_prediction_direction(act, pred)

        self.assertEqual(signed, 5.0)
        self.assertEqual(absolute, 5.0)
        self.assertIsNone(pct)  # Strictly None / NULL
        self.assertEqual(direction, DIRECTION_UNDERPREDICTED)

    def test_zero_prediction_and_zero_actual(self):
        """
        Both predicted and actual are zero:
        Signed = 0.0, Absolute = 0.0, Percentage = None (denominator is zero).
        Direction = EXACT.
        """
        pred = 0
        act = 0
        signed = calculate_signed_error(act, pred)
        absolute = calculate_absolute_error(act, pred)
        pct = calculate_percentage_error(act, pred)
        direction = classify_prediction_direction(act, pred)

        self.assertEqual(signed, 0.0)
        self.assertEqual(absolute, 0.0)
        self.assertIsNone(pct)
        self.assertEqual(direction, DIRECTION_EXACT)

    # -------------------------------------------------------------
    # 3. NULL HANDLING & UNKNOWN SEMANTICS
    # -------------------------------------------------------------

    def test_null_prediction_remains_null(self):
        """If predicted is None, all errors must be None and direction UNKNOWN."""
        act = 14
        pred = None
        self.assertIsNone(calculate_signed_error(act, pred))
        self.assertIsNone(calculate_absolute_error(act, pred))
        self.assertIsNone(calculate_percentage_error(act, pred))
        self.assertEqual(classify_prediction_direction(act, pred), DIRECTION_UNKNOWN)

    def test_null_actual_remains_null(self):
        """If actual is None, all errors must be None and direction UNKNOWN."""
        act = None
        pred = 20
        self.assertIsNone(calculate_signed_error(act, pred))
        self.assertIsNone(calculate_absolute_error(act, pred))
        self.assertIsNone(calculate_percentage_error(act, pred))
        self.assertEqual(classify_prediction_direction(act, pred), DIRECTION_UNKNOWN)

    def test_both_null_remains_null(self):
        """If both are None, all errors must be None and direction UNKNOWN."""
        self.assertIsNone(calculate_signed_error(None, None))
        self.assertIsNone(calculate_absolute_error(None, None))
        self.assertIsNone(calculate_percentage_error(None, None))
        self.assertEqual(classify_prediction_direction(None, None), DIRECTION_UNKNOWN)

    # -------------------------------------------------------------
    # 4. CONTRIBUTION MARGIN (CM) CALIBRATION
    # -------------------------------------------------------------

    def test_cm_percentage_point_error_overprediction(self):
        """
        Predicted CM = 25.0%, Actual CM = 21.0%.
        Signed CM error: 21.0 - 25.0 = -4.0 percentage points.
        Absolute CM error: 4.0 percentage points.
        """
        pred_cm = 25.0
        act_cm = 21.0
        signed_pp, abs_pp = calculate_percentage_point_error(act_cm, pred_cm)
        self.assertEqual(signed_pp, -4.0)
        self.assertEqual(abs_pp, 4.0)

    def test_cm_percentage_point_error_underprediction(self):
        """
        Predicted CM = 20.0%, Actual CM = 28.5%.
        Signed CM error: 28.5 - 20.0 = +8.5 percentage points.
        Absolute CM error: 8.5 percentage points.
        """
        pred_cm = 20.0
        act_cm = 28.5
        signed_pp, abs_pp = calculate_percentage_point_error(act_cm, pred_cm)
        self.assertEqual(signed_pp, 8.5)
        self.assertEqual(abs_pp, 8.5)

    def test_cm_null_handling(self):
        """CM error with missing values must return (None, None)."""
        self.assertEqual(calculate_percentage_point_error(None, 25.0), (None, None))
        self.assertEqual(calculate_percentage_point_error(21.0, None), (None, None))
        self.assertEqual(calculate_percentage_point_error(None, None), (None, None))

    # -------------------------------------------------------------
    # 5. RTO CALIBRATION
    # -------------------------------------------------------------

    def test_rto_percentage_point_error(self):
        """
        Predicted RTO = 8.0%, Actual RTO = 12.0%.
        Signed error: 12.0 - 8.0 = +4.0 percentage points (underestimated RTO risk).
        Absolute error: 4.0 percentage points.
        """
        pred_rto = 8.0
        act_rto = 12.0
        signed_pp, abs_pp = calculate_percentage_point_error(act_rto, pred_rto)
        self.assertEqual(signed_pp, 4.0)
        self.assertEqual(abs_pp, 4.0)

    def test_rto_null_handling(self):
        """RTO error with missing values returns (None, None)."""
        self.assertEqual(calculate_percentage_point_error(None, 8.0), (None, None))
        self.assertEqual(calculate_percentage_point_error(12.0, None), (None, None))

    # -------------------------------------------------------------
    # 6. CAC CALIBRATION
    # -------------------------------------------------------------

    def test_cac_error_calculations(self):
        """
        Predicted CAC = 120.0, Actual CAC = 150.0.
        Signed error: 150.0 - 120.0 = +30.0.
        Absolute error: 30.0.
        Percentage error: ((150 - 120) / 120) * 100 = +25.0%.
        """
        pred_cac = 120.0
        act_cac = 150.0
        self.assertEqual(calculate_signed_error(act_cac, pred_cac), 30.0)
        self.assertEqual(calculate_absolute_error(act_cac, pred_cac), 30.0)
        self.assertEqual(calculate_percentage_error(act_cac, pred_cac), 25.0)

    def test_cac_predicted_zero_safety(self):
        """If predicted CAC is 0.0, percentage error must be None."""
        self.assertEqual(calculate_signed_error(50.0, 0.0), 50.0)
        self.assertEqual(calculate_absolute_error(50.0, 0.0), 50.0)
        self.assertIsNone(calculate_percentage_error(50.0, 0.0))

    def test_cac_null_handling(self):
        """Missing CAC values return None."""
        self.assertIsNone(calculate_signed_error(None, 120.0))
        self.assertIsNone(calculate_signed_error(150.0, None))

    # -------------------------------------------------------------
    # 7. DATA COMPLETENESS & CALIBRATION STATUS
    # -------------------------------------------------------------

    def test_data_completeness_full_calibrated(self):
        """When all 4 core predicted metrics have actual observations, completeness is 100% and status is CALIBRATED."""
        decision = {
            "decision_id": 1,
            "product_id": "P1",
            "predicted_daily_units": 20,
            "predicted_cm_pct": 25.0,
            "predicted_rto_pct": 8.0,
            "predicted_cac": 120.0,
            "predicted_selling_price": 999.0
        }
        outcome = {
            "outcome_id": 1,
            "product_id": "P1",
            "period_start": "2026-08-01",
            "period_end": "2026-08-31",
            "actual_units_sold": 450,
            "actual_cm_pct": 22.0,
            "actual_rto_rate_pct": 10.0,
            "actual_cac": 130.0,
            "actual_avg_selling_price": 999.0
        }
        calib = calculate_prediction_calibration(decision, outcome)
        self.assertEqual(calib["data_completeness_pct"], 100.0)
        self.assertEqual(calib["calibration_status"], STATUS_CALIBRATED)
        self.assertIsNotNone(calib["demand_signed_error"])
        self.assertIsNotNone(calib["cm_signed_error_pct_points"])
        self.assertIsNotNone(calib["rto_signed_error_pct_points"])
        self.assertIsNotNone(calib["cac_signed_error"])

    def test_data_completeness_partial_data(self):
        """
        When 4 metrics are predicted, but CAC is missing in the outcome:
        Completeness is 3 / 4 = 75.0% and status is PARTIAL_DATA.
        """
        decision = {
            "decision_id": 1,
            "product_id": "P1",
            "predicted_daily_units": 20,
            "predicted_cm_pct": 25.0,
            "predicted_rto_pct": 8.0,
            "predicted_cac": 120.0
        }
        outcome = {
            "outcome_id": 1,
            "product_id": "P1",
            "period_start": "2026-08-01",
            "period_end": "2026-08-31",
            "actual_units_sold": 450,
            "actual_cm_pct": 22.0,
            "actual_rto_rate_pct": 10.0,
            "actual_cac": None  # Missing
        }
        calib = calculate_prediction_calibration(decision, outcome)
        self.assertEqual(calib["data_completeness_pct"], 75.0)
        self.assertEqual(calib["calibration_status"], STATUS_PARTIAL_DATA)
        self.assertIsNone(calib["cac_signed_error"])
        self.assertIsNone(calib["cac_percentage_error"])

    def test_data_completeness_insufficient_data(self):
        """When predictions exist but zero actuals are available in outcome, status is INSUFFICIENT_DATA."""
        decision = {
            "decision_id": 1,
            "product_id": "P1",
            "predicted_daily_units": 20,
            "predicted_cm_pct": 25.0
        }
        outcome = {
            "outcome_id": 1,
            "product_id": "P1",
            "period_start": "2026-08-01",
            "period_end": "2026-08-31",
            "actual_units_sold": None,
            "actual_cm_pct": None
        }
        calib = calculate_prediction_calibration(decision, outcome)
        self.assertEqual(calib["data_completeness_pct"], 0.0)
        self.assertEqual(calib["calibration_status"], STATUS_INSUFFICIENT_DATA)

    def test_data_completeness_not_calculable_when_no_predictions(self):
        """When decision has zero predictions, completeness is 0.0% and status is NOT_CALCULABLE."""
        decision = {
            "decision_id": 1,
            "product_id": "P1",
            "predicted_daily_units": None,
            "predicted_cm_pct": None,
            "predicted_rto_pct": None,
            "predicted_cac": None
        }
        outcome = {
            "outcome_id": 1,
            "product_id": "P1",
            "actual_units_sold": 100
        }
        calib = calculate_prediction_calibration(decision, outcome)
        self.assertEqual(calib["data_completeness_pct"], 0.0)
        self.assertEqual(calib["calibration_status"], STATUS_NOT_CALCULABLE)

    # -------------------------------------------------------------
    # 8. OUTCOME-TO-DECISION MATCHING & TEMPORAL INTEGRITY
    # -------------------------------------------------------------

    def test_explicit_decision_matching_success(self):
        """Outcome with valid decision_id matches correctly when decision occurred prior to period_start."""
        pid = self._create_dummy_product("PROD_MATCH_001")
        # Freeze decision with prior timestamp
        dec_id = record_decision_snapshot(pid, decision_timestamp="2026-07-15 10:00:00")

        outcome = {
            "product_id": pid,
            "decision_id": dec_id,
            "period_start": "2026-08-01",
            "period_end": "2026-08-31",
            "period_type": "DAY_30",
            "actual_units_sold": 300
        }
        res = record_product_outcome(outcome)
        saved_out = get_outcome_by_id(res["outcome_id"])

        matched_dec, status, note = match_decision_for_outcome(saved_out)
        self.assertIsNotNone(matched_dec)
        self.assertEqual(matched_dec["decision_id"], dec_id)
        self.assertEqual(status, STATUS_CALIBRATED)

    def test_explicit_decision_matching_nonexistent_decision(self):
        """Outcome linking to non-existent decision_id returns NO_MATCHING_DECISION."""
        pid = self._create_dummy_product("PROD_MATCH_002")
        outcome = {
            "product_id": pid,
            "decision_id": 99999,  # Non-existent
            "period_start": "2026-08-01",
            "period_end": "2026-08-31"
        }
        matched_dec, status, note = match_decision_for_outcome(outcome)
        self.assertIsNone(matched_dec)
        self.assertEqual(status, STATUS_NO_MATCHING_DECISION)

    def test_explicit_decision_matching_product_mismatch(self):
        """Outcome linking to a decision of a different product returns INVALID_INPUT."""
        pid1 = self._create_dummy_product("PROD_MATCH_003A")
        pid2 = self._create_dummy_product("PROD_MATCH_003B")
        dec_id1 = record_decision_snapshot(pid1, decision_timestamp="2026-07-15 10:00:00")

        outcome_bad = {
            "product_id": pid2,  # Product 2 attempting to link to Product 1's decision
            "decision_id": dec_id1,
            "period_start": "2026-08-01",
            "period_end": "2026-08-31"
        }
        matched_dec, status, note = match_decision_for_outcome(outcome_bad)
        self.assertIsNone(matched_dec)
        self.assertEqual(status, STATUS_INVALID_INPUT)

    def test_temporal_integrity_rejection_of_future_decision(self):
        """
        TEMPORAL INTEGRITY RULE:
        A decision made AFTER the outcome period began cannot be the predictor of that outcome.
        Decision: 2026-08-15
        Outcome period: 2026-08-01 -> 2026-08-31
        Must be rejected with TEMPORAL_MISMATCH.
        """
        pid = self._create_dummy_product("PROD_TEMP_001")
        # Decision made on 2026-08-15, which is after outcome period_start (2026-08-01)
        dec_id = record_decision_snapshot(pid, decision_timestamp="2026-08-15 12:00:00")

        outcome = {
            "product_id": pid,
            "decision_id": dec_id,
            "period_start": "2026-08-01",
            "period_end": "2026-08-31",
            "period_type": "DAY_30"
        }
        matched_dec, status, note = match_decision_for_outcome(outcome)
        self.assertIsNone(matched_dec)
        self.assertEqual(status, STATUS_TEMPORAL_MISMATCH)
        self.assertIn("Temporal integrity violation", note)

    def test_fallback_unambiguous_chronological_match(self):
        """
        When decision_id is None, if exactly 1 decision exists on or before period_start,
        it is matched unambiguously.
        """
        pid = self._create_dummy_product("PROD_FALLBACK_001")
        dec_id = record_decision_snapshot(pid, decision_timestamp="2026-07-20 12:00:00")

        outcome_no_id = {
            "product_id": pid,
            "decision_id": None,
            "period_start": "2026-08-01",
            "period_end": "2026-08-31"
        }
        matched_dec, status, note = match_decision_for_outcome(outcome_no_id)
        self.assertIsNotNone(matched_dec)
        self.assertEqual(matched_dec["decision_id"], dec_id)
        self.assertEqual(status, STATUS_CALIBRATED)

    def test_fallback_ambiguous_decisions_rejected(self):
        """
        When decision_id is None, if MULTIPLE prior decisions exist,
        APRS refuses to guess and returns NO_UNAMBIGUOUS_DECISION.
        """
        pid = self._create_dummy_product("PROD_AMBIG_001")
        # Record 2 distinct decisions prior to period_start
        dec1 = record_decision_snapshot(
            pid,
            decision_type="STAGE1_APPROVAL",
            override_predictions={"frozen_score": 75.0},
            decision_timestamp="2026-07-01 10:00:00"
        )
        dec2 = record_decision_snapshot(
            pid,
            decision_type="LAUNCHPAD_COMMITMENT",
            override_predictions={"frozen_score": 85.0},
            decision_timestamp="2026-07-15 10:00:00"
        )

        outcome_unlinked = {
            "product_id": pid,
            "decision_id": None,
            "period_start": "2026-08-01",
            "period_end": "2026-08-31"
        }
        matched_dec, status, note = match_decision_for_outcome(outcome_unlinked)
        self.assertIsNone(matched_dec)
        self.assertEqual(status, STATUS_NO_UNAMBIGUOUS_DECISION)
        self.assertIn("Multiple candidate decisions", note)

    # -------------------------------------------------------------
    # 9. IDEMPOTENCY & DATABASE PERSISTENCE
    # -------------------------------------------------------------

    def test_calibration_idempotency_and_update(self):
        """
        Calibrating the same decision_id + outcome_id + calculation_version twice
        must update the existing record without creating duplicates.
        """
        pid = self._create_dummy_product("PROD_IDEMP_CALIB_001")
        dec_id = record_decision_snapshot(pid, decision_timestamp="2026-07-15 10:00:00")

        outcome_res = record_product_outcome({
            "product_id": pid,
            "decision_id": dec_id,
            "period_start": "2026-08-01",
            "period_end": "2026-08-31",
            "period_type": "DAY_30",
            "actual_units_sold": 450,
            "actual_cm_pct": 28.0
        })
        out_id = outcome_res["outcome_id"]

        # Run calibration 1
        res1 = calibrate_outcome(out_id)
        self.assertEqual(res1["status"], "SUCCESS")
        calib_id1 = res1["calibration_id"]
        self.assertGreater(calib_id1, 0)

        # Run calibration 2 (identical inputs)
        res2 = calibrate_outcome(out_id)
        self.assertEqual(res2["status"], "SUCCESS")
        calib_id2 = res2["calibration_id"]

        # Identical calibration_id must be reused
        self.assertEqual(calib_id1, calib_id2)

        # Total rows in prediction_calibrations for this decision & outcome must be exactly 1
        cur = self.conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM prediction_calibrations WHERE decision_id = ? AND outcome_id = ?",
            (dec_id, out_id)
        )
        self.assertEqual(cur.fetchone()[0], 1)

    def test_database_cascading_deletes(self):
        """Deleting a master product cascades to decision_ledger, product_outcomes, and prediction_calibrations."""
        pid = self._create_dummy_product("PROD_CASCADE_001")
        dec_id = record_decision_snapshot(pid, decision_timestamp="2026-07-15 10:00:00")

        out_res = record_product_outcome({
            "product_id": pid,
            "decision_id": dec_id,
            "period_start": "2026-08-01",
            "period_end": "2026-08-31",
            "period_type": "DAY_30",
            "actual_units_sold": 300
        })
        out_id = out_res["outcome_id"]
        calibrate_outcome(out_id)

        cur = self.conn.cursor()
        # Verify calibration exists
        cur.execute("SELECT COUNT(*) FROM prediction_calibrations WHERE product_id = ?", (pid,))
        self.assertEqual(cur.fetchone()[0], 1)

        # Delete product
        cur.execute("DELETE FROM master_products WHERE product_id = ?", (pid,))
        self.conn.commit()

        # Cascading deletes verified
        cur.execute("SELECT COUNT(*) FROM decision_ledger WHERE product_id = ?", (pid,))
        self.assertEqual(cur.fetchone()[0], 0)
        cur.execute("SELECT COUNT(*) FROM product_outcomes WHERE product_id = ?", (pid,))
        self.assertEqual(cur.fetchone()[0], 0)
        cur.execute("SELECT COUNT(*) FROM prediction_calibrations WHERE product_id = ?", (pid,))
        self.assertEqual(cur.fetchone()[0], 0)

        # Check FK integrity
        cur.execute("PRAGMA foreign_key_check")
        self.assertEqual(len(cur.fetchall()), 0)

    # -------------------------------------------------------------
    # 10. SAMPLE-SIZE SAFEGUARDS & AGGREGATE BIAS
    # -------------------------------------------------------------

    def test_sample_size_safeguards_insufficient_vs_provisional(self):
        """
        N < 5 enforces INSUFFICIENT_SAMPLE tier.
        N >= 5 unlocks PROVISIONAL_AGGREGATE tier.
        """
        # Scenario 1: N = 4 observations
        calibs_4 = [
            {"demand_signed_error": -4.0, "demand_absolute_error": 4.0, "demand_percentage_error": -20.0},
            {"demand_signed_error": -6.0, "demand_absolute_error": 6.0, "demand_percentage_error": -30.0},
            {"demand_signed_error": -2.0, "demand_absolute_error": 2.0, "demand_percentage_error": -10.0},
            {"demand_signed_error": -8.0, "demand_absolute_error": 8.0, "demand_percentage_error": -40.0},
        ]
        bias_4 = calculate_aggregate_bias(calibs_4, metric_prefix="demand")
        self.assertEqual(bias_4["sample_size"], 4)
        self.assertEqual(bias_4["reliability_tier"], RELIABILITY_INSUFFICIENT_SAMPLE)

        # Scenario 2: N = 5 observations
        calibs_5 = calibs_4 + [
            {"demand_signed_error": -5.0, "demand_absolute_error": 5.0, "demand_percentage_error": -25.0}
        ]
        bias_5 = calculate_aggregate_bias(calibs_5, metric_prefix="demand")
        self.assertEqual(bias_5["sample_size"], 5)
        self.assertEqual(bias_5["reliability_tier"], RELIABILITY_PROVISIONAL_AGGREGATE)
        self.assertEqual(bias_5["systematic_bias"], "OVERPREDICTION_BIAS")
        self.assertAlmostEqual(bias_5["mean_signed_error"], -5.0, places=2)
        self.assertAlmostEqual(bias_5["mean_absolute_error"], 5.0, places=2)
        self.assertAlmostEqual(bias_5["mape"], 25.0, places=2)

    def test_aggregate_bias_excludes_undefined_percentage_errors_from_mape(self):
        """
        Observations with undefined percentage error (e.g. predicted == 0) must be
        excluded from MAPE denominator, without substituting zero or crashing.
        """
        calibs = [
            {"demand_signed_error": 5.0, "demand_absolute_error": 5.0, "demand_percentage_error": None},  # predicted was 0
            {"demand_signed_error": -4.0, "demand_absolute_error": 4.0, "demand_percentage_error": -20.0}, # valid
            {"demand_signed_error": 6.0, "demand_absolute_error": 6.0, "demand_percentage_error": 30.0},  # valid
            {"demand_signed_error": -2.0, "demand_absolute_error": 2.0, "demand_percentage_error": -10.0}, # valid
            {"demand_signed_error": 0.0, "demand_absolute_error": 0.0, "demand_percentage_error": 0.0},   # valid
        ]
        bias = calculate_aggregate_bias(calibs, metric_prefix="demand")
        self.assertEqual(bias["sample_size"], 5)
        self.assertEqual(bias["valid_observations"], 5)
        # MAPE should average over the 4 valid percentage errors: (20 + 30 + 10 + 0) / 4 = 15.0%
        self.assertAlmostEqual(bias["mape"], 15.0, places=2)

    def test_mean_signed_error_calculation_and_terminology(self):
        """
        Hardening Audit Phase 2.1:
        Verify that Mean Signed Error (MBE / Mean Bias Error) is strictly calculated as:
          sum(actual - predicted) / valid_n
        Verify that:
        - The returned dictionary key is strictly 'mean_signed_error'
        - No ambiguous 'mse' (Mean Squared Error) key is produced
        - Positive value indicates UNDERPREDICTION_BIAS (actual > predicted)
        - Negative value indicates OVERPREDICTION_BIAS (actual < predicted)
        - Zero value indicates UNBIASED
        """
        # Test Case 1: Underprediction Bias (actual > predicted, signed > 0)
        calibs_under = [
            {"demand_signed_error": 10.0, "demand_absolute_error": 10.0, "demand_percentage_error": 50.0},
            {"demand_signed_error": 20.0, "demand_absolute_error": 20.0, "demand_percentage_error": 100.0},
            {"demand_signed_error": 30.0, "demand_absolute_error": 30.0, "demand_percentage_error": 150.0},
            {"demand_signed_error": 15.0, "demand_absolute_error": 15.0, "demand_percentage_error": 75.0},
            {"demand_signed_error": 25.0, "demand_absolute_error": 25.0, "demand_percentage_error": 125.0},
        ]
        bias_under = calculate_aggregate_bias(calibs_under, metric_prefix="demand")
        # mean_signed_error = (10 + 20 + 30 + 15 + 25) / 5 = 20.0
        self.assertEqual(bias_under["mean_signed_error"], 20.0)
        self.assertNotIn("mse", bias_under)  # Strict terminology: not confused with Mean Squared Error
        self.assertEqual(bias_under["systematic_bias"], "UNDERPREDICTION_BIAS")

        # Test Case 2: Overprediction Bias (actual < predicted, signed < 0)
        calibs_over = [
            {"demand_signed_error": -10.0, "demand_absolute_error": 10.0, "demand_percentage_error": -50.0},
            {"demand_signed_error": -20.0, "demand_absolute_error": 20.0, "demand_percentage_error": -100.0},
            {"demand_signed_error": -30.0, "demand_absolute_error": 30.0, "demand_percentage_error": -150.0},
            {"demand_signed_error": -15.0, "demand_absolute_error": 15.0, "demand_percentage_error": -75.0},
            {"demand_signed_error": -25.0, "demand_absolute_error": 25.0, "demand_percentage_error": -125.0},
        ]
        bias_over = calculate_aggregate_bias(calibs_over, metric_prefix="demand")
        # mean_signed_error = (-10 - 20 - 30 - 15 - 25) / 5 = -20.0
        self.assertEqual(bias_over["mean_signed_error"], -20.0)
        self.assertNotIn("mse", bias_over)
        self.assertEqual(bias_over["systematic_bias"], "OVERPREDICTION_BIAS")

        # Test Case 3: Perfectly Unbiased (mean = 0.0)
        calibs_unbiased = [
            {"demand_signed_error": -10.0, "demand_absolute_error": 10.0, "demand_percentage_error": -50.0},
            {"demand_signed_error": 10.0, "demand_absolute_error": 10.0, "demand_percentage_error": 50.0},
            {"demand_signed_error": -5.0, "demand_absolute_error": 5.0, "demand_percentage_error": -25.0},
            {"demand_signed_error": 5.0, "demand_absolute_error": 5.0, "demand_percentage_error": 25.0},
            {"demand_signed_error": 0.0, "demand_absolute_error": 0.0, "demand_percentage_error": 0.0},
        ]
        bias_unbiased = calculate_aggregate_bias(calibs_unbiased, metric_prefix="demand")
        self.assertEqual(bias_unbiased["mean_signed_error"], 0.0)
        self.assertNotIn("mse", bias_unbiased)
        self.assertEqual(bias_unbiased["systematic_bias"], "UNBIASED")

    # -------------------------------------------------------------
    # 11. BATCH CALIBRATION & PRODUCT SUMMARY ORCHESTRATION
    # -------------------------------------------------------------

    def test_batch_calibration_and_product_summary(self):
        """Batch calibrator processes uncalibrated records and product summary aggregates them."""
        pid = self._create_dummy_product("PROD_BATCH_CALIB_001")
        dec_id = record_decision_snapshot(pid, decision_timestamp="2026-06-01 10:00:00")

        # Ingest 2 distinct monthly outcomes
        record_product_outcome({
            "product_id": pid,
            "decision_id": dec_id,
            "period_start": "2026-07-01",
            "period_end": "2026-07-31",
            "period_type": "DAY_30",
            "actual_units_sold": 450,
            "actual_cm_pct": 28.0,
            "actual_rto_rate_pct": 10.0,
            "actual_cac": 125.0
        })
        record_product_outcome({
            "product_id": pid,
            "decision_id": dec_id,
            "period_start": "2026-08-01",
            "period_end": "2026-08-31",
            "period_type": "DAY_30",
            "actual_units_sold": 500,
            "actual_cm_pct": 31.0,
            "actual_rto_rate_pct": 8.0,
            "actual_cac": 115.0
        })

        # Run batch calibration
        batch_res = calibrate_all_uncalibrated_outcomes()
        self.assertEqual(batch_res["total_uncalibrated"], 2)
        self.assertEqual(batch_res["calibrated"], 2)
        self.assertEqual(batch_res["errors"], 0)

        # Get product summary
        summary = get_calibration_summary_for_product(pid)
        self.assertEqual(summary["calibration_count"], 2)
        self.assertEqual(summary["reliability_tier"], RELIABILITY_INSUFFICIENT_SAMPLE)  # N=2 < 5
        self.assertIsNotNone(summary["demand_bias"]["mean_signed_error"])
        self.assertIsNotNone(summary["cm_bias"]["mean_signed_error"])

    # -------------------------------------------------------------
    # 12. SCHEMA MIGRATION & INDEX VALIDATION
    # -------------------------------------------------------------

    def test_schema_indexes_and_foreign_keys(self):
        """Verify Table 33 prediction_calibrations has all required indexes and 0 FK violations."""
        cur = self.conn.cursor()
        cur.execute("PRAGMA index_list(prediction_calibrations)")
        indexes = [r[1] for r in cur.fetchall()]

        self.assertIn("idx_calib_decision", indexes)
        self.assertIn("idx_calib_outcome", indexes)
        self.assertIn("idx_calib_product", indexes)
        self.assertIn("idx_calib_version", indexes)

        cur.execute("PRAGMA foreign_key_check")
        violations = cur.fetchall()
        self.assertEqual(len(violations), 0)

    def test_conflicting_recalculation_behavior(self):
        """When outcome data changes, re-calibration must update the calibration record with new errors."""
        pid = self._create_dummy_product("PROD_RECALC_001")
        dec_id = record_decision_snapshot(pid, decision_timestamp="2026-07-15 10:00:00")

        # Initial outcome: 400 units
        out_res = record_product_outcome({
            "product_id": pid,
            "decision_id": dec_id,
            "period_start": "2026-08-01",
            "period_end": "2026-08-31",
            "period_type": "DAY_30",
            "actual_units_sold": 400
        })
        out_id = out_res["outcome_id"]

        calib1 = calibrate_outcome(out_id)
        self.assertEqual(calib1["status"], "SUCCESS")
        initial_calib_id = calib1["calibration_id"]
        initial_signed_err = calib1["demand_signed_error"]

        # Legitimate outcome update: reconciliation reveals actual units sold was 620
        record_product_outcome({
            "product_id": pid,
            "decision_id": dec_id,
            "period_start": "2026-08-01",
            "period_end": "2026-08-31",
            "period_type": "DAY_30",
            "actual_units_sold": 620
        }, update_if_exists=True)

        # Re-run calibration
        calib2 = calibrate_outcome(out_id)
        self.assertEqual(calib2["status"], "SUCCESS")
        self.assertEqual(calib2["calibration_id"], initial_calib_id)  # Same row updated
        self.assertNotEqual(calib2["demand_signed_error"], initial_signed_err)

    def test_fresh_db_migration_all_tables(self):
        """Fresh database initialization must create all 33 tables, 4 calibration indexes, and 0 FK violations."""
        fresh_temp = tempfile.TemporaryDirectory()
        fresh_db_path = Path(fresh_temp.name) / "fresh_migration.db"
        orig_path = os.environ.get("APRS_DB_PATH")
        try:
            os.environ["APRS_DB_PATH"] = str(fresh_db_path)
            init_db()
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tables = [r[0] for r in cur.fetchall()]
            self.assertIn("prediction_calibrations", tables)
            self.assertIn("outcome_corrections_log", tables)
            self.assertGreaterEqual(len(tables), 33)

            cur.execute("PRAGMA index_list(prediction_calibrations)")
            indexes = [r[1] for r in cur.fetchall()]
            self.assertIn("idx_calib_decision", indexes)
            self.assertIn("idx_calib_outcome", indexes)
            self.assertIn("idx_calib_product", indexes)
            self.assertIn("idx_calib_version", indexes)

            cur.execute("PRAGMA foreign_key_check")
            violations = cur.fetchall()
            self.assertEqual(len(violations), 0)
            conn.close()
        finally:
            if orig_path:
                os.environ["APRS_DB_PATH"] = orig_path
            fresh_temp.cleanup()

    def test_existing_db_migration_preserves_data(self):
        """Running init_db on a database with existing product data must add prediction_calibrations without data loss."""
        fresh_temp = tempfile.TemporaryDirectory()
        existing_db_path = Path(fresh_temp.name) / "existing_migration.db"
        orig_path = os.environ.get("APRS_DB_PATH")
        try:
            os.environ["APRS_DB_PATH"] = str(existing_db_path)
            init_db()
            conn = get_connection()
            cur = conn.cursor()

            # Seed a product and a decision snapshot
            pid = self._create_dummy_product("PROD_MIGRATE_001")
            dec_id = record_decision_snapshot(pid)

            # Re-run init_db (simulating migration run against existing DB)
            init_db()

            cur.execute("SELECT COUNT(*) FROM master_products WHERE product_id = ?", (pid,))
            self.assertEqual(cur.fetchone()[0], 1)
            cur.execute("SELECT COUNT(*) FROM decision_ledger WHERE decision_id = ?", (dec_id,))
            self.assertEqual(cur.fetchone()[0], 1)

            cur.execute("PRAGMA foreign_key_check")
            self.assertEqual(len(cur.fetchall()), 0)
            conn.close()
        finally:
            if orig_path:
                os.environ["APRS_DB_PATH"] = orig_path
            fresh_temp.cleanup()


if __name__ == "__main__":
    unittest.main()

