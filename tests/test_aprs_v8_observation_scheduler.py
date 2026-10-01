"""
APRS V8 PHASE 4A: OBSERVATION SCHEDULER & MATURITY ENGINE TESTS
================================================================
Comprehensive, isolated tests validating:
  1. Product launch detection (master_products vs launchpad_items)
  2. Observation window calculation (DAY_30, DAY_60, DAY_90 deterministic bounds)
  3. Window maturity states:
     - NOT_DUE (as_of_date < due_date)
     - DUE (as_of_date >= due_date within grace period)
     - OVERDUE (as_of_date > due_date + grace period)
     - OBSERVED (outcome recorded with complete core metrics)
     - PARTIALLY_OBSERVED (outcome recorded with partial metrics)
     - NOT_LAUNCHED (unlaunched product)
  4. Next expected observation prioritization
  5. Actionable due observations queue (get_due_observations)
  6. Catalog-wide schedule listing and status filtering
  7. Maturity summary statistics
  8. Rule 0: Strict separation of scheduling vs ingestion (zero outcomes generated)
  9. Production database purity (zero contamination)
"""

import os
import unittest
import tempfile
from pathlib import Path
import datetime
import sqlite3

from core.database import (
    init_db,
    get_connection,
    record_product_evaluation,
    record_decision_snapshot,
    add_to_launchpad,
    update_launchpad_status,
    get_product_outcomes
)
from core.outcome_ingestion import (
    OutcomeIngestionService
)
from core.observation_scheduler import (
    ObservationScheduler,
    get_product_launch_info,
    compute_observation_windows,
    evaluate_window_maturity,
    WINDOW_STATUS_NOT_DUE,
    WINDOW_STATUS_DUE,
    WINDOW_STATUS_OVERDUE,
    WINDOW_STATUS_OBSERVED,
    WINDOW_STATUS_PARTIALLY_OBSERVED,
    WINDOW_STATUS_NOT_LAUNCHED
)


