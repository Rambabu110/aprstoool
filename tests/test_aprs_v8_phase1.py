"""
APRS V8 Phase 1 — Decision Ledger + Outcome Data Foundation Tests
===================================================================
Forensic validation of:
1. Immutable Decision Ledger (snapshots, nullable predictions, immutability trigger, duplicate handling)
2. Post-Launch Product Outcomes (partial data, NULL vs ZERO preservation, integrity validation, idempotency)
3. Foreign key integrity and cascading behaviors
4. Integration with existing Sourcing Launchpad
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
    add_to_launchpad,
    get_launchpad_items,
    record_decision_snapshot,
    get_decision_snapshot,
    get_decision_snapshots_for_product,
    get_latest_decision_snapshot,
    validate_outcome_payload,
    record_product_outcome,
    get_product_outcomes,
    get_outcome_by_id,
    get_all_outcomes,
    get_product_timeline,
)


class TestAPRSV8Phase1(unittest.TestCase):

    def setUp(self):
        # Create an isolated temporary SQLite database for each test
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_v8_engine.db"
        os.environ["APRS_DB_PATH"] = str(self.db_path)
        init_db()
        self.conn = get_connection()

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    def _create_dummy_product(self, product_id="PROD_V8_001", name="Smart Aroma Diffuser Pro", msrp=1299.0, cogs=350.0):
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
            "estimated_daily_units": 25,
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
    # 1. DATABASE SCHEMA & INTEGRITY TESTS
    # -------------------------------------------------------------

    def test_fresh_db_initialization_includes_v8_tables(self):
        """Verify that fresh init_db creates decision_ledger and product_outcomes without FK violations."""
        cur = self.conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = {row[0] for row in cur.fetchall()}

        self.assertIn("decision_ledger", tables)
        self.assertIn("product_outcomes", tables)
        self.assertGreaterEqual(len(tables), 32)

        cur.execute("PRAGMA foreign_key_check")
        violations = cur.fetchall()
        self.assertEqual(len(violations), 0, f"FK violations found in fresh DB: {violations}")

        cur.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
        triggers = {row[0] for row in cur.fetchall()}
        self.assertIn("trg_decision_ledger_immutable", triggers)

    def test_v8_indexes_exist(self):
        """Verify that all required performance indexes exist on V8 tables."""
        cur = self.conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = {row[0] for row in cur.fetchall()}

        required_indexes = {
            "idx_decision_ledger_prod_time",
            "idx_decision_ledger_type",
            "idx_product_outcomes_prod_start",
            "idx_product_outcomes_decision",
            "idx_product_outcomes_period",
            "idx_product_outcomes_source",
        }
        self.assertTrue(required_indexes.issubset(indexes), f"Missing indexes: {required_indexes - indexes}")

    # -------------------------------------------------------------
    # 2. DECISION LEDGER SNAPSHOT & IMMUTABILITY TESTS
    # -------------------------------------------------------------

    def test_decision_ledger_create_snapshot_with_predictions(self):
        """Snapshot must freeze score, confidence, kill status, and all available prediction fields."""
        pid = self._create_dummy_product("PROD_SNAP_001")

        # Add intelligence profile
        save_product_intelligence(
            product_id=pid,
            opportunity_score=84.5,
            kill_status="SURVIVES",
            kill_reasons=[],
            kill_evidence=[],
            scorecard={"demand": 85.0, "economics": 84.0},
            signals={"trend": "RISING"},
            confidence_score=78.0
        )

        # Add economics assessment
        cur = self.conn.cursor()
        cur.execute('''
            INSERT INTO economics_assessments (
                product_id, scenario, msrp, fob_cost, contribution_margin_pct, rto_reserve
            ) VALUES (?, 'EXPECTED', 1299.0, 350.0, 31.4, 95.0)
        ''', (pid,))
        self.conn.commit()

        # Capture snapshot
        dec_id = record_decision_snapshot(
            product_id=pid,
            decision_type="LAUNCHPAD_COMMITMENT",
            policy_version="V7.2",
            model_version="V7.2_HEURISTIC"
        )
        self.assertGreater(dec_id, 0)

        snapshot = get_decision_snapshot(dec_id)
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot["product_id"], pid)
        self.assertEqual(snapshot["decision_type"], "LAUNCHPAD_COMMITMENT")
        self.assertAlmostEqual(snapshot["frozen_score"], 84.5, places=1)
        self.assertAlmostEqual(snapshot["frozen_confidence"], 78.0, places=1)
        self.assertEqual(snapshot["frozen_kill_status"], "SURVIVES")
        self.assertEqual(snapshot["predicted_daily_units"], 25)
        self.assertAlmostEqual(snapshot["predicted_selling_price"], 1299.0, places=1)
        self.assertAlmostEqual(snapshot["predicted_cogs"], 350.0, places=1)
        self.assertAlmostEqual(snapshot["predicted_cm_pct"], 31.4, places=1)
        self.assertAlmostEqual(snapshot["predicted_cac"], 120.0, places=1)
        self.assertEqual(snapshot["policy_version"], "V7.2")
        self.assertEqual(snapshot["model_version"], "V7.2_HEURISTIC")

        # Snapshot payload must contain full contextual reconstruction data
        payload = snapshot["snapshot_payload"]
        self.assertIn("product_snapshot", payload)
        self.assertIn("intelligence_snapshot", payload)
        self.assertIn("economics_snapshot", payload)
        self.assertEqual(payload["product_id"], pid)

    def test_decision_ledger_nullable_predictions_remain_null(self):
        """Unknown predictions must remain strictly NULL — never defaulted to 0.0."""
        # Minimal product with 0 CAC, no economics assessment, no intelligence
        cur = self.conn.cursor()
        cur.execute('''
            INSERT INTO master_products (
                product_id, name, category, region, planned_msrp, landed_cogs,
                gross_margin_pct, estimated_cac, net_profit_pct, worst_case_stress_margin_pct,
                status, overall_score, consensus_status, estimated_daily_units
            ) VALUES ('PROD_NULL_001', 'Minimal SKU', 'Home', 'India', 499.0, 0.0, 0.0, 0.0, 0.0, 0.0, 'PENDING', 50.0, 'PENDING', NULL)
        ''')
        self.conn.commit()

        dec_id = record_decision_snapshot("PROD_NULL_001")
        snapshot = get_decision_snapshot(dec_id)

        self.assertIsNone(snapshot["predicted_daily_units"])
        self.assertIsNone(snapshot["predicted_cogs"])
        self.assertIsNone(snapshot["predicted_cm_pct"])
        self.assertIsNone(snapshot["predicted_rto_pct"])
        self.assertIsNone(snapshot["predicted_cac"])
        self.assertEqual(snapshot["predicted_selling_price"], 499.0)

    def test_decision_ledger_survives_later_product_reevaluation(self):
        """Later product re-evaluations must NOT overwrite or modify historical decision snapshots."""
        pid = self._create_dummy_product("PROD_IMMUT_001", msrp=1000.0, cogs=300.0)
        save_product_intelligence(pid, opportunity_score=85.0, kill_status="SURVIVES", confidence_score=80.0)

        dec_id = record_decision_snapshot(pid, decision_type="LAUNCHPAD_COMMITMENT")
        original_snap = get_decision_snapshot(dec_id)
        self.assertEqual(original_snap["frozen_score"], 85.0)
        self.assertEqual(original_snap["frozen_kill_status"], "SURVIVES")

        # Simulate later re-evaluation with drastic changes
        cur = self.conn.cursor()
        cur.execute("UPDATE master_products SET planned_msrp = 2500.0 WHERE product_id = ?", (pid,))
        self.conn.commit()
        save_product_intelligence(pid, opportunity_score=22.0, kill_status="KILL_DEFECT_RISK", confidence_score=95.0)

        # Retrieve historical snapshot again
        frozen_snap = get_decision_snapshot(dec_id)
        self.assertEqual(frozen_snap["frozen_score"], 85.0)
        self.assertEqual(frozen_snap["frozen_kill_status"], "SURVIVES")
        self.assertEqual(frozen_snap["predicted_selling_price"], 1000.0)

        # Verify latest snapshot query
        history = get_decision_snapshots_for_product(pid)
        self.assertEqual(len(history), 1)

    def test_decision_ledger_immutability_enforced_by_trigger(self):
        """Direct SQL UPDATE against decision_ledger must raise IntegrityError via database trigger."""
        pid = self._create_dummy_product("PROD_TRIG_001")
        dec_id = record_decision_snapshot(pid)

        cur = self.conn.cursor()
        with self.assertRaises(sqlite3.IntegrityError) as ctx:
            cur.execute("UPDATE decision_ledger SET frozen_score = 99.9 WHERE decision_id = ?", (dec_id,))
        self.assertIn("immutable", str(ctx.exception).lower())

    def test_decision_ledger_duplicate_deterministic_handling(self):
        """Calling record_decision_snapshot with identical state must return existing ID idempotently."""
        pid = self._create_dummy_product("PROD_DUP_001")
        id1 = record_decision_snapshot(pid, decision_type="LAUNCHPAD_COMMITMENT")
        id2 = record_decision_snapshot(pid, decision_type="LAUNCHPAD_COMMITMENT")
        self.assertEqual(id1, id2)

        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM decision_ledger WHERE product_id = ?", (pid,))
        self.assertEqual(cur.fetchone()[0], 1)

    def test_decision_ledger_rejects_nonexistent_product(self):
        """Attempting to snapshot a product not in master_products must raise ValueError."""
        with self.assertRaises(ValueError) as ctx:
            record_decision_snapshot("SKU_DOES_NOT_EXIST")
        self.assertIn("does not exist", str(ctx.exception))

    def test_add_to_launchpad_captures_decision_snapshot(self):
        """Adding a product to Launchpad must automatically capture an authoritative commitment snapshot."""
        pid = self._create_dummy_product("PROD_LP_HOOK_001")
        lid = add_to_launchpad(
            product_id=pid,
            product_name="Smart Aroma Diffuser Pro",
            target_moq=500,
            target_fob=320.0,
            target_launch_date="2026-11-01",
            confirmed_factory_name="Surat Tech Fabricators"
        )
        self.assertGreater(lid, 0)

        latest = get_latest_decision_snapshot(pid, decision_type="LAUNCHPAD_COMMITMENT")
        self.assertIsNotNone(latest)
        self.assertEqual(latest["product_id"], pid)
        self.assertEqual(latest["decision_type"], "LAUNCHPAD_COMMITMENT")
        self.assertEqual(latest["predicted_cogs"], 320.0)

    # -------------------------------------------------------------
    # 3. PRODUCT OUTCOMES VALIDATION & DATA INTEGRITY TESTS
    # -------------------------------------------------------------

    def test_outcome_validation_rejects_negative_metrics(self):
        """Outcome validation must reject negative units, revenue, returns, costs, and ad spend."""
        invalid_cases = [
            {"actual_units_sold": -10},
            {"actual_revenue": -500.0},
            {"actual_avg_selling_price": -50.0},
            {"actual_landed_cogs": -20.0},
            {"actual_returns_count": -1},
            {"actual_rto_count": -5},
            {"actual_ad_spend": -100.0},
            {"actual_cac": -15.0},
            {"actual_inventory": -100},
            {"actual_stockout_days": -2},
        ]
        base = {
            "product_id": "TEST_PROD",
            "period_start": "2026-08-01",
            "period_end": "2026-08-31",
            "period_type": "DAY_30"
        }
        for bad_metric in invalid_cases:
            payload = {**base, **bad_metric}
            with self.assertRaises(ValueError, msg=f"Should reject: {bad_metric}"):
                validate_outcome_payload(payload)

    def test_outcome_validation_rejects_invalid_dates_and_periods(self):
        """Validation must reject period_end < period_start, malformed dates, and unsupported period types."""
        base = {"product_id": "TEST_PROD"}

        # End before start
        with self.assertRaises(ValueError) as ctx:
            validate_outcome_payload({**base, "period_start": "2026-09-30", "period_end": "2026-09-01", "period_type": "DAY_30"})
        self.assertIn("cannot be before", str(ctx.exception))

        # Malformed date string
        with self.assertRaises(ValueError):
            validate_outcome_payload({**base, "period_start": "yesterday", "period_end": "tomorrow", "period_type": "DAY_30"})

        # Unsupported period type
        with self.assertRaises(ValueError) as ctx:
            validate_outcome_payload({**base, "period_start": "2026-08-01", "period_end": "2026-08-31", "period_type": "ANNUAL_2026"})
        self.assertIn("Invalid period_type", str(ctx.exception))

    def test_outcome_validation_rejects_returns_exceeding_units(self):
        """Validation must detect logical impossibility: returns > units sold or RTO > units sold."""
        base = {
            "product_id": "TEST_PROD",
            "period_start": "2026-08-01",
            "period_end": "2026-08-31",
            "period_type": "DAY_30",
            "actual_units_sold": 50
        }
        # Returns > units
        with self.assertRaises(ValueError) as ctx:
            validate_outcome_payload({**base, "actual_returns_count": 60})
        self.assertIn("cannot exceed", str(ctx.exception))

        # RTO > units
        with self.assertRaises(ValueError) as ctx:
            validate_outcome_payload({**base, "actual_rto_count": 55})
        self.assertIn("cannot exceed", str(ctx.exception))

    def test_outcome_validation_percentage_bounds(self):
        """Return rate and RTO rate must be bounded between 0% and 100%."""
        base = {
            "product_id": "TEST_PROD",
            "period_start": "2026-08-01",
            "period_end": "2026-08-31",
            "period_type": "DAY_30"
        }
        with self.assertRaises(ValueError):
            validate_outcome_payload({**base, "actual_return_rate_pct": 105.0})
        with self.assertRaises(ValueError):
            validate_outcome_payload({**base, "actual_rto_rate_pct": -2.0})

    # -------------------------------------------------------------
    # 4. PRODUCT OUTCOMES STORAGE & IDEMPOTENCY TESTS
    # -------------------------------------------------------------

    def test_outcome_full_record_and_foreign_keys(self):
        """Create full outcome record with valid decision_id foreign key link."""
        pid = self._create_dummy_product("PROD_OUT_001")
        dec_id = record_decision_snapshot(pid)

        outcome_data = {
            "product_id": pid,
            "decision_id": dec_id,
            "period_start": "2026-08-01",
            "period_end": "2026-08-31",
            "period_type": "DAY_30",
            "actual_units_sold": 450,
            "actual_revenue": 584550.0,
            "actual_avg_selling_price": 1299.0,
            "actual_landed_cogs": 350.0,
            "actual_contribution_margin": 162500.0,
            "actual_cm_pct": 27.8,
            "actual_returns_count": 18,
            "actual_return_rate_pct": 4.0,
            "actual_rto_count": 45,
            "actual_rto_rate_pct": 10.0,
            "actual_ad_spend": 54000.0,
            "actual_cac": 120.0,
            "actual_inventory": 150,
            "actual_stockout_days": 2,
            "data_source": "MANUAL",
            "source_record_id": "BATCH_2026_08_001",
            "notes": "First month post-launch performance"
        }

        res = record_product_outcome(outcome_data)
        self.assertEqual(res["status"], "CREATED")
        outcome_id = res["outcome_id"]
        self.assertGreater(outcome_id, 0)

        saved = get_outcome_by_id(outcome_id)
        self.assertIsNotNone(saved)
        self.assertEqual(saved["product_id"], pid)
        self.assertEqual(saved["decision_id"], dec_id)
        self.assertEqual(saved["actual_units_sold"], 450)
        self.assertAlmostEqual(saved["actual_revenue"], 584550.0, places=1)
        self.assertAlmostEqual(saved["actual_cm_pct"], 27.8, places=1)
        self.assertEqual(saved["actual_stockout_days"], 2)
        self.assertEqual(saved["source_record_id"], "BATCH_2026_08_001")

    def test_outcome_partial_record_null_vs_zero_distinction(self):
        """CRITICAL: NULL metrics must remain NULL and 0 must remain 0."""
        pid = self._create_dummy_product("PROD_PARTIAL_001")

        # Scenario: Observed zero units sold, ad spend was spent, but CAC and inventory are unknown
        partial_data = {
            "product_id": pid,
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "period_type": "DAY_30",
            "actual_units_sold": 0,           # Obs: zero units sold
            "actual_revenue": 0.0,            # Obs: zero revenue
            "actual_returns_count": 0,        # Obs: zero returns
            "actual_ad_spend": 1500.0,        # Obs: 1500 spent on test ads
            "actual_cac": None,               # Unknown / undefined (no conversions)
            "actual_landed_cogs": None,       # Unknown
            "actual_contribution_margin": -1500.0,
            "actual_inventory": None,         # Unknown
            "actual_stockout_days": None,     # Unknown
        }

        res = record_product_outcome(partial_data)
        saved = get_outcome_by_id(res["outcome_id"])

        # Strict checks: 0 is 0
        self.assertEqual(saved["actual_units_sold"], 0)
        self.assertEqual(saved["actual_revenue"], 0.0)
        self.assertEqual(saved["actual_returns_count"], 0)

        # Strict checks: None is None (NOT converted to 0)
        self.assertIsNone(saved["actual_cac"])
        self.assertIsNone(saved["actual_landed_cogs"])
        self.assertIsNone(saved["actual_inventory"])
        self.assertIsNone(saved["actual_stockout_days"])

    def test_outcome_idempotency_duplicate_and_update(self):
        """Outcome ingestion must detect duplicate records and support safe updating when specified."""
        pid = self._create_dummy_product("PROD_IDEMP_001")

        outcome_data = {
            "product_id": pid,
            "period_start": "2026-08-01",
            "period_end": "2026-08-31",
            "period_type": "DAY_30",
            "actual_units_sold": 100,
            "actual_revenue": 100000.0
        }

        # First insert
        res1 = record_product_outcome(outcome_data)
        self.assertEqual(res1["status"], "CREATED")
        oid = res1["outcome_id"]

        # Duplicate identical insert -> IDEMPOTENT_DUPLICATE
        res2 = record_product_outcome(outcome_data)
        self.assertEqual(res2["status"], "IDEMPOTENT_DUPLICATE")
        self.assertEqual(res2["outcome_id"], oid)

        # Conflict insert with different metrics and update_if_exists=False -> ValueError
        conflict_data = {**outcome_data, "actual_units_sold": 120}
        with self.assertRaises(ValueError) as ctx:
            record_product_outcome(conflict_data, update_if_exists=False)
        self.assertIn("already exists", str(ctx.exception))

        # Safe update with update_if_exists=True -> UPDATED
        res3 = record_product_outcome(conflict_data, update_if_exists=True)
        self.assertEqual(res3["status"], "UPDATED")
        self.assertEqual(res3["outcome_id"], oid)

        updated_row = get_outcome_by_id(oid)
        self.assertEqual(updated_row["actual_units_sold"], 120)

    def test_outcome_cascade_delete_on_product_removal(self):
        """Deleting a master product must cascade delete all decision snapshots and outcomes."""
        pid = self._create_dummy_product("PROD_CASC_001")
        dec_id = record_decision_snapshot(pid)
        res = record_product_outcome({
            "product_id": pid,
            "decision_id": dec_id,
            "period_start": "2026-08-01",
            "period_end": "2026-08-31",
            "period_type": "DAY_30",
            "actual_units_sold": 100
        })

        cur = self.conn.cursor()
        cur.execute("DELETE FROM master_products WHERE product_id = ?", (pid,))
        self.conn.commit()

        cur.execute("SELECT COUNT(*) FROM decision_ledger WHERE product_id = ?", (pid,))
        self.assertEqual(cur.fetchone()[0], 0)

        cur.execute("SELECT COUNT(*) FROM product_outcomes WHERE product_id = ?", (pid,))
        self.assertEqual(cur.fetchone()[0], 0)

        cur.execute("PRAGMA foreign_key_check")
        self.assertEqual(len(cur.fetchall()), 0)

    def test_timeline_events_recorded_for_v8_actions(self):
        """Recording decision snapshots and outcomes must log audit events to intelligence_timeline."""
        pid = self._create_dummy_product("PROD_TIME_001")
        dec_id = record_decision_snapshot(pid)
        record_product_outcome({
            "product_id": pid,
            "decision_id": dec_id,
            "period_start": "2026-08-01",
            "period_end": "2026-08-31",
            "period_type": "DAY_30",
            "actual_units_sold": 50
        })

        timeline = get_product_timeline(pid)
        event_types = [e["event_type"] for e in timeline]
        self.assertIn("DECISION_FROZEN", event_types)
        self.assertIn("OUTCOME_RECORDED", event_types)


if __name__ == "__main__":
    unittest.main(verbosity=2)
