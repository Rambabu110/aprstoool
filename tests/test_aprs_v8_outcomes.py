"""
APRS V8 PHASE 3: REAL OUTCOME INGESTION & OBSERVATION TEST SUITE
================================================================
Comprehensive, isolated tests validating:
  1. Basic ingestion (valid outcome -> 1 row)
  2. Duplicate ingestion (same source_record_id -> no duplicate)
  3. Decision mismatch (Product A outcome vs Product B decision -> reject)
  4. Unknown decision (nonexistent decision_id -> reject)
  5. Temporal violation (outcome predates decision -> reject)
  6. Invalid period (end < start -> reject)
  7. Partial outcome (metrics NULL -> accepted, NULL preserved)
  8. Zero actual outcome (units = 0 -> accepted & calibrated)
  9. Return validation (returns > units -> reject)
  10. RTO validation (rto > units -> reject)
  11. Rate validation (rate > 100% -> reject)
  12. Stockout validation (stockouts > observation period -> reject)
  13. Calibration integration (valid outcome -> deterministic calibration)
  14. Historical prediction (frozen ledger used, not mutated current intelligence)
  15. Outcome correction (explicit correction -> audit log + recalibration)
  16. Idempotency (repeated ingestion -> one observation)
  17. Multiple periods (DAY_30 + DAY_60 -> two distinct observations)
  18. Missing future periods (DAY_30 only -> no fake DAY_60/DAY_90 placeholders)
  19. Scraped proxies rejection (BSR, Helium, Trends rejected)
  20. Observation status lifecycle (NOT_LAUNCHED, LAUNCHED_NOT_OBSERVED, etc.)
  21. Decision disambiguation (multiple prior decisions -> reject ambiguity)
  22. Derived metrics transparency (reported vs derived tracked)
  23. No production database contamination (isolated fixtures only)
"""

import os
import unittest
import tempfile
from pathlib import Path
import sqlite3

from core.database import (
    init_db,
    get_connection,
    record_product_evaluation,
    record_decision_snapshot,
    get_outcome_by_id,
    get_product_outcomes,
    get_outcome_corrections,
    add_to_launchpad,
    update_launchpad_status,
    validate_outcome_payload
)
from core.outcome_ingestion import (
    OutcomeIngestionService,
    STATUS_NOT_LAUNCHED,
    STATUS_LAUNCHED_NOT_OBSERVED,
    STATUS_OBSERVATION_AVAILABLE,
    STATUS_PARTIAL_OBSERVATION,
    derive_outcome_metrics,
    resolve_decision_link
)
from core.calibration_engine import (
    get_calibrations_for_product
)