class TestAPRSV8ObservationScheduler(unittest.TestCase):

    def setUp(self):
        """Create an isolated temporary SQLite database for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_v8_scheduler.db"
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

    def _create_dummy_product(self, product_id="PROD_SCHED_001", name="Smart Coffee Tumbler", msrp=1299.0, cogs=350.0):
        """Helper to create a valid master product with baseline economics."""
        prod = {
            "id": product_id,
            "name": name,
            "category": "Home & Kitchen",
            "region": "India",
            "retail_msrp": msrp,
            "factory_cogs": cogs,
            "est_cac": 120.0,
            "bsr_rank": 400,
            "estimated_daily_units": 20,
            "ad_active_days": 15,
            "sourcing_hub": "Surat Cluster",
            "marketplace_url": f"https://www.amazon.in/dp/{product_id}",
            "competitor_flaw": "Weak lid seal",
            "upgrade_v2": "Double-threaded silicone gasket",
            "suppliers": []
        }
        econ = {
            "status": "PASS",
            "score": 85.0,
            "landed_cogs": cogs,
            "gross_margin_pct": 73.0,
            "net_profit_pct": 28.0,
            "worst_case_stress_margin_pct": 14.0,
            "consensus_status": "CONSENSUS_PASS",
            "action_plan": "Proceed to sourcing"
        }
        record_product_evaluation(prod, econ)
        return product_id

    # -------------------------------------------------------------
    # 1. PRODUCT LAUNCH DETECTION
    # -------------------------------------------------------------

    def test_get_product_launch_info_unlaunched(self):
        """Unlaunched product has is_launched=False and launch_status='NOT_LAUNCHED'."""
        pid = self._create_dummy_product("PROD_UNLAUNCHED_01")
        info = get_product_launch_info(pid)
        self.assertFalse(info["is_launched"])
        self.assertEqual(info["launch_status"], "NOT_LAUNCHED")
        self.assertIsNone(info["effective_launch_date"])

    def test_get_product_launch_info_launched_via_launchpad(self):
        """Product added to launchpad with target_launch_date and LIVE status is recognized."""
        pid = self._create_dummy_product("PROD_LP_LAUNCHED_01")
        item_id = add_to_launchpad(
            product_id=pid,
            product_name="Smart Coffee Tumbler",
            target_moq=500,
            target_fob=350.0,
            target_launch_date="2026-09-01"
        )
        update_launchpad_status(item_id, launch_status="LIVE", po_generated=True)

        info = get_product_launch_info(pid)
        self.assertTrue(info["is_launched"])
        self.assertEqual(info["launch_status"], "LIVE")
        self.assertEqual(info["effective_launch_date"], datetime.date(2026, 9, 1))
        self.assertEqual(info["launchpad_item_id"], item_id)
        self.assertTrue(info["purchase_order_generated"])

    def test_get_product_launch_info_launched_via_master_status(self):
        """Product marked LAUNCHED in master_products is recognized."""
        pid = self._create_dummy_product("PROD_MASTER_LAUNCHED_01")
        cur = self.conn.cursor()
        cur.execute("UPDATE master_products SET status = 'LAUNCHED' WHERE product_id = ?", (pid,))
        self.conn.commit()

        info = get_product_launch_info(pid)
        self.assertTrue(info["is_launched"])
        self.assertEqual(info["launch_status"], "LAUNCHED")

    # -------------------------------------------------------------
    # 2. OBSERVATION WINDOW CALCULATION
    # -------------------------------------------------------------

    def test_compute_observation_windows_deterministic_dates(self):
        """Verify deterministic date bounds for DAY_30, DAY_60, and DAY_90."""
        launch_date = datetime.date(2026, 9, 1)
        windows = compute_observation_windows(launch_date)

        self.assertEqual(len(windows), 3)

        # DAY_30: 2026-09-01 to 2026-09-30 (30 days inclusive), due on 2026-10-01
        w30 = windows[0]
        self.assertEqual(w30["period_type"], "DAY_30")
        self.assertEqual(w30["period_start"], "2026-09-01")
        self.assertEqual(w30["period_end"], "2026-09-30")
        self.assertEqual(w30["due_date"], "2026-10-01")
        self.assertEqual(w30["duration_days"], 30)

        # DAY_60: 2026-09-01 to 2026-10-30 (60 days inclusive), due on 2026-10-31
        w60 = windows[1]
        self.assertEqual(w60["period_type"], "DAY_60")
        self.assertEqual(w60["period_start"], "2026-09-01")
        self.assertEqual(w60["period_end"], "2026-10-30")
        self.assertEqual(w60["due_date"], "2026-10-31")
        self.assertEqual(w60["duration_days"], 60)

        # DAY_90: 2026-09-01 to 2026-11-29 (90 days inclusive), due on 2026-11-30
        w90 = windows[2]
        self.assertEqual(w90["period_type"], "DAY_90")
        self.assertEqual(w90["period_start"], "2026-09-01")
        self.assertEqual(w90["period_end"], "2026-11-29")
        self.assertEqual(w90["due_date"], "2026-11-30")
        self.assertEqual(w90["duration_days"], 90)

    # -------------------------------------------------------------
    # 3. WINDOW MATURITY STATES (TIME TRAVEL EVALUATION)
    # -------------------------------------------------------------

    def test_window_maturity_not_due_before_window_completion(self):
        """When evaluated during the active observation window, status is NOT_DUE."""
        pid = self._create_dummy_product("PROD_TIME_NOT_DUE")
        item_id = add_to_launchpad(pid, "Coffee Tumbler", target_launch_date="2026-09-01")
        update_launchpad_status(item_id, launch_status="LIVE")

        window_30 = {
            "period_type": "DAY_30",
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "due_date": "2026-10-01",
            "duration_days": 30
        }

        # Evaluated on 2026-09-15 (16 days until due)
        res = evaluate_window_maturity(pid, window_30, as_of_date="2026-09-15")
        self.assertEqual(res["status"], WINDOW_STATUS_NOT_DUE)
        self.assertEqual(res["days_until_due"], 16)
        self.assertEqual(res["days_overdue"], 0)
        self.assertIsNone(res["outcome_id"])

    def test_window_maturity_due_within_grace_period(self):
        """When evaluated on or slightly after due date within grace period, status is DUE."""
        pid = self._create_dummy_product("PROD_TIME_DUE")
        item_id = add_to_launchpad(pid, "Coffee Tumbler", target_launch_date="2026-09-01")
        update_launchpad_status(item_id, launch_status="LIVE")

        window_30 = {
            "period_type": "DAY_30",
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "due_date": "2026-10-01",
            "duration_days": 30
        }

        # Evaluated on 2026-10-03 (2 days overdue, within default 7-day grace period)
        res = evaluate_window_maturity(pid, window_30, as_of_date="2026-10-03", grace_period_days=7)
        self.assertEqual(res["status"], WINDOW_STATUS_DUE)
        self.assertEqual(res["days_until_due"], 0)
        self.assertEqual(res["days_overdue"], 2)

    def test_window_maturity_overdue_beyond_grace_period(self):
        """When evaluated beyond grace period without outcome, status is OVERDUE."""
        pid = self._create_dummy_product("PROD_TIME_OVERDUE")
        item_id = add_to_launchpad(pid, "Coffee Tumbler", target_launch_date="2026-09-01")
        update_launchpad_status(item_id, launch_status="LIVE")

        window_30 = {
            "period_type": "DAY_30",
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "due_date": "2026-10-01",
            "duration_days": 30
        }

        # Evaluated on 2026-10-15 (14 days past due date, > 7-day grace period)
        res = evaluate_window_maturity(pid, window_30, as_of_date="2026-10-15", grace_period_days=7)
        self.assertEqual(res["status"], WINDOW_STATUS_OVERDUE)
        self.assertEqual(res["days_until_due"], 0)
        self.assertEqual(res["days_overdue"], 14)

    def test_window_maturity_observed_when_full_outcome_ingested(self):
        """When an outcome with all core metrics exists, status is OBSERVED."""
        pid = self._create_dummy_product("PROD_TIME_OBSERVED")
        dec_id = record_decision_snapshot(pid, decision_timestamp="2026-08-15 10:00:00")
        item_id = add_to_launchpad(pid, "Coffee Tumbler", target_launch_date="2026-09-01")
        update_launchpad_status(item_id, launch_status="LIVE")

        # Ingest complete DAY_30 outcome
        OutcomeIngestionService.ingest_outcome({
            "product_id": pid,
            "decision_id": dec_id,
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "period_type": "DAY_30",
            "actual_units_sold": 450,
            "actual_revenue": 584550.0,
            "actual_avg_selling_price": 1299.0,
            "actual_landed_cogs": 350.0,
            "actual_contribution_margin": 162500.0,
            "actual_cm_pct": 27.8,
            "actual_ad_spend": 54000.0,
            "actual_cac": 120.0
        })

        window_30 = {
            "period_type": "DAY_30",
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "due_date": "2026-10-01",
            "duration_days": 30
        }

        # Evaluated on 2026-10-15: even though date is past due, outcome exists -> OBSERVED!
        res = evaluate_window_maturity(pid, window_30, as_of_date="2026-10-15")
        self.assertEqual(res["status"], WINDOW_STATUS_OBSERVED)
        self.assertIsNotNone(res["outcome_id"])
        self.assertEqual(len(res["missing_core_metrics"]), 0)

    def test_window_maturity_partially_observed_when_partial_outcome_ingested(self):
        """When an outcome exists but core metrics are missing, status is PARTIALLY_OBSERVED."""
        pid = self._create_dummy_product("PROD_TIME_PARTIAL")
        dec_id = record_decision_snapshot(pid, decision_timestamp="2026-08-15 10:00:00")
        item_id = add_to_launchpad(pid, "Coffee Tumbler", target_launch_date="2026-09-01")
        update_launchpad_status(item_id, launch_status="LIVE")

        # Ingest partial outcome (revenue and units known, but COGS/CAC missing)
        OutcomeIngestionService.ingest_outcome({
            "product_id": pid,
            "decision_id": dec_id,
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "period_type": "DAY_30",
            "actual_units_sold": 450,
            "actual_revenue": 584550.0
        })

        window_30 = {
            "period_type": "DAY_30",
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "due_date": "2026-10-01",
            "duration_days": 30
        }

        res = evaluate_window_maturity(pid, window_30, as_of_date="2026-10-15")
        self.assertEqual(res["status"], WINDOW_STATUS_PARTIALLY_OBSERVED)
        self.assertIsNotNone(res["outcome_id"])
        self.assertGreater(len(res["missing_core_metrics"]), 0)

    # -------------------------------------------------------------
    # 4. PRODUCT OBSERVATION SCHEDULE & NEXT DUE IDENTIFICATION
    # -------------------------------------------------------------

    def test_product_schedule_unlaunched_handling(self):
        """Unlaunched product returns schedule_status=NOT_LAUNCHED and empty windows."""
        pid = self._create_dummy_product("PROD_SCHED_UNLAUNCHED")
        sched = ObservationScheduler.get_product_schedule(pid)
        self.assertEqual(sched["schedule_status"], WINDOW_STATUS_NOT_LAUNCHED)
        self.assertEqual(len(sched["windows"]), 0)
        self.assertIsNone(sched["next_expected_observation"])

    def test_product_schedule_and_next_expected_observation(self):
        """
        Verify that get_product_schedule returns windows and correctly identifies
        next expected observation according to priority (OVERDUE > DUE > NOT_DUE).
        """
        pid = self._create_dummy_product("PROD_SCHED_FLOW")
        item_id = add_to_launchpad(pid, "Coffee Tumbler", target_launch_date="2026-09-01")
        update_launchpad_status(item_id, launch_status="LIVE")

        # Scenario 1: Evaluated on 2026-09-15 -> DAY_30 is NOT_DUE, next expected is DAY_30
        s1 = ObservationScheduler.get_product_schedule(pid, as_of_date="2026-09-15")
        self.assertEqual(s1["schedule_status"], "UP_TO_DATE")
        self.assertEqual(len(s1["windows"]), 3)
        self.assertIsNotNone(s1["next_expected_observation"])
        self.assertEqual(s1["next_expected_observation"]["period_type"], "DAY_30")
        self.assertEqual(s1["next_expected_observation"]["status"], WINDOW_STATUS_NOT_DUE)

        # Scenario 2: Evaluated on 2026-10-03 -> DAY_30 is DUE, next expected is DAY_30
        s2 = ObservationScheduler.get_product_schedule(pid, as_of_date="2026-10-03")
        self.assertEqual(s2["schedule_status"], "HAS_DUE_OBSERVATIONS")
        self.assertEqual(s2["due_windows_count"], 1)
        self.assertEqual(s2["next_expected_observation"]["period_type"], "DAY_30")
        self.assertEqual(s2["next_expected_observation"]["status"], WINDOW_STATUS_DUE)

        # Scenario 3: Evaluated on 2026-10-20 -> DAY_30 is OVERDUE, next expected is DAY_30 (OVERDUE)
        s3 = ObservationScheduler.get_product_schedule(pid, as_of_date="2026-10-20")
        self.assertEqual(s3["schedule_status"], "HAS_OVERDUE_OBSERVATIONS")
        self.assertEqual(s3["overdue_windows_count"], 1)
        self.assertEqual(s3["next_expected_observation"]["period_type"], "DAY_30")
        self.assertEqual(s3["next_expected_observation"]["status"], WINDOW_STATUS_OVERDUE)

        # Scenario 4: Now ingest DAY_30 outcome; next expected becomes DAY_60
        dec_id = record_decision_snapshot(pid, decision_timestamp="2026-08-15 10:00:00")
        OutcomeIngestionService.ingest_outcome({
            "product_id": pid,
            "decision_id": dec_id,
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "period_type": "DAY_30",
            "actual_units_sold": 500,
            "actual_revenue": 649500.0,
            "actual_avg_selling_price": 1299.0,
            "actual_landed_cogs": 350.0,
            "actual_contribution_margin": 180000.0,
            "actual_cm_pct": 27.7,
            "actual_ad_spend": 60000.0,
            "actual_cac": 120.0
        })

        s4 = ObservationScheduler.get_product_schedule(pid, as_of_date="2026-10-20")
        self.assertEqual(s4["schedule_status"], "UP_TO_DATE")
        self.assertEqual(s4["observed_windows_count"], 1)
        self.assertEqual(s4["overdue_windows_count"], 0)
        # Next expected observation advances to DAY_60!
        self.assertIsNotNone(s4["next_expected_observation"])
        self.assertEqual(s4["next_expected_observation"]["period_type"], "DAY_60")
        self.assertEqual(s4["next_expected_observation"]["status"], WINDOW_STATUS_NOT_DUE)

    # -------------------------------------------------------------
    # 5. ACTIONABLE DUE OBSERVATIONS QUEUE & CATALOG SCHEDULES
    # -------------------------------------------------------------

    def test_get_due_observations_actionable_queue(self):
        """
        Verify get_due_observations returns a sorted, actionable list of only
        due and overdue observation windows across multiple products.
        """
        # Product 1: launched on 2026-08-01 (DAY_30 was due on 2026-08-31 -> OVERDUE on 2026-10-01)
        p1 = self._create_dummy_product("PROD_QUEUE_01", name="Product One")
        i1 = add_to_launchpad(p1, "Product One", target_launch_date="2026-08-01")
        update_launchpad_status(i1, launch_status="LIVE")

        # Product 2: launched on 2026-09-01 (DAY_30 due on 2026-10-01 -> DUE on 2026-10-03)
        p2 = self._create_dummy_product("PROD_QUEUE_02", name="Product Two")
        i2 = add_to_launchpad(p2, "Product Two", target_launch_date="2026-09-01")
        update_launchpad_status(i2, launch_status="LIVE")

        # Product 3: launched on 2026-09-20 (DAY_30 due on 2026-10-20 -> NOT_DUE on 2026-10-03)
        p3 = self._create_dummy_product("PROD_QUEUE_03", name="Product Three")
        i3 = add_to_launchpad(p3, "Product Three", target_launch_date="2026-09-20")
        update_launchpad_status(i3, launch_status="LIVE")

        # Evaluate due observations as of 2026-10-03
        due_queue = ObservationScheduler.get_due_observations(as_of_date="2026-10-03")

        # Product 1 (DAY_30 overdue) and Product 2 (DAY_30 due) should be in the queue; Product 3 should NOT.
        prod_ids = [item["product_id"] for item in due_queue]
        self.assertIn(p1, prod_ids)
        self.assertIn(p2, prod_ids)
        self.assertNotIn(p3, prod_ids)

        # Oldest due date should appear first
        self.assertEqual(due_queue[0]["product_id"], p1)
        self.assertEqual(due_queue[0]["status"], WINDOW_STATUS_OVERDUE)

    def test_catalog_schedules_and_maturity_summary(self):
        """Verify catalog schedules and aggregate maturity metrics."""
        p1 = self._create_dummy_product("PROD_CAT_01")
        i1 = add_to_launchpad(p1, "Product 1", target_launch_date="2026-08-01")
        update_launchpad_status(i1, launch_status="LIVE")

        p2 = self._create_dummy_product("PROD_CAT_02")
        i2 = add_to_launchpad(p2, "Product 2", target_launch_date="2026-09-01")
        update_launchpad_status(i2, launch_status="LIVE")

        summary = ObservationScheduler.get_maturity_summary(as_of_date="2026-10-03")
        self.assertEqual(summary["total_launched_products"], 2)
        # 2 products * 3 windows = 6 scheduled windows
        self.assertEqual(summary["total_scheduled_windows"], 6)
        self.assertGreaterEqual(summary["due_count"] + summary["overdue_count"], 2)

    # -------------------------------------------------------------
    # 6. RULE 0: ZERO SYNTHETIC OUTCOMES INVENTED
    # -------------------------------------------------------------

    def test_separation_of_concerns_zero_outcomes_invented(self):
        """
        CRITICAL INVARIANT (Rule 0):
        ObservationScheduler must NEVER insert or invent outcome records.
        """
        p = self._create_dummy_product("PROD_RULE0_01")
        i = add_to_launchpad(p, "Tumbler", target_launch_date="2026-08-01")
        update_launchpad_status(i, launch_status="LIVE")

        # Run scheduler queries
        ObservationScheduler.get_product_schedule(p, as_of_date="2026-10-03")
        ObservationScheduler.get_catalog_schedules(as_of_date="2026-10-03")
        ObservationScheduler.get_due_observations(as_of_date="2026-10-03")
        ObservationScheduler.get_maturity_summary(as_of_date="2026-10-03")

        # Confirm zero outcomes and zero calibrations exist
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM product_outcomes")
        self.assertEqual(cur.fetchone()[0], 0, "ObservationScheduler must never invent outcomes.")

        cur.execute("SELECT COUNT(*) FROM prediction_calibrations")
        self.assertEqual(cur.fetchone()[0], 0, "ObservationScheduler must never insert calibrations.")

    # -------------------------------------------------------------
    # 7. PRODUCTION DATABASE PURITY (ZERO CONTAMINATION)
    # -------------------------------------------------------------

    def test_no_synthetic_production_contamination(self):
        """
        Verify that all tests ran in isolated databases and the authoritative
        production database at data/research_engine.db contains zero synthetic rows.
        """
        prod_db_file = Path("data/research_engine.db")
        if not prod_db_file.exists():
            return

        p_conn = sqlite3.connect(str(prod_db_file))
        p_cur = p_conn.cursor()

        p_cur.execute("SELECT COUNT(*) FROM decision_ledger")
        self.assertEqual(p_cur.fetchone()[0], 0, "Production decision_ledger must remain 0.")

        p_cur.execute("SELECT COUNT(*) FROM product_outcomes")
        self.assertEqual(p_cur.fetchone()[0], 0, "Production product_outcomes must remain 0.")

        p_cur.execute("SELECT COUNT(*) FROM prediction_calibrations")
        self.assertEqual(p_cur.fetchone()[0], 0, "Production prediction_calibrations must remain 0.")

        p_conn.close()
