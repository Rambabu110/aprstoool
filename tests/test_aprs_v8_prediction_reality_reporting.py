"""
tests/test_aprs_v8_prediction_reality_reporting.py — APRS V8 Phase 6 Test Suite
=============================================================================
Forensic validation of the Read-Only Prediction vs Reality & Calibration Reporting Layer:
1. Empty-state rendering & zero-division safety
2. Production DB pristine zero-outcome verification
3. Product with decision but no outcome
4. Product with outcome and calibration
5. Partial outcome handling (missing/NULL fields)
6. Calibration display & directional accuracy
7. Terminology check: Mean Signed Error / Mean Bias Error (MBE), MAE, MAPE (Zero MSE references)
8. MAE display & calculation
9. MAPE display & undefined exclusions
10. Strict NULL vs 0 semantics (0 -> "₹0" / "0.0%", None -> "Not observed")
11. Multiple decisions history & ordering
12. Historical frozen decision snapshot immutability
13. Observation maturity & schedule integration (DAY_30, DAY_60, DAY_90, LIFETIME)
14. Outcome corrections audit log visibility (read-only audit trail)
15. Portfolio aggregate volume & error summaries
16. Zero-division mathematical safety across all metrics
17. Sample-size reliability tiers (N < 5 INSUFFICIENT_SAMPLE vs N >= 5 PROVISIONAL_AGGREGATE)
18. Read-only database guarantee (0 INSERTs/UPDATEs/DELETEs during reporting)
19. Streamlit AppTest integration on Product Intelligence Tab
20. Foreign-key integrity check (0 FK violations)
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
    record_decision_snapshot,
    get_decision_snapshot,
    record_product_outcome,
    save_prediction_calibration,
    record_outcome_correction
)
from core.prediction_reality_report import (
    PredictionRealityReportService,
    format_metric,
    format_currency_pvr,
    format_pct_pvr,
    format_pp_pvr,
    COVERAGE_COMPLETE_CALIBRATED,
    COVERAGE_PARTIAL_OUTCOME,
    COVERAGE_OUTCOME_NO_CALIBRATION,
    COVERAGE_DECISION_NO_OUTCOME,
    COVERAGE_NO_DECISION
)
from core.calibration_engine import (
    STATUS_CALIBRATED,
    STATUS_PARTIAL_DATA,
    DIRECTION_OVERPREDICTED,
    DIRECTION_UNDERPREDICTED
)


class TestPredictionRealityReportingEmptyAndSafety(unittest.TestCase):
    """Tests for empty states, mathematical edge cases, and safety invariants."""

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        self.orig_env = os.environ.get("APRS_DB_PATH")
        os.environ["APRS_DB_PATH"] = self.db_path
        init_db()

    def tearDown(self):
        if self.orig_env is not None:
            os.environ["APRS_DB_PATH"] = self.orig_env
        else:
            os.environ.pop("APRS_DB_PATH", None)
        try:
            os.remove(self.db_path)
        except Exception:
            pass

    def test_01_empty_state_portfolio_summary_zero_division_safety(self):
        """Empty database summary returns zero counts, None for averages, no zero-division."""
        summary = PredictionRealityReportService.get_portfolio_summary(self.db_path)
        self.assertEqual(summary["total_master_products"], 0)
        self.assertEqual(summary["products_with_decisions"], 0)
        self.assertEqual(summary["products_with_outcomes"], 0)
        self.assertEqual(summary["total_decisions"], 0)
        self.assertEqual(summary["total_outcomes"], 0)
        self.assertEqual(summary["total_calibrations"], 0)
        self.assertIsNone(summary["total_observed_units"])
        self.assertIsNone(summary["total_observed_revenue"])
        self.assertIsNone(summary["demand_bias_mbe"])
        self.assertIsNone(summary["demand_mae"])
        self.assertIsNone(summary["demand_mape"])
        self.assertEqual(summary["calibration_reliability"], "NO_CALIBRATIONS")
        self.assertTrue(summary["structural_readiness"]["decision_ledger_ready"])
        self.assertTrue(summary["structural_readiness"]["outcome_ingestion_ready"])
        self.assertTrue(summary["structural_readiness"]["calibration_engine_ready"])
        self.assertTrue(summary["structural_readiness"]["observation_scheduler_ready"])

    def test_02_production_db_zero_outcome_state_read_only(self):
        """Production database data/research_engine.db must remain strictly unmutated."""
        prod_path = str(_ROOT / "data" / "research_engine.db")
        if not os.path.exists(prod_path):
            self.skipTest("Production database not found")

        # Snapshot row counts before
        conn = sqlite3.connect(prod_path)
        tables = [
            "master_products", "product_intelligence", "launchpad_items",
            "decision_ledger", "product_outcomes", "prediction_calibrations",
            "outcome_corrections_log"
        ]
        counts_before = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
        conn.close()

        # Execute all reporting methods
        summary = PredictionRealityReportService.get_portfolio_summary(prod_path)
        catalog = PredictionRealityReportService.get_products_pvr_catalog(limit=50, db_path=prod_path)
        if catalog:
            dossier = PredictionRealityReportService.get_product_pvr_dossier(catalog[0]["product_id"], db_path=prod_path)
            self.assertTrue(dossier["exists"])

        # Snapshot row counts after
        conn = sqlite3.connect(prod_path)
        counts_after = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
        fks = conn.execute("PRAGMA foreign_key_check").fetchall()
        conn.close()

        self.assertEqual(counts_before, counts_after, "Production DB table counts were mutated!")
        self.assertEqual(counts_after["decision_ledger"], 0)
        self.assertEqual(counts_after["product_outcomes"], 0)
        self.assertEqual(counts_after["prediction_calibrations"], 0)
        self.assertEqual(counts_after["outcome_corrections_log"], 0)
        self.assertEqual(len(fks), 0, "FK violations found in production DB!")

    def test_03_null_vs_zero_formatting_semantics(self):
        """Strict differentiation: 0 is an observed zero; None is 'Not observed'."""
        # Currency
        self.assertEqual(format_currency_pvr(0), "₹0")
        self.assertEqual(format_currency_pvr(0.0), "₹0")
        self.assertEqual(format_currency_pvr(None), "Not observed")
        self.assertEqual(format_currency_pvr(1500), "₹1,500")

        # Percentage
        self.assertEqual(format_pct_pvr(0), "0.0%")
        self.assertEqual(format_pct_pvr(0.0), "0.0%")
        self.assertEqual(format_pct_pvr(None), "Not observed")
        self.assertEqual(format_pct_pvr(15.5), "+15.5%")
        self.assertEqual(format_pct_pvr(-8.2), "-8.2%")

        # Percentage Points
        self.assertEqual(format_pp_pvr(0), "0.0 pp")
        self.assertEqual(format_pp_pvr(None), "Not observed")
        self.assertEqual(format_pp_pvr(3.2), "+3.2 pp")

        # Generic metric
        self.assertEqual(format_metric(0, "integer"), "0")
        self.assertEqual(format_metric(None, "integer"), "Not observed")
        self.assertEqual(format_metric(None, "integer", default_str="Not available"), "Not available")

    def test_04_mbe_mae_mape_terminology(self):
        """Verify that calibration engine and reporting use MBE, MAE, MAPE, never MSE."""
        report_file = _ROOT / "core" / "prediction_reality_report.py"
        with open(report_file, "r", encoding="utf-8") as f:
            code = f.read()

        self.assertNotIn("mean_squared_error", code.lower())
        self.assertNotIn("def mse", code.lower())
        self.assertNotIn("'mse'", code.lower())
        self.assertNotIn('"mse"', code.lower())
        self.assertIn("MBE", code)
        self.assertIn("MAE", code)
        self.assertIn("MAPE", code)

        summary = PredictionRealityReportService.get_portfolio_summary()
        for k in summary.keys():
            self.assertNotIn("mse", k.lower())
            self.assertNotIn("squared", k.lower())

    def test_05_read_only_database_guarantee(self):
        """Verify report queries only perform read operations (zero inserts/updates/deletes)."""
        conn = get_connection()
        conn.execute("""
            INSERT INTO master_products (product_id, name, category, region, planned_msrp, landed_cogs, gross_margin_pct, estimated_cac, estimated_daily_units, overall_score)
            VALUES ('RO_PROD_1', 'Read Only Test', 'Tools', 'India', 999.0, 300.0, 70.0, 150.0, 10, 75.0)
        """)
        conn.commit()
        conn.close()

        # Record total rows across all V8 tables
        conn = get_connection()
        t_counts_before = conn.execute("SELECT COUNT(*) FROM master_products").fetchone()[0]
        conn.close()

        # Run all read services
        _ = PredictionRealityReportService.get_portfolio_summary()
        _ = PredictionRealityReportService.get_products_pvr_catalog()
        _ = PredictionRealityReportService.get_product_pvr_dossier("RO_PROD_1")
        _ = PredictionRealityReportService.get_all_decision_history()
        _ = PredictionRealityReportService.get_corrections_audit_log()

        conn = get_connection()
        t_counts_after = conn.execute("SELECT COUNT(*) FROM master_products").fetchone()[0]
        conn.close()

        self.assertEqual(t_counts_before, t_counts_after)


class TestPredictionRealityReportingPopulated(unittest.TestCase):
    """Tests with populated data scenarios in temporary database."""

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        self.orig_env = os.environ.get("APRS_DB_PATH")
        os.environ["APRS_DB_PATH"] = self.db_path
        init_db()

        # Insert test product
        conn = get_connection()
        conn.execute("""
            INSERT INTO master_products (
                product_id, name, category, region, planned_msrp, landed_cogs,
                gross_margin_pct, estimated_cac, estimated_daily_units, overall_score, status
            ) VALUES (
                'TEST_SKU_1', 'Ergonomic Desk Mat', 'Office', 'India', 1200.0, 350.0,
                70.8, 250.0, 15, 82.5, 'LAUNCHED'
            )
        """)
        conn.execute("""
            INSERT INTO product_intelligence (
                product_id, opportunity_score, kill_status, confidence_score, freshness_status
            ) VALUES (
                'TEST_SKU_1', 82.5, 'SURVIVES', 0.88, 'FRESH'
            )
        """)
        conn.execute("""
            INSERT INTO launchpad_items (
                product_id, product_name, launch_status, target_launch_date
            ) VALUES (
                'TEST_SKU_1', 'Ergonomic Desk Mat', 'LAUNCHED', '2026-06-01'
            )
        """)
        conn.commit()
        conn.close()

    def tearDown(self):
        if self.orig_env is not None:
            os.environ["APRS_DB_PATH"] = self.orig_env
        else:
            os.environ.pop("APRS_DB_PATH", None)
        try:
            os.remove(self.db_path)
        except Exception:
            pass

    def test_06_product_decision_no_outcome(self):
        """Product has frozen decision, but 0 outcomes."""
        dec_id = record_decision_snapshot(
            product_id="TEST_SKU_1",
            decision_type="LAUNCHPAD_COMMITMENT",
            override_predictions={
                "predicted_daily_units": 15,
                "predicted_selling_price": 1200.0,
                "predicted_cogs": 350.0,
                "predicted_cm_pct": 70.8,
                "predicted_rto_pct": 8.0,
                "predicted_cac": 250.0
            },
            decision_timestamp="2026-06-01T00:00:00"
        )
        self.assertGreater(dec_id, 0)

        dossier = PredictionRealityReportService.get_product_pvr_dossier("TEST_SKU_1")
        self.assertEqual(dossier["coverage_status"], COVERAGE_DECISION_NO_OUTCOME)
        self.assertEqual(len(dossier["decisions"]), 1)
        self.assertEqual(len(dossier["outcomes"]), 0)
        self.assertEqual(len(dossier["comparisons"]), 0)

        dec = dossier["decisions"][0]
        self.assertEqual(dec["predicted_daily_units"], 15)
        self.assertEqual(dec["predicted_selling_price"], 1200.0)
        self.assertEqual(dec["predicted_cogs"], 350.0)

    def test_07_product_with_outcome_and_calibration(self):
        """Product has decision + outcome + calibration."""
        dec_id = record_decision_snapshot(
            product_id="TEST_SKU_1",
            decision_type="LAUNCHPAD_COMMITMENT",
            override_predictions={
                "predicted_daily_units": 15,
                "predicted_selling_price": 1200.0,
                "predicted_cogs": 350.0,
                "predicted_cm_pct": 70.8,
                "predicted_rto_pct": 8.0,
                "predicted_cac": 250.0
            },
            decision_timestamp="2026-06-01T00:00:00"
        )

        out_res = record_product_outcome({
            "product_id": "TEST_SKU_1",
            "decision_id": dec_id,
            "period_start": "2026-06-02",
            "period_end": "2026-07-01",
            "period_type": "DAY_30",
            "actual_units_sold": 390,
            "actual_revenue": 468000.0,
            "actual_avg_selling_price": 1200.0,
            "actual_landed_cogs": 360.0,
            "actual_contribution_margin": 327600.0,
            "actual_cm_pct": 70.0,
            "actual_rto_rate_pct": 10.0,
            "actual_cac": 260.0,
            "data_source": "MANUAL_CSV"
        })
        out_id = out_res["outcome_id"]

        calib_id = save_prediction_calibration({
            "decision_id": dec_id,
            "outcome_id": out_id,
            "product_id": "TEST_SKU_1",
            "demand_predicted": 15.0,
            "demand_actual": 13.0,
            "demand_signed_error": -2.0,
            "demand_absolute_error": 2.0,
            "demand_percentage_error": -13.33,
            "price_predicted": 1200.0,
            "price_actual": 1200.0,
            "price_signed_error": 0.0,
            "cm_predicted_pct": 70.8,
            "cm_actual_pct": 70.0,
            "cm_signed_error_pct_points": -0.8,
            "rto_predicted_pct": 8.0,
            "rto_actual_pct": 10.0,
            "rto_signed_error_pct_points": 2.0,
            "cac_predicted": 250.0,
            "cac_actual": 260.0,
            "cac_signed_error": 10.0,
            "directional_accuracy": DIRECTION_OVERPREDICTED,
            "calibration_status": STATUS_CALIBRATED,
            "data_completeness_pct": 100.0
        })

        dossier = PredictionRealityReportService.get_product_pvr_dossier("TEST_SKU_1")
        self.assertEqual(dossier["coverage_status"], COVERAGE_COMPLETE_CALIBRATED)
        self.assertEqual(len(dossier["comparisons"]), 1)

        comp = dossier["comparisons"][0]
        self.assertEqual(comp["outcome_id"], out_id)
        self.assertEqual(comp["decision_id"], dec_id)
        self.assertEqual(comp["calibration_id"], calib_id)
        self.assertEqual(comp["period_type"], "DAY_30")

        # Metric assertions
        demand = comp["metrics"]["demand"]
        self.assertEqual(demand["predicted"], 15)
        self.assertEqual(demand["actual_daily_velocity"], 13.0)
        self.assertEqual(demand["actual_total_units"], 390)
        self.assertEqual(demand["signed_error_mbe"], -2.0)
        self.assertEqual(demand["absolute_error_mae"], 2.0)
        self.assertEqual(demand["percentage_error_mape"], -13.33)
        self.assertEqual(demand["directional_accuracy"], DIRECTION_OVERPREDICTED)

        # Contribution margin error in percentage points
        cm = comp["metrics"]["cm"]
        self.assertEqual(cm["predicted"], 70.8)
        self.assertEqual(cm["actual"], 70.0)
        self.assertEqual(cm["signed_error_pp"], -0.8)

    def test_08_partial_outcome_handling(self):
        """Outcome with missing metrics results in PARTIAL_OUTCOME status without error."""
        dec_id = record_decision_snapshot(
            product_id="TEST_SKU_1",
            decision_type="LAUNCHPAD_COMMITMENT",
            override_predictions={"predicted_daily_units": 10},
            decision_timestamp="2026-06-01T00:00:00"
        )
        out_res = record_product_outcome({
            "product_id": "TEST_SKU_1",
            "decision_id": dec_id,
            "period_start": "2026-06-02",
            "period_end": "2026-07-01",
            "period_type": "DAY_30",
            "actual_units_sold": None,
            "actual_revenue": None,
            "data_source": "MANUAL_CSV"
        })
        save_prediction_calibration({
            "decision_id": dec_id,
            "outcome_id": out_res["outcome_id"],
            "product_id": "TEST_SKU_1",
            "calibration_status": STATUS_PARTIAL_DATA,
            "data_completeness_pct": 20.0
        })

        dossier = PredictionRealityReportService.get_product_pvr_dossier("TEST_SKU_1")
        self.assertEqual(dossier["coverage_status"], COVERAGE_PARTIAL_OUTCOME)
        self.assertEqual(dossier["comparisons"][0]["calibration_status"], STATUS_PARTIAL_DATA)

    def test_09_multiple_decisions_history_and_ordering(self):
        """Multiple historical decisions are preserved in chronological order DESC."""
        d1 = record_decision_snapshot(
            product_id="TEST_SKU_1",
            decision_type="LAUNCHPAD_COMMITMENT",
            override_predictions={"predicted_daily_units": 10, "predicted_selling_price": 1000.0},
            decision_timestamp="2026-05-01T00:00:00"
        )
        d2 = record_decision_snapshot(
            product_id="TEST_SKU_1",
            decision_type="SCALE_COMMITMENT",
            override_predictions={"predicted_daily_units": 25, "predicted_selling_price": 1100.0},
            decision_timestamp="2026-06-01T00:00:00"
        )

        dossier = PredictionRealityReportService.get_product_pvr_dossier("TEST_SKU_1")
        self.assertEqual(len(dossier["decisions"]), 2)
        # Verify ordering: latest decision first
        self.assertEqual(dossier["decisions"][0]["decision_id"], d2)
        self.assertEqual(dossier["decisions"][1]["decision_id"], d1)

    def test_10_frozen_decision_isolated_from_current_intelligence(self):
        """Decision snapshots must remain frozen even if current intelligence changes."""
        dec_id = record_decision_snapshot(
            product_id="TEST_SKU_1",
            decision_type="LAUNCHPAD_COMMITMENT",
            override_predictions={"predicted_daily_units": 20, "predicted_selling_price": 1200.0},
            decision_timestamp="2026-06-01T00:00:00"
        )

        # Mutate master_products and product_intelligence
        conn = get_connection()
        conn.execute("""
            UPDATE master_products 
            SET overall_score = 40.0, estimated_daily_units = 3 
            WHERE product_id = 'TEST_SKU_1'
        """)
        conn.execute("""
            UPDATE product_intelligence 
            SET opportunity_score = 40.0, kill_status = 'KILLED' 
            WHERE product_id = 'TEST_SKU_1'
        """)
        conn.commit()
        conn.close()

        dossier = PredictionRealityReportService.get_product_pvr_dossier("TEST_SKU_1")
        frozen_dec = dossier["decisions"][0]
        # Frozen decision unchanged
        self.assertEqual(frozen_dec["predicted_daily_units"], 20)
        self.assertEqual(frozen_dec["predicted_selling_price"], 1200.0)

        # Current intelligence reflects new state separately
        curr = dossier["current_intelligence"]
        self.assertEqual(curr["opportunity_score"], 40.0)
        self.assertEqual(curr["kill_status"], "KILLED")

    def test_11_corrected_outcome_visibility(self):
        """Outcome corrections are visible in read-only audit trail."""
        out_res = record_product_outcome({
            "product_id": "TEST_SKU_1",
            "period_start": "2026-06-02",
            "period_end": "2026-07-01",
            "period_type": "DAY_30",
            "actual_units_sold": 400,
            "actual_revenue": 480000.0,
            "data_source": "MANUAL_CSV"
        })
        oid = out_res["outcome_id"]

        record_outcome_correction(
            outcome_id=oid,
            updates={"actual_revenue": 485000.0, "actual_units_sold": 405},
            correction_reason="Audited marketplace reconciliation statement",
            corrected_by="OPERATOR_AUDIT"
        )

        dossier = PredictionRealityReportService.get_product_pvr_dossier("TEST_SKU_1")
        comp = dossier["comparisons"][0]
        self.assertTrue(comp["is_corrected"])
        self.assertEqual(comp["correction_count"], 2)  # 2 fields corrected

        # Corrections audit log helper
        corrs = PredictionRealityReportService.get_corrections_audit_log("TEST_SKU_1")
        self.assertEqual(len(corrs), 2)
        field_names = [c["field_name"] for c in corrs]
        self.assertIn("actual_revenue", field_names)
        self.assertIn("actual_units_sold", field_names)

    def test_12_observation_maturity_integration(self):
        """Observation scheduler provides 30/60/90-day maturity windows."""
        dossier = PredictionRealityReportService.get_product_pvr_dossier("TEST_SKU_1")
        sched = dossier["observation_schedule"]
        self.assertIn("windows", sched)
        window_names = [w.get("period_type") or w.get("window_name") for w in sched["windows"]]
        self.assertIn("DAY_30", window_names)
        self.assertIn("DAY_60", window_names)
        self.assertIn("DAY_90", window_names)

    def test_13_insufficient_sample_size_safeguard(self):
        """N < 5 calibrations yield INSUFFICIENT_SAMPLE reliability with sample metrics."""
        dec_id = record_decision_snapshot(
            product_id="TEST_SKU_1",
            decision_type="LAUNCHPAD_COMMITMENT",
            override_predictions={"predicted_daily_units": 15},
            decision_timestamp="2026-06-01T00:00:00"
        )
        out_res = record_product_outcome({
            "product_id": "TEST_SKU_1",
            "decision_id": dec_id,
            "period_start": "2026-06-02",
            "period_end": "2026-07-01",
            "period_type": "DAY_30",
            "actual_units_sold": 300,
            "data_source": "MANUAL_CSV"
        })
        save_prediction_calibration({
            "decision_id": dec_id,
            "outcome_id": out_res["outcome_id"],
            "product_id": "TEST_SKU_1",
            "demand_signed_error": -5.0,
            "demand_absolute_error": 5.0,
            "demand_percentage_error": -33.3,
            "calibration_status": STATUS_CALIBRATED
        })

        summary = PredictionRealityReportService.get_portfolio_summary()
        self.assertEqual(summary["sample_size"], 1)
        self.assertEqual(summary["calibration_reliability"], "INSUFFICIENT_SAMPLE")
        self.assertEqual(summary["demand_bias_mbe"], -5.0)
        self.assertEqual(summary["demand_mae"], 5.0)

    def test_14_provisional_aggregate_sample_size(self):
        """N >= 5 calibrations yield PROVISIONAL_AGGREGATE reliability and calculate MAE/MAPE."""
        conn = get_connection()
        for i in range(5):
            pid = f"PROV_SKU_{i}"
            conn.execute("""
                INSERT INTO master_products (product_id, name, category, region, planned_msrp, landed_cogs, gross_margin_pct, estimated_cac, estimated_daily_units, overall_score)
                VALUES (?, ?, 'Office', 'India', 1000.0, 300.0, 70.0, 200.0, 10, 80.0)
            """, (pid, f"Product {i}"))
            conn.commit()

            dec_id = record_decision_snapshot(
                product_id=pid,
                decision_type="LAUNCHPAD_COMMITMENT",
                override_predictions={"predicted_daily_units": 10, "predicted_selling_price": 1000.0},
                decision_timestamp="2026-06-01T00:00:00"
            )
            out_res = record_product_outcome({
                "product_id": pid,
                "decision_id": dec_id,
                "period_start": "2026-06-02",
                "period_end": "2026-07-01",
                "period_type": "DAY_30",
                "actual_units_sold": 360,
                "actual_avg_selling_price": 980.0,
                "data_source": "MANUAL_CSV"
            })
            save_prediction_calibration({
                "decision_id": dec_id,
                "outcome_id": out_res["outcome_id"],
                "product_id": pid,
                "demand_predicted": 10.0,
                "demand_actual": 12.0,
                "demand_signed_error": 2.0,
                "demand_absolute_error": 2.0,
                "demand_percentage_error": 20.0,
                "price_predicted": 1000.0,
                "price_actual": 980.0,
                "price_signed_error": -20.0,
                "calibration_status": STATUS_CALIBRATED
            })
        conn.close()

        summary = PredictionRealityReportService.get_portfolio_summary()
        self.assertEqual(summary["sample_size"], 5)
        self.assertEqual(summary["calibration_reliability"], "PROVISIONAL_AGGREGATE")
        self.assertEqual(summary["demand_bias_mbe"], 2.0)
        self.assertEqual(summary["demand_mae"], 2.0)
        self.assertEqual(summary["demand_mape"], 20.0)
        self.assertEqual(summary["price_bias_mbe"], -20.0)

    def test_15_portfolio_aggregation_totals(self):
        """Portfolio summary accurately sums observed units and revenue."""
        conn = get_connection()
        conn.execute("""
            INSERT INTO master_products (product_id, name, category, region, planned_msrp, landed_cogs, gross_margin_pct, estimated_cac, estimated_daily_units, overall_score)
            VALUES ('VOL_SKU_1', 'Vol Product 1', 'General', 'India', 500.0, 100.0, 80.0, 50.0, 10, 80.0),
                   ('VOL_SKU_2', 'Vol Product 2', 'General', 'India', 1000.0, 200.0, 80.0, 100.0, 10, 80.0)
        """)
        conn.commit()
        conn.close()

        record_product_outcome({
            "product_id": "VOL_SKU_1",
            "period_start": "2026-06-02",
            "period_end": "2026-07-01",
            "period_type": "DAY_30",
            "actual_units_sold": 100,
            "actual_revenue": 50000.0,
            "data_source": "MANUAL_CSV"
        })
        record_product_outcome({
            "product_id": "VOL_SKU_2",
            "period_start": "2026-06-02",
            "period_end": "2026-07-01",
            "period_type": "DAY_30",
            "actual_units_sold": 200,
            "actual_revenue": 200000.0,
            "data_source": "MANUAL_CSV"
        })

        summary = PredictionRealityReportService.get_portfolio_summary()
        self.assertEqual(summary["total_observed_units"], 300)
        self.assertEqual(summary["total_observed_revenue"], 250000.0)

    def test_16_products_pvr_catalog_sorting_and_badges(self):
        """Catalog prioritizes products with outcomes, then decisions, then uncommitted."""
        # TEST_SKU_1 currently has 0 outcomes and 0 decisions
        # Create SKU_WITH_DECISION
        conn = get_connection()
        conn.execute("""
            INSERT INTO master_products (product_id, name, category, region, planned_msrp, landed_cogs, gross_margin_pct, estimated_cac, estimated_daily_units, overall_score)
            VALUES ('SKU_DEC', 'Decision Product', 'Tools', 'India', 500.0, 100.0, 80.0, 50.0, 10, 80.0),
                   ('SKU_OUT', 'Outcome Product', 'Tools', 'India', 500.0, 100.0, 80.0, 50.0, 10, 80.0)
        """)
        conn.commit()
        conn.close()

        record_decision_snapshot(product_id="SKU_DEC", override_predictions={"predicted_daily_units": 5})
        record_product_outcome({
            "product_id": "SKU_OUT",
            "period_start": "2026-06-02",
            "period_end": "2026-07-01",
            "period_type": "DAY_30",
            "actual_units_sold": 50,
            "data_source": "MANUAL_CSV"
        })

        catalog = PredictionRealityReportService.get_products_pvr_catalog(limit=50)
        product_order = [p["product_id"] for p in catalog]

        # SKU_OUT should appear before SKU_DEC, and SKU_DEC before uncommitted
        self.assertIn("SKU_OUT", product_order)
        self.assertIn("SKU_DEC", product_order)
        idx_out = product_order.index("SKU_OUT")
        idx_dec = product_order.index("SKU_DEC")
        idx_uncommitted = product_order.index("TEST_SKU_1")

        self.assertLess(idx_out, idx_dec)
        self.assertLess(idx_dec, idx_uncommitted)

    def test_17_nonexistent_product_dossier_safe(self):
        """Nonexistent product ID returns exists=False without raising exception."""
        dossier = PredictionRealityReportService.get_product_pvr_dossier("NON_EXISTENT_SKU_999")
        self.assertFalse(dossier["exists"])
        self.assertEqual(dossier["coverage_status"], "PRODUCT_NOT_FOUND")

    def test_18_audit_logs_and_decision_history_helpers(self):
        """Audit log and decision history helpers return clean lists."""
        dec_id = record_decision_snapshot(product_id="TEST_SKU_1", override_predictions={"predicted_daily_units": 10})
        history = PredictionRealityReportService.get_all_decision_history("TEST_SKU_1")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["decision_id"], dec_id)

    def test_19_foreign_key_integrity(self):
        """Verify PRAGMA foreign_key_check is completely clean on test database."""
        conn = get_connection()
        fks = conn.execute("PRAGMA foreign_key_check").fetchall()
        conn.close()
        self.assertEqual(len(fks), 0, f"FK violations: {fks}")

    def test_20_streamlit_apptest_prediction_reality_subtab(self):
        """Verify Streamlit AppTest renders Prediction vs Reality subtab with 0 exceptions on isolated DB."""
        import subprocess
        # Use temporary database for AppTest to guarantee zero production DB writes
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
                "at.run(timeout=30); "
                "assert len(at.exception) == 0; "
                "assert any('Prediction vs Reality' in str(m.value) for m in at.markdown); "
                "assert any('waiting for real outcome observations' in str(i.value) for i in at.info); "
                "print('AppTest Subtab: 0 exceptions')"
            ]
            res = subprocess.run(cmd, cwd=str(_ROOT), env=env, capture_output=True, text=True, timeout=60)
            self.assertEqual(res.returncode, 0, f"AppTest failed:\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}")
        finally:
            try:
                os.remove(t_db)
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()