class TestAPRSV8OutcomeIngestion(unittest.TestCase):

    def setUp(self):
        """Create an isolated temporary SQLite database for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_v8_outcomes.db"
        self.orig_db_path = os.environ.get("APRS_DB_PATH")
        os.environ["APRS_DB_PATH"] = str(self.db_path)
        init_db()
        self.conn = get_connection()

    def tearDown(self):
        """Clean up test database and restore environment."""
        self.conn.close()
        if self.orig_db_path:
            os.environ["APRS_DB_PATH"] = self.orig_db_path
        elif "APRS_DB_PATH" in os.environ:
            del os.environ["APRS_DB_PATH"]
        self.temp_dir.cleanup()

    def _create_dummy_product(self, product_id="PROD_TEST_001", name="Smart Ceramic Mug", msrp=1499.0, cogs=450.0):
        """Helper to create a valid master product with baseline economics."""
        prod = {
            "id": product_id,
            "name": name,
            "category": "Home & Kitchen",
            "region": "India",
            "retail_msrp": msrp,
            "factory_cogs": cogs,
            "est_cac": 150.0,
            "bsr_rank": 350,
            "estimated_daily_units": 25,
            "ad_active_days": 20,
            "sourcing_hub": "Moradabad Cluster",
            "marketplace_url": f"https://www.amazon.in/dp/{product_id}",
            "competitor_flaw": "Coating peels off",
            "upgrade_v2": "Triple-glazed enamel finish",
            "suppliers": []
        }
        econ = {
            "status": "PASS",
            "score": 85.0,
            "landed_cogs": cogs,
            "gross_margin_pct": 70.0,
            "net_profit_pct": 25.0,
            "worst_case_stress_margin_pct": 12.0,
            "consensus_status": "CONSENSUS_PASS",
            "action_plan": "Proceed to sourcing"
        }
        record_product_evaluation(prod, econ)
        return product_id

    # -------------------------------------------------------------
    # 1. BASIC INGESTION & CALIBRATION INTEGRATION
    # -------------------------------------------------------------

    def test_basic_ingestion_valid_outcome(self):
        """Valid outcome observation is recorded and automatically calibrated."""
        pid = self._create_dummy_product("PROD_BASIC_001")
        dec_id = record_decision_snapshot(pid, decision_timestamp="2026-07-01 10:00:00")

        payload = {
            "product_id": pid,
            "decision_id": dec_id,
            "period_start": "2026-07-15",
            "period_end": "2026-08-14",
            "period_type": "DAY_30",
            "actual_units_sold": 600,
            "actual_revenue": 899400.0,
            "actual_avg_selling_price": 1499.0,
            "actual_landed_cogs": 450.0,
            "actual_contribution_margin": 270000.0,
            "actual_cm_pct": 30.0,
            "actual_returns_count": 24,
            "actual_return_rate_pct": 4.0,
            "actual_rto_count": 48,
            "actual_rto_rate_pct": 8.0,
            "actual_ad_spend": 90000.0,
            "actual_cac": 150.0,
            "actual_inventory": 400,
            "actual_stockout_days": 1,
            "data_source": "SHOPIFY_API",
            "source_record_id": "SHOP_SYNC_001",
            "notes": "Month 1 sales validated"
        }

        res = OutcomeIngestionService.ingest_outcome(payload, auto_calibrate=True)
        self.assertEqual(res["status"], "CREATED")
        self.assertGreater(res["outcome_id"], 0)
        self.assertIsNotNone(res["calibration"])
        self.assertEqual(res["calibration"]["status"], "SUCCESS")

        # Verify outcome in DB
        saved = get_outcome_by_id(res["outcome_id"])
        self.assertIsNotNone(saved)
        self.assertEqual(saved["product_id"], pid)
        self.assertEqual(saved["decision_id"], dec_id)
        self.assertEqual(saved["actual_units_sold"], 600)

        # Verify calibrations for product (600 units / 31 days = 19.35 daily units)
        calibs = get_calibrations_for_product(pid)
        self.assertEqual(len(calibs), 1)
        self.assertEqual(calibs[0]["demand_actual"], 19.35)

    # -------------------------------------------------------------
    # 2. DUPLICATE INGESTION & IDEMPOTENCY
    # -------------------------------------------------------------

    def test_duplicate_ingestion_same_source_record(self):
        """Re-ingesting the exact same source_record_id returns IDEMPOTENT_DUPLICATE without creating new rows."""
        pid = self._create_dummy_product("PROD_DUP_001")
        dec_id = record_decision_snapshot(pid, decision_timestamp="2026-06-01 10:00:00")

        payload = {
            "product_id": pid,
            "decision_id": dec_id,
            "period_start": "2026-07-01",
            "period_end": "2026-07-31",
            "period_type": "DAY_30",
            "actual_units_sold": 300,
            "actual_revenue": 450000.0,
            "data_source": "SHOPIFY_ORDER_EXPORT",
            "source_record_id": "ORDER_EXP_9999"
        }

        res1 = OutcomeIngestionService.ingest_outcome(payload)
        self.assertEqual(res1["status"], "CREATED")
        first_id = res1["outcome_id"]

        # Ingest again
        res2 = OutcomeIngestionService.ingest_outcome(payload)
        self.assertEqual(res2["status"], "IDEMPOTENT_DUPLICATE")
        self.assertEqual(res2["outcome_id"], first_id)

        # Confirm count in database is exactly 1
        outcomes = get_product_outcomes(pid)
        self.assertEqual(len(outcomes), 1)

    # -------------------------------------------------------------
    # 3. DECISION MATCHING & MISMATCH REJECTION
    # -------------------------------------------------------------

    def test_decision_mismatch_rejected(self):
        """Reject outcome referencing a decision belonging to a different product."""
        pid_a = self._create_dummy_product("PROD_MATCH_A")
        pid_b = self._create_dummy_product("PROD_MATCH_B")

        dec_a = record_decision_snapshot(pid_a, decision_timestamp="2026-06-01 10:00:00")

        payload = {
            "product_id": pid_b,  # Product B
            "decision_id": dec_a,  # Decision belongs to Product A
            "period_start": "2026-07-01",
            "period_end": "2026-07-31",
            "period_type": "DAY_30",
            "actual_units_sold": 100
        }

        with self.assertRaises(ValueError) as ctx:
            OutcomeIngestionService.ingest_outcome(payload)
        self.assertIn("belongs to product 'PROD_MATCH_A', not 'PROD_MATCH_B'", str(ctx.exception))

    def test_unknown_decision_rejected(self):
        """Reject outcome referencing nonexistent decision_id."""
        pid = self._create_dummy_product("PROD_UNK_DEC")
        payload = {
            "product_id": pid,
            "decision_id": 999999,  # Nonexistent
            "period_start": "2026-07-01",
            "period_end": "2026-07-31",
            "period_type": "DAY_30",
            "actual_units_sold": 100
        }

        with self.assertRaises(ValueError) as ctx:
            OutcomeIngestionService.ingest_outcome(payload)
        self.assertIn("does not exist in decision_ledger", str(ctx.exception))

    # -------------------------------------------------------------
    # 4. TEMPORAL INTEGRITY
    # -------------------------------------------------------------

    def test_temporal_violation_outcome_predates_decision(self):
        """Reject outcome occurring before the decision snapshot timestamp."""
        pid = self._create_dummy_product("PROD_TEMP_VIOL")
        # Decision made on 2026-09-01
        dec_id = record_decision_snapshot(pid, decision_timestamp="2026-09-01 12:00:00")

        # Outcome period was in August 2026 (before decision)
        payload = {
            "product_id": pid,
            "decision_id": dec_id,
            "period_start": "2026-08-01",
            "period_end": "2026-08-31",
            "period_type": "DAY_30",
            "actual_units_sold": 150
        }

        with self.assertRaises(ValueError) as ctx:
            OutcomeIngestionService.ingest_outcome(payload)
        self.assertIn("Temporal Integrity Error", str(ctx.exception))

    def test_invalid_period_end_before_start(self):
        """Reject outcome where period_end is before period_start."""
        pid = self._create_dummy_product("PROD_DATE_ORDER")
        payload = {
            "product_id": pid,
            "period_start": "2026-08-31",
            "period_end": "2026-08-01",  # End before start
            "period_type": "DAY_30",
            "actual_units_sold": 50
        }

        with self.assertRaises(ValueError) as ctx:
            OutcomeIngestionService.ingest_outcome(payload)
        self.assertIn("cannot be before period_start", str(ctx.exception))

    # -------------------------------------------------------------
    # 5. BUSINESS METRIC VALIDATION
    # -------------------------------------------------------------

    def test_partial_outcome_accepted_null_preserved(self):
        """Partial outcome with missing commercial fields is accepted, preserving NULLs."""
        pid = self._create_dummy_product("PROD_PARTIAL_ACC")
        dec_id = record_decision_snapshot(pid, decision_timestamp="2026-07-01 10:00:00")

        payload = {
            "product_id": pid,
            "decision_id": dec_id,
            "period_start": "2026-07-15",
            "period_end": "2026-08-14",
            "period_type": "DAY_30",
            "actual_units_sold": 200,
            "actual_revenue": 300000.0,
            # Landed cogs, CM, returns, RTO, CAC intentionally omitted / None
        }

        res = OutcomeIngestionService.ingest_outcome(payload, auto_calibrate=True)
        self.assertEqual(res["status"], "CREATED")

        saved = get_outcome_by_id(res["outcome_id"])
        self.assertEqual(saved["actual_units_sold"], 200)
        self.assertIsNone(saved["actual_landed_cogs"])
        self.assertIsNone(saved["actual_cac"])
        self.assertIsNone(saved["actual_returns_count"])

        # Calibration engine handles partial data cleanly
        calib = res["calibration"]
        self.assertEqual(calib["calibration_status"], "PARTIAL_DATA")
        self.assertEqual(calib["demand_actual"], 6.45)
        self.assertIsNone(calib["cac_actual"])

    def test_zero_actual_outcome_handled_correctly(self):
        """Zero actual units sold (e.g. dead launch) is valid and does not crash calibration."""
        pid = self._create_dummy_product("PROD_ZERO_ACT")
        dec_id = record_decision_snapshot(pid, decision_timestamp="2026-07-01 10:00:00")

        payload = {
            "product_id": pid,
            "decision_id": dec_id,
            "period_start": "2026-07-15",
            "period_end": "2026-08-14",
            "period_type": "DAY_30",
            "actual_units_sold": 0,
            "actual_revenue": 0.0,
            "actual_ad_spend": 25000.0
        }

        res = OutcomeIngestionService.ingest_outcome(payload, auto_calibrate=True)
        self.assertEqual(res["status"], "CREATED")
        calib = res["calibration"]
        self.assertEqual(calib["demand_actual"], 0.0)
        self.assertIsNotNone(calib["demand_signed_error"])

    def test_return_validation_returns_exceeding_units(self):
        """Reject actual_returns_count > actual_units_sold."""
        pid = self._create_dummy_product("PROD_RET_EXCEED")
        payload = {
            "product_id": pid,
            "period_start": "2026-07-01",
            "period_end": "2026-07-31",
            "period_type": "DAY_30",
            "actual_units_sold": 50,
            "actual_returns_count": 60  # 60 > 50!
        }
        with self.assertRaises(ValueError) as ctx:
            OutcomeIngestionService.ingest_outcome(payload)
        self.assertIn("cannot exceed actual_units_sold", str(ctx.exception))

    def test_rto_validation_rto_exceeding_units(self):
        """Reject actual_rto_count > actual_units_sold."""
        pid = self._create_dummy_product("PROD_RTO_EXCEED")
        payload = {
            "product_id": pid,
            "period_start": "2026-07-01",
            "period_end": "2026-07-31",
            "period_type": "DAY_30",
            "actual_units_sold": 100,
            "actual_rto_count": 120  # 120 > 100!
        }
        with self.assertRaises(ValueError) as ctx:
            OutcomeIngestionService.ingest_outcome(payload)
        self.assertIn("cannot exceed actual_units_sold", str(ctx.exception))

    def test_rate_validation_rate_exceeding_100(self):
        """Reject percentages > 100.0%."""
        pid = self._create_dummy_product("PROD_RATE_EXCEED")
        payload = {
            "product_id": pid,
            "period_start": "2026-07-01",
            "period_end": "2026-07-31",
            "period_type": "DAY_30",
            "actual_units_sold": 100,
            "actual_return_rate_pct": 105.0  # > 100%
        }
        with self.assertRaises(ValueError) as ctx:
            OutcomeIngestionService.ingest_outcome(payload)
        self.assertIn("must be between 0.0% and 100.0%", str(ctx.exception))

    def test_stockout_validation_exceeding_observation_period(self):
        """Reject stockout_days > observation_period_days."""
        pid = self._create_dummy_product("PROD_STOCKOUT_EXCEED")
        # Observation period is 31 days (2026-07-01 to 2026-07-31)
        payload = {
            "product_id": pid,
            "period_start": "2026-07-01",
            "period_end": "2026-07-31",
            "period_type": "DAY_30",
            "actual_units_sold": 100,
            "actual_stockout_days": 35  # 35 > 31!
        }
        with self.assertRaises(ValueError) as ctx:
            OutcomeIngestionService.ingest_outcome(payload)
        self.assertIn("cannot exceed observation period days", str(ctx.exception))

    def test_scraped_market_proxies_rejected(self):
        """Reject pre-launch research proxies (BSR, Helium, Trends) from being recorded as outcomes."""
        pid = self._create_dummy_product("PROD_PROXY_REJECT")
        for bad_src in ("GOOGLE_TRENDS", "COMPETITOR_BSR", "SCRAPED_ESTIMATE", "HELIUM_ESTIMATE"):
            payload = {
                "product_id": pid,
                "period_start": "2026-07-01",
                "period_end": "2026-07-31",
                "period_type": "DAY_30",
                "actual_units_sold": 100,
                "data_source": bad_src
            }
            with self.assertRaises(ValueError) as ctx:
                OutcomeIngestionService.ingest_outcome(payload)
            self.assertIn("represents pre-launch research/scraped estimates", str(ctx.exception))

    # -------------------------------------------------------------
    # 6. HISTORICAL PREDICTION PURITY (DECISION LEDGER IS FROZEN)
    # -------------------------------------------------------------

    def test_historical_prediction_uses_frozen_ledger_not_current_intelligence(self):
        """
        Verify calibration strictly uses the frozen decision_ledger values,
        even if master_products is subsequently re-evaluated or mutated.
        """
        pid = self._create_dummy_product("PROD_FROZEN_PURITY", msrp=1000.0, cogs=300.0)
        dec_id = record_decision_snapshot(pid, decision_timestamp="2026-06-01 10:00:00")

        # Mutate product through new evaluation after decision was frozen
        prod_mutated = {
            "id": pid,
            "name": "Smart Ceramic Mug",
            "category": "Home & Kitchen",
            "region": "India",
            "retail_msrp": 5000.0,  # Mutated from 1000 to 5000
            "factory_cogs": 1500.0,
            "est_cac": 500.0,
            "bsr_rank": 50,
            "estimated_daily_units": 80,  # Mutated from 25 to 80
            "ad_active_days": 30,
            "sourcing_hub": "Moradabad Cluster",
            "marketplace_url": f"https://www.amazon.in/dp/{pid}",
            "competitor_flaw": "None",
            "upgrade_v2": "None",
            "suppliers": []
        }
        econ_mutated = {
            "status": "PASS",
            "score": 98.0,
            "landed_cogs": 1500.0,
            "gross_margin_pct": 70.0,
            "net_profit_pct": 25.0,
            "worst_case_stress_margin_pct": 12.0,
            "consensus_status": "CONSENSUS_PASS",
            "action_plan": "Mutated re-evaluation"
        }
        record_product_evaluation(prod_mutated, econ_mutated)

        # Ingest outcome
        res = OutcomeIngestionService.ingest_outcome({
            "product_id": pid,
            "decision_id": dec_id,
            "period_start": "2026-07-01",
            "period_end": "2026-07-31",
            "period_type": "DAY_30",
            "actual_units_sold": 600,
            "actual_avg_selling_price": 1050.0
        }, auto_calibrate=True)

        calib = res["calibration"]
        # Predicted price in calibration must be the FROZEN 1000.0, NOT the mutated 5000.0!
        self.assertEqual(calib["price_predicted"], 1000.0)
        self.assertNotEqual(calib["price_predicted"], 5000.0)
        self.assertEqual(calib["price_actual"], 1050.0)
        # Price signed error: 1050 - 1000 = +50.0
        self.assertEqual(calib["price_signed_error"], 50.0)
        # Predicted daily demand in calibration must be the FROZEN 25, NOT the mutated 80!
        self.assertEqual(calib["demand_predicted"], 25.0)

    # -------------------------------------------------------------
    # 7. OUTCOME CORRECTIONS & AUDIT LOGGING
    # -------------------------------------------------------------

    def test_outcome_correction_auditability_and_recalibration(self):
        """
        Explicit correction updates outcome values, logs every changed field to
        outcome_corrections_log, and immediately triggers recalibration.
        """
        pid = self._create_dummy_product("PROD_CORR_001")
        dec_id = record_decision_snapshot(pid, decision_timestamp="2026-07-01 10:00:00")

        # Initial ingestion
        res = OutcomeIngestionService.ingest_outcome({
            "product_id": pid,
            "decision_id": dec_id,
            "period_start": "2026-07-15",
            "period_end": "2026-08-14",
            "period_type": "DAY_30",
            "actual_units_sold": 500,
            "actual_revenue": 749500.0
        }, auto_calibrate=True)
        out_id = res["outcome_id"]
        initial_calib_demand = res["calibration"]["demand_actual"]
        self.assertEqual(initial_calib_demand, 16.13)

        # Explicit correction: Sales audit revealed 50 units returned, units sold should be 450
        corr_res = OutcomeIngestionService.correct_outcome(
            outcome_id=out_id,
            correction_data={"actual_units_sold": 450, "actual_returns_count": 50},
            reason="Audited Shopify return sync adjustments",
            operator="LEAD_ACCOUNTANT",
            auto_calibrate=True
        )
        self.assertEqual(corr_res["status"], "CORRECTED")
        self.assertGreaterEqual(corr_res["corrections_logged"], 2)

        # Verify outcome updated
        updated_out = get_outcome_by_id(out_id)
        self.assertEqual(updated_out["actual_units_sold"], 450)
        self.assertEqual(updated_out["actual_returns_count"], 50)

        # Verify audit log in outcome_corrections_log
        corr_logs = get_outcome_corrections(outcome_id=out_id)
        self.assertGreaterEqual(len(corr_logs), 2)
        fields_changed = {c["field_name"]: (c["previous_value"], c["new_value"]) for c in corr_logs}
        self.assertIn("actual_units_sold", fields_changed)
        self.assertEqual(fields_changed["actual_units_sold"], ("500", "450"))
        self.assertEqual(corr_logs[0]["corrected_by"], "LEAD_ACCOUNTANT")

        # Verify recalibrated demand (450 units / 31 days = 14.52 daily units)
        recalib = corr_res["calibration"]
        self.assertEqual(recalib["demand_actual"], 14.52)

        # Verify history API
        history = OutcomeIngestionService.get_outcome_history(out_id)
        self.assertEqual(history["corrections_count"], len(corr_logs))
        self.assertEqual(history["calibration"]["demand_actual"], 14.52)

    # -------------------------------------------------------------
    # 8. MULTIPLE PERIODS & MATURITY
    # -------------------------------------------------------------

    def test_multiple_periods_coexist_independently(self):
        """DAY_30 and DAY_60 observations for the same product coexist independently without conflict."""
        pid = self._create_dummy_product("PROD_PERIODS_001")
        dec_id = record_decision_snapshot(pid, decision_timestamp="2026-06-01 10:00:00")

        # DAY_30
        res30 = OutcomeIngestionService.ingest_outcome({
            "product_id": pid,
            "decision_id": dec_id,
            "period_start": "2026-07-01",
            "period_end": "2026-07-31",
            "period_type": "DAY_30",
            "actual_units_sold": 400
        })

        # DAY_60
        res60 = OutcomeIngestionService.ingest_outcome({
            "product_id": pid,
            "decision_id": dec_id,
            "period_start": "2026-07-01",
            "period_end": "2026-08-31",
            "period_type": "DAY_60",
            "actual_units_sold": 850
        })

        self.assertNotEqual(res30["outcome_id"], res60["outcome_id"])
        outcomes = get_product_outcomes(pid)
        self.assertEqual(len(outcomes), 2)
        period_types = [o["period_type"] for o in outcomes]
        self.assertIn("DAY_30", period_types)
        self.assertIn("DAY_60", period_types)

    def test_missing_future_periods_no_fake_placeholders(self):
        """Recording DAY_30 must never insert fake zero-valued DAY_60 or DAY_90 records."""
        pid = self._create_dummy_product("PROD_MATURITY_001")
        dec_id = record_decision_snapshot(pid, decision_timestamp="2026-06-01 10:00:00")

        OutcomeIngestionService.ingest_outcome({
            "product_id": pid,
            "decision_id": dec_id,
            "period_start": "2026-07-01",
            "period_end": "2026-07-31",
            "period_type": "DAY_30",
            "actual_units_sold": 350
        })

        outcomes = get_product_outcomes(pid)
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes[0]["period_type"], "DAY_30")

        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM product_outcomes WHERE product_id = ? AND period_type IN ('DAY_60', 'DAY_90')", (pid,))
        self.assertEqual(cur.fetchone()[0], 0)

    # -------------------------------------------------------------
    # 9. OBSERVATION STATUS DERIVATION
    # -------------------------------------------------------------

    def test_observation_status_lifecycle_derivation(self):
        """
        Verify clean derivation of all 4 observation statuses:
          - NOT_LAUNCHED
          - LAUNCHED_NOT_OBSERVED
          - PARTIAL_OBSERVATION
          - OBSERVATION_AVAILABLE
        """
        pid = self._create_dummy_product("PROD_OBS_STATUS_001")

        # 1. NOT_LAUNCHED: Product created, not yet in launchpad or launched
        s1 = OutcomeIngestionService.get_observation_status(pid)
        self.assertEqual(s1["observation_status"], STATUS_NOT_LAUNCHED)
        self.assertFalse(s1["is_launched"])

        # 2. Add to Launchpad and mark launched -> LAUNCHED_NOT_OBSERVED
        item_id = add_to_launchpad(pid, "Smart Ceramic Mug", target_moq=500, target_fob=400.0)
        update_launchpad_status(item_id, launch_status="LAUNCHED")

        s2 = OutcomeIngestionService.get_observation_status(pid)
        self.assertEqual(s2["observation_status"], STATUS_LAUNCHED_NOT_OBSERVED)
        self.assertTrue(s2["is_launched"])

        # 3. Ingest partial outcome (missing COGS, CAC, margin) -> PARTIAL_OBSERVATION
        res_part = OutcomeIngestionService.ingest_outcome({
            "product_id": pid,
            "period_start": "2026-08-01",
            "period_end": "2026-08-31",
            "period_type": "DAY_30",
            "actual_units_sold": 200,
            "actual_revenue": 299800.0
        })
        s3 = OutcomeIngestionService.get_observation_status(pid)
        self.assertEqual(s3["observation_status"], STATUS_PARTIAL_OBSERVATION)

        # 4. Ingest complete observation with all core metrics -> OBSERVATION_AVAILABLE
        OutcomeIngestionService.ingest_outcome({
            "product_id": pid,
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "period_type": "DAY_30",
            "actual_units_sold": 450,
            "actual_revenue": 674550.0,
            "actual_avg_selling_price": 1499.0,
            "actual_landed_cogs": 450.0,
            "actual_contribution_margin": 270000.0,
            "actual_cm_pct": 40.0,
            "actual_returns_count": 10,
            "actual_return_rate_pct": 2.2,
            "actual_rto_count": 25,
            "actual_rto_rate_pct": 5.5,
            "actual_ad_spend": 50000.0,
            "actual_cac": 111.11,
            "actual_inventory": 300,
            "actual_stockout_days": 0
        })
        s4 = OutcomeIngestionService.get_observation_status(pid)
        self.assertEqual(s4["observation_status"], STATUS_OBSERVATION_AVAILABLE)

    # -------------------------------------------------------------
    # 10. DECISION DISAMBIGUATION & AUTO-LINKING
    # -------------------------------------------------------------

    def test_decision_auto_linking_single_prior_decision(self):
        """When decision_id is omitted, exactly 1 prior decision is auto-linked chronologically."""
        pid = self._create_dummy_product("PROD_AUTOLINK_001")
        dec_id = record_decision_snapshot(pid, decision_timestamp="2026-07-01 10:00:00")

        res = OutcomeIngestionService.ingest_outcome({
            "product_id": pid,
            # decision_id omitted
            "period_start": "2026-07-15",
            "period_end": "2026-08-14",
            "period_type": "DAY_30",
            "actual_units_sold": 100
        })
        self.assertEqual(res["decision_id"], dec_id)
        saved = get_outcome_by_id(res["outcome_id"])
        self.assertEqual(saved["decision_id"], dec_id)

    def test_decision_disambiguation_multiple_prior_decisions_rejected(self):
        """When multiple prior decisions exist and decision_id is omitted, reject as ambiguous."""
        pid = self._create_dummy_product("PROD_AMBIG_001")
        record_decision_snapshot(pid, decision_type="GATE_EXIT", decision_timestamp="2026-06-01 10:00:00")
        record_decision_snapshot(pid, decision_type="LAUNCHPAD_COMMITMENT", decision_timestamp="2026-07-01 10:00:00")

        payload = {
            "product_id": pid,
            # decision_id omitted
            "period_start": "2026-07-15",
            "period_end": "2026-08-14",
            "period_type": "DAY_30",
            "actual_units_sold": 100
        }
        with self.assertRaises(ValueError) as ctx:
            OutcomeIngestionService.ingest_outcome(payload)
        self.assertIn("Ambiguous historical matching", str(ctx.exception))

    # -------------------------------------------------------------
    # 11. DERIVED METRICS TRANSPARENCY
    # -------------------------------------------------------------

    def test_derived_metrics_transparency_and_non_overwriting(self):
        """
        Verify derive_outcome_metrics derives missing values without overwriting supplied values.
        """
        # Scenario 1: Missing price is derived from revenue / units
        data1 = {
            "actual_units_sold": 100,
            "actual_revenue": 150000.0,
            "actual_avg_selling_price": None
        }
        enr1, der1 = derive_outcome_metrics(data1)
        self.assertEqual(enr1["actual_avg_selling_price"], 1500.0)
        self.assertIn("actual_avg_selling_price", der1)

        # Scenario 2: Supplied price is NOT overwritten, even if different from rev / units
        data2 = {
            "actual_units_sold": 100,
            "actual_revenue": 150000.0,
            "actual_avg_selling_price": 1450.0  # Explicit reported discount price
        }
        enr2, der2 = derive_outcome_metrics(data2)
        self.assertEqual(enr2["actual_avg_selling_price"], 1450.0)
        self.assertNotIn("actual_avg_selling_price", der2)

        # Scenario 3: Return rate & RTO rate derived from counts
        data3 = {
            "actual_units_sold": 200,
            "actual_returns_count": 8,
            "actual_rto_count": 16,
            "actual_ad_spend": 24000.0
        }
        enr3, der3 = derive_outcome_metrics(data3)
        self.assertEqual(enr3["actual_return_rate_pct"], 4.0)
        self.assertEqual(enr3["actual_rto_rate_pct"], 8.0)
        self.assertEqual(enr3["actual_cac"], 120.0)

    # -------------------------------------------------------------
    # 12. PRODUCTION DATABASE REMAINS CLEAN (ZERO CONTAMINATION)
    # -------------------------------------------------------------

    def test_no_synthetic_production_contamination(self):
        """
        Verify that all tests ran in isolated databases and the authoritative
        production database at data/research_engine.db contains zero synthetic rows.
        """
        prod_db_file = Path("data/research_engine.db")
        if not prod_db_file.exists():
            return  # In environments without existing file, test passes

        p_conn = sqlite3.connect(str(prod_db_file))
        p_cur = p_conn.cursor()

        p_cur.execute("SELECT COUNT(*) FROM decision_ledger")
        self.assertEqual(p_cur.fetchone()[0], 0, "Production decision_ledger must remain 0.")

        p_cur.execute("SELECT COUNT(*) FROM product_outcomes")
        self.assertEqual(p_cur.fetchone()[0], 0, "Production product_outcomes must remain 0.")

        p_cur.execute("SELECT COUNT(*) FROM prediction_calibrations")
        self.assertEqual(p_cur.fetchone()[0], 0, "Production prediction_calibrations must remain 0.")

        p_conn.close()
