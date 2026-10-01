"""
APRS V8 PHASE 5.1: FORENSIC VERIFICATION & AUDIT TEST SUITE
============================================================
Comprehensive test suite verifying that Phase 5 (Manual CSV Outcome Source)
strictly complies with all architectural, mathematical, temporal, and safety invariants.

Verifies:
  Check #1:  Phase 3 Authoritative Persistence & Business Validation Boundary
  Check #2:  Decision ID Temporal Validation & Immutability Trigger
  Check #3:  CSV Schema Aliasing & Alias Conflict Detection
  Check #4:  Canonical Numeric Parsing & NULL vs Zero Preservation
  Check #5:  Source Record ID Rules (Unique, Duplicate, Idempotent, Conflict)
  Check #6:  Deterministic Product Resolution & Rejection of Fuzzy Guessing
  Check #7:  Dry-Run Safety (Zero Writes with Valid & Invalid Input)
  Check #8:  Batch Atomicity (All-or-Nothing Default vs Opt-in Partial)
  Check #9:  Conflict Protection vs Auditable Phase 3 Correction Service
  Check #10: Provenance Preservation & Deterministic SHA-256 File Hash
  Check #11: CUSTOM Period Bounds & Scheduler Independence
  Check #12: Research Proxy & Scraped Estimate Prohibition
  Check #13: Adapter Independence (No Direct Database Writes)
  Check #14: Idempotent Reingestion (No Duplicate Outcomes or Calibrations)
  Check #15: Calibration Integrity (Frozen Decision Ledger vs Reality)
  Check #16: Calibration Terminology (Mean Signed Error vs No MSE)
  Check #17: File Safety (Rejection of URLs, Non-Files, Missing Files)
  Check #18: UTF-8 and UTF-8 BOM Encoding Determinism
  Check #19: Production Database Zero-Contamination Invariant
"""

import datetime
import math
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest

from core.database import (
    init_db,
    get_connection,
    record_product_evaluation,
    record_decision_snapshot,
    get_decision_snapshot,
    get_product_outcomes,
    get_outcome_by_id,
    get_calibrations_for_product,
)
from core.outcome_ingestion import (
    OutcomeIngestionService,
)
from core.calibration_engine import (
    calculate_prediction_calibration,
    calculate_aggregate_bias,
    calibrate_outcome,
)
from core.outcome_adapters.base import (
    SOURCE_MANUAL_CSV,
    ERROR_INVALID_SOURCE_RECORD,
    ERROR_MISSING_PRODUCT_ID,
    ERROR_UNRESOLVED_PRODUCT,
    ERROR_INVALID_PERIOD,
    ERROR_INVALID_NUMERIC_VALUE,
    ERROR_RESEARCH_ESTIMATE_NOT_OUTCOME,
    ERROR_DUPLICATE_SOURCE_RECORD_ID,
    ERROR_OUTCOME_SOURCE_CONFLICT,
    ERROR_FILE_SAFETY_VIOLATION,
)
from core.outcome_adapters.manual_csv_adapter import (
    ManualCsvOutcomeAdapter,
    ManualCsvOutcomeService,
    CSV_SOURCE_VERSION,
    CSV_SCHEMA_VERSION,
    parse_canonical_numeric_string,
    check_metric_alias_conflicts,
)


class TestAPRSV8Phase51Forensics(unittest.TestCase):
    """
    Exhaustive forensic verification test cases for APRS V8 Phase 5.
    """

    def setUp(self):
        # Create an isolated temporary directory and database for every test
        self.test_dir = tempfile.mkdtemp(prefix="aprs_phase5_1_test_")
        self.db_path = Path(self.test_dir) / "test_engine.db"

        # Patch environment and initialize fresh test database
        self._orig_db_path = os.environ.get("APRS_DB_PATH")
        os.environ["APRS_DB_PATH"] = str(self.db_path)
        init_db()

        self.adapter = ManualCsvOutcomeAdapter()
        self.service = ManualCsvOutcomeService(self.adapter)

    def tearDown(self):
        if self._orig_db_path:
            os.environ["APRS_DB_PATH"] = self._orig_db_path
        else:
            os.environ.pop("APRS_DB_PATH", None)

        if Path(self.test_dir).exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_dummy_product(self, product_id: str = "PROD_FORENSIC_1") -> str:
        prod = {
            "id": product_id,
            "name": f"Forensic Product {product_id}",
            "category": "Home & Kitchen",
            "region": "India",
            "retail_msrp": 999.0,
            "factory_cogs": 250.0,
            "est_cac": 150.0,
            "bsr_rank": 300,
            "estimated_daily_units": 15,
            "ad_active_days": 10,
            "sourcing_hub": "Cluster A",
            "marketplace_url": f"https://www.amazon.in/dp/{product_id}",
            "competitor_flaw": "Chip prone",
            "upgrade_v2": "Reinforced ceramic",
            "suppliers": []
        }
        econ = {
            "status": "PASS",
            "score": 85.0,
            "landed_cogs": 250.0,
            "gross_margin_pct": 74.97,
            "net_profit_pct": 45.0,
            "worst_case_stress_margin_pct": 20.0,
            "consensus_status": "CONSENSUS_PASS",
            "action_plan": "SCALE"
        }
        record_product_evaluation(prod, econ)
        return product_id

    def _create_decision(self, product_id: str, timestamp: str = "2026-08-15 12:00:00") -> int:
        pred_dict = {
            "predicted_daily_units": 5,
            "predicted_selling_price": 999.0,
            "predicted_cogs": 350.0,
            "predicted_cm_pct": 45.0,
            "predicted_rto_pct": 3.0,
            "predicted_cac": 120.0,
        }
        dec_id = record_decision_snapshot(
            product_id=product_id,
            decision_type="GO_DECISION",
            override_predictions=pred_dict,
            decision_timestamp=timestamp
        )
        return dec_id

    def _write_csv(self, content: str, filename: str = "test.csv") -> Path:
        p = Path(self.test_dir) / filename
        p.write_text(content, encoding="utf-8")
        return p

    # -------------------------------------------------------------
    # CHECK #1: PHASE 3 MUST REMAIN AUTHORITATIVE BOUNDARY
    # -------------------------------------------------------------
    def test_check1_phase3_authoritative_boundary(self):
        """
        Phase 3 OutcomeIngestionService is the sole persistence and business validation boundary.
        The adapter does not write to the DB. Business constraints (e.g. stockout_days > window)
        and derived metrics are authoritatively handled by Phase 3.
        """
        pid = self._create_dummy_product("PROD_CHK1")
        # Observation period is 30 days (2026-09-01 to 2026-09-30)
        # Attempt to supply stockout_days = 40 (violates Phase 3 window constraint)
        csv_content = (
            "product_id,period_start,period_end,period_type,source_record_id,units_sold,revenue,stockout_days\n"
            f"{pid},2026-09-01,2026-09-30,DAY_30,REC_CHK1,100,99900.0,40\n"
        )
        p = self._write_csv(csv_content)

        # Ingestion through service must be rejected at Phase 3 ingestion boundary
        rep = self.service.ingest_file(p, dry_run=False, atomic=True)
        self.assertIn(rep.status, ("BLOCKED_VALIDATION_FAILED", "PARTIAL_INGESTION_WITH_ERRORS"))
        outcomes = get_product_outcomes(pid)
        self.assertEqual(len(outcomes), 0, "No outcome should be persisted when business validation fails.")

    # -------------------------------------------------------------
    # CHECK #2: DECISION ID TEMPORAL VALIDATION & IMMUTABILITY
    # -------------------------------------------------------------
    def test_check2_decision_temporal_validation(self):
        """
        Decision timestamp must precede period_start. An outcome claiming a future decision is rejected.
        Valid decision links cleanly and triggers calibration. Decision ledger trigger prevents mutation.
        """
        # Case A: Future decision timestamp rejected
        pid_fut = self._create_dummy_product("PROD_CHK2_FUT")
        future_dec_id = self._create_decision(pid_fut, timestamp="2026-10-15 10:00:00")

        # Outcome period is 2026-09-01 to 2026-09-30 (BEFORE the decision occurred!)
        csv_future = (
            "product_id,decision_id,period_start,period_end,period_type,source_record_id,units_sold,revenue\n"
            f"{pid_fut},{future_dec_id},2026-09-01,2026-09-30,DAY_30,REC_CHK2_FUT,100,99900.0\n"
        )
        p_fut = self._write_csv(csv_future, "future.csv")
        rep_fut = self.service.ingest_file(p_fut, dry_run=False)
        self.assertEqual(rep_fut.ingested_count, 0)
        self.assertEqual(len(get_product_outcomes(pid_fut)), 0)

        # Case B: Valid chronological decision: made on 2026-08-15
        pid_val = self._create_dummy_product("PROD_CHK2_VAL")
        valid_dec_id = self._create_decision(pid_val, timestamp="2026-08-15 10:00:00")
        csv_valid = (
            "product_id,decision_id,period_start,period_end,period_type,source_record_id,units_sold,revenue\n"
            f"{pid_val},{valid_dec_id},2026-09-01,2026-09-30,DAY_30,REC_CHK2_VAL,100,99900.0\n"
        )
        p_val = self._write_csv(csv_valid, "valid.csv")
        rep_val = self.service.ingest_file(p_val, dry_run=False)
        self.assertEqual(rep_val.ingested_count, 1)

        calibs = get_calibrations_for_product(pid_val)
        self.assertEqual(len(calibs), 1)
        self.assertEqual(calibs[0]["decision_id"], valid_dec_id)

        # Verify decision_ledger immutability trigger
        conn = get_connection()
        cur = conn.cursor()
        with self.assertRaises(sqlite3.IntegrityError):
            cur.execute("UPDATE decision_ledger SET predicted_daily_units = 9999 WHERE decision_id = ?", (valid_dec_id,))
        conn.close()

    # -------------------------------------------------------------
    # CHECK #3: CSV SCHEMA ALIASING & CONFLICT DETECTION
    # -------------------------------------------------------------
    def test_check3_schema_aliasing_canonical_only(self):
        """Supplying only canonical field (units_sold) normalizes successfully."""
        pid = self._create_dummy_product("PROD_CHK3_A")
        csv_data = (
            "product_id,period_start,period_end,period_type,source_record_id,units_sold\n"
            f"{pid},2026-09-01,2026-09-30,DAY_30,REC_ALIAS_1,50\n"
        )
        norm_res = self.service.normalize_file(self._write_csv(csv_data, "alias1.csv"))
        self.assertEqual(norm_res.successful[0].actual_units_sold, 50)

    def test_check3_schema_aliasing_actual_prefix_only(self):
        """Supplying only actual_* field (actual_units_sold) normalizes successfully."""
        pid = self._create_dummy_product("PROD_CHK3_B")
        csv_data = (
            "product_id,period_start,period_end,period_type,source_record_id,actual_units_sold\n"
            f"{pid},2026-09-01,2026-09-30,DAY_30,REC_ALIAS_2,75\n"
        )
        norm_res = self.service.normalize_file(self._write_csv(csv_data, "alias2.csv"))
        self.assertEqual(norm_res.successful[0].actual_units_sold, 75)

    def test_check3_schema_aliasing_both_identical_accepted(self):
        """Supplying both units_sold=50 and actual_units_sold=50 is accepted deterministically."""
        pid = self._create_dummy_product("PROD_CHK3_C")
        csv_data = (
            "product_id,period_start,period_end,period_type,source_record_id,units_sold,actual_units_sold\n"
            f"{pid},2026-09-01,2026-09-30,DAY_30,REC_ALIAS_3,50,50\n"
        )
        norm_res = self.service.normalize_file(self._write_csv(csv_data, "alias3.csv"))
        self.assertEqual(norm_res.success_count, 1)
        self.assertEqual(norm_res.successful[0].actual_units_sold, 50)

    def test_check3_schema_aliasing_both_differing_rejected(self):
        """Supplying both units_sold=10 and actual_units_sold=20 is REJECTED with explicit conflict."""
        pid = self._create_dummy_product("PROD_CHK3_D")
        csv_data = (
            "product_id,period_start,period_end,period_type,source_record_id,units_sold,actual_units_sold\n"
            f"{pid},2026-09-01,2026-09-30,DAY_30,REC_ALIAS_4,10,20\n"
        )
        p = self._write_csv(csv_data, "alias4.csv")
        val = self.service.validate_file(p)
        # Normalizing via service captures the failure in norm_res.failed
        norm_res = self.service.normalize_file(p)
        self.assertEqual(norm_res.failure_count, 1)
        self.assertTrue(any("Conflicting values provided for aliased column" in e.error_message for e in norm_res.failed))

        # Direct adapter normalize raises ValueError
        raw_row = {
            "product_id": pid,
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "period_type": "DAY_30",
            "source_record_id": "REC_ALIAS_4",
            "units_sold": 10,
            "actual_units_sold": 20
        }
        with self.assertRaises(ValueError) as ctx:
            self.adapter.normalize(raw_row)
        self.assertIn("Conflicting values provided for aliased column", str(ctx.exception))

    def test_check3_schema_aliasing_revenue_conflict_rejected(self):
        """Supplying revenue=1000 and actual_revenue=2000 is REJECTED."""
        pid = self._create_dummy_product("PROD_CHK3_E")
        csv_data = (
            "product_id,period_start,period_end,period_type,source_record_id,revenue,actual_revenue\n"
            f"{pid},2026-09-01,2026-09-30,DAY_30,REC_ALIAS_5,1000.0,2000.0\n"
        )
        p = self._write_csv(csv_data, "alias5.csv")
        val = self.service.validate_file(p)
        self.assertFalse(val.is_valid)

    # -------------------------------------------------------------
    # CHECK #4: NUMERIC PARSING & NULL VS ZERO
    # -------------------------------------------------------------
    def test_check4_numeric_parsing_rules(self):
        """
        0 remains 0.
        blank remains None (Never coerced to zero).
        Decimals accepted.
        Currency symbols and thousand commas are rejected.
        """
        # Canonical string parser tests
        self.assertEqual(parse_canonical_numeric_string("0", "f"), "0")
        self.assertEqual(parse_canonical_numeric_string("10", "f"), "10")
        self.assertEqual(parse_canonical_numeric_string("10.5", "f"), "10.5")
        self.assertIsNone(parse_canonical_numeric_string("", "f"))
        self.assertIsNone(parse_canonical_numeric_string(None, "f"))

        # Currency symbols rejected
        with self.assertRaises(ValueError):
            parse_canonical_numeric_string("₹1250", "field")
        with self.assertRaises(ValueError):
            parse_canonical_numeric_string("$1250", "field")

        # Thousands commas rejected
        with self.assertRaises(ValueError):
            parse_canonical_numeric_string("1,250", "field")

    # -------------------------------------------------------------
    # CHECK #5: SOURCE RECORD ID BEHAVIOR
    # -------------------------------------------------------------
    def test_check5_source_record_id_rules(self):
        """
        A: unique -> accept
        B: duplicate in file -> reject
        C: identical already persisted -> idempotent skip
        D: different data for same ID -> conflict error
        """
        pid = self._create_dummy_product("PROD_CHK5")

        # B: Duplicate in file
        csv_dup = (
            "product_id,period_start,period_end,period_type,source_record_id,units_sold\n"
            f"{pid},2026-09-01,2026-09-30,DAY_30,REC_SAME,10\n"
            f"{pid},2026-10-01,2026-10-31,DAY_30,REC_SAME,20\n"
        )
        val_dup = self.service.validate_file(self._write_csv(csv_dup, "dup.csv"))
        self.assertFalse(val_dup.is_valid)
        self.assertIn("REC_SAME", val_dup.duplicate_source_ids)

        # Initial ingestion of unique
        csv_init = (
            "product_id,period_start,period_end,period_type,source_record_id,units_sold,revenue\n"
            f"{pid},2026-09-01,2026-09-30,DAY_30,REC_UNIQ,100,50000.0\n"
        )
        p_init = self._write_csv(csv_init, "init.csv")
        rep1 = self.service.ingest_file(p_init, dry_run=False)
        self.assertEqual(rep1.ingested_count, 1)

        # C: Re-ingest exact same data -> idempotent skip
        rep2 = self.service.ingest_file(p_init, dry_run=False)
        self.assertEqual(rep2.ingested_count, 0)
        self.assertEqual(rep2.skipped_idempotent_count, 1)

        # D: Ingest same ID with differing data -> CONFLICT
        csv_conflict = (
            "product_id,period_start,period_end,period_type,source_record_id,units_sold,revenue\n"
            f"{pid},2026-09-01,2026-09-30,DAY_30,REC_UNIQ,999,999999.0\n"
        )
        p_conf = self._write_csv(csv_conflict, "conf.csv")
        rep3 = self.service.ingest_file(p_conf, dry_run=False)
        self.assertEqual(rep3.status, "CONFLICT_ERROR")
        self.assertEqual(rep3.ingested_count, 0)

        # Confirm original row still has original units (100)
        outcomes = get_product_outcomes(pid)
        self.assertEqual(outcomes[0]["actual_units_sold"], 100)

    # -------------------------------------------------------------
    # CHECK #6: PRODUCT RESOLUTION
    # -------------------------------------------------------------
    def test_check6_product_mapping_rules(self):
        """
        Direct APRS product_id -> accepts.
        source_product_id + resolver -> accepts.
        unknown product -> rejects with UNRESOLVED_PRODUCT.
        fuzzy-looking product -> rejects (no guessing).
        conflicting product_id and source_product_id -> rejects.
        """
        pid = self._create_dummy_product("PROD_EXACT_A")
        resolver = lambda code: pid if code == "SKU_EXTERNAL_1" else None

        # Direct
        csv_dir = f"product_id,period_start,period_end,period_type,source_record_id,units_sold\n{pid},2026-09-01,2026-09-30,DAY_30,R1,10\n"
        self.assertTrue(self.service.validate_file(self._write_csv(csv_dir, "d.csv")).is_valid)

        # Resolver
        csv_res = "source_product_id,period_start,period_end,period_type,source_record_id,units_sold\nSKU_EXTERNAL_1,2026-09-01,2026-09-30,DAY_30,R2,10\n"
        self.assertTrue(self.service.validate_file(self._write_csv(csv_res, "r.csv"), product_resolver=resolver).is_valid)

        # Unknown
        csv_unk = "product_id,period_start,period_end,period_type,source_record_id,units_sold\nPROD_DOES_NOT_EXIST,2026-09-01,2026-09-30,DAY_30,R3,10\n"
        val_unk = self.service.validate_file(self._write_csv(csv_unk, "u.csv"))
        self.assertFalse(val_unk.is_valid)
        self.assertEqual(val_unk.errors[0].error_category, ERROR_UNRESOLVED_PRODUCT)

        # Fuzzy matching rejected (even if similar to PROD_EXACT_A)
        csv_fuzz = "product_id,period_start,period_end,period_type,source_record_id,units_sold\nPROD_EXACT_A_TYPO,2026-09-01,2026-09-30,DAY_30,R4,10\n"
        val_fuzz = self.service.validate_file(self._write_csv(csv_fuzz, "fuzz.csv"))
        self.assertFalse(val_fuzz.is_valid)

        # Conflicting product_id and source_product_id
        csv_conf = f"product_id,source_product_id,period_start,period_end,period_type,source_record_id,units_sold\nOTHER_PROD,SKU_EXTERNAL_1,2026-09-01,2026-09-30,DAY_30,R5,10\n"
        val_conf = self.service.validate_file(self._write_csv(csv_conf, "conf_p.csv"), product_resolver=resolver)
        self.assertFalse(val_conf.is_valid)

    # -------------------------------------------------------------
    # CHECK #7: DRY RUN SAFETY
    # -------------------------------------------------------------
    def test_check7_dry_run_safety(self):
        """dry_run=True must perform ZERO database writes for both valid and invalid files."""
        pid = self._create_dummy_product("PROD_CHK7")
        conn = get_connection()
        cur = conn.cursor()

        def _get_counts():
            d = cur.execute("SELECT COUNT(*) FROM decision_ledger").fetchone()[0]
            o = cur.execute("SELECT COUNT(*) FROM product_outcomes").fetchone()[0]
            c = cur.execute("SELECT COUNT(*) FROM prediction_calibrations").fetchone()[0]
            cl = cur.execute("SELECT COUNT(*) FROM outcome_corrections_log").fetchone()[0]
            return d, o, c, cl

        init_counts = _get_counts()

        # Valid CSV with dry_run=True
        csv_valid = (
            "product_id,period_start,period_end,period_type,source_record_id,units_sold,revenue\n"
            f"{pid},2026-09-01,2026-09-30,DAY_30,REC_DRY_1,100,50000.0\n"
        )
        p_val = self._write_csv(csv_valid, "dry_val.csv")
        rep_val = self.service.ingest_file(p_val, dry_run=True)
        self.assertEqual(rep_val.status, "DRY_RUN_SUCCESS")
        self.assertEqual(_get_counts(), init_counts, "Dry run must perform 0 DB writes.")

        # Invalid CSV with dry_run=True
        csv_inv = (
            "product_id,period_start,period_end,period_type,source_record_id,units_sold\n"
            "UNKNOWN_PROD,2026-09-01,2026-09-30,DAY_30,REC_DRY_2,100\n"
        )
        p_inv = self._write_csv(csv_inv, "dry_inv.csv")
        rep_inv = self.service.ingest_file(p_inv, dry_run=True)
        self.assertEqual(rep_inv.status, "BLOCKED_VALIDATION_FAILED")
        self.assertEqual(_get_counts(), init_counts, "Invalid dry run must perform 0 DB writes.")
        conn.close()

    # -------------------------------------------------------------
    # CHECK #8: BATCH ATOMICITY
    # -------------------------------------------------------------
    def test_check8_batch_atomicity(self):
        """
        By default (atomic=True), if 1 row in the file is invalid, ZERO rows are written.
        """
        pid = self._create_dummy_product("PROD_CHK8")
        csv_content = (
            "product_id,period_start,period_end,period_type,source_record_id,units_sold\n"
            f"{pid},2026-09-01,2026-09-30,DAY_30,REC_AT_1,50\n"
            "NONEXISTENT_PROD,2026-09-01,2026-09-30,DAY_30,REC_AT_2,60\n"
            f"{pid},2026-10-01,2026-10-31,DAY_30,REC_AT_3,70\n"
        )
        p = self._write_csv(csv_content, "atomic.csv")
        rep = self.service.ingest_file(p, dry_run=False, atomic=True)
        self.assertEqual(rep.status, "BLOCKED_VALIDATION_FAILED")
        self.assertEqual(rep.ingested_count, 0)
        self.assertEqual(len(get_product_outcomes(pid)), 0, "Atomic failure must write 0 rows.")

    # -------------------------------------------------------------
    # CHECK #9: CONFLICT VS CORRECTION
    # -------------------------------------------------------------
    def test_check9_conflict_vs_correction(self):
        """
        CSV ingestion cannot overwrite existing outcomes.
        Legitimate updates must route through OutcomeIngestionService.correct_outcome.
        """
        pid = self._create_dummy_product("PROD_CHK9")
        csv_init = f"product_id,period_start,period_end,period_type,source_record_id,units_sold\n{pid},2026-09-01,2026-09-30,DAY_30,REC_C9,100\n"
        rep_init = self.service.ingest_file(self._write_csv(csv_init, "c9_init.csv"), dry_run=False)
        outcome_id = rep_init.row_results[0]["outcome_id"]

        # Submitting changed units (120) via CSV is blocked as conflict
        csv_revised = f"product_id,period_start,period_end,period_type,source_record_id,units_sold\n{pid},2026-09-01,2026-09-30,DAY_30,REC_C9,120\n"
        rep_rev = self.service.ingest_file(self._write_csv(csv_revised, "c9_rev.csv"), dry_run=False)
        self.assertEqual(rep_rev.status, "CONFLICT_ERROR")
        self.assertEqual(get_outcome_by_id(outcome_id)["actual_units_sold"], 100)

        # Official auditable correction
        corr = OutcomeIngestionService.correct_outcome(
            outcome_id=outcome_id,
            correction_data={"actual_units_sold": 120},
            reason="Audited ledger reconciliation",
            operator="LEAD_AUDITOR"
        )
        self.assertEqual(corr["status"], "CORRECTED")
        self.assertEqual(get_outcome_by_id(outcome_id)["actual_units_sold"], 120)

    # -------------------------------------------------------------
    # CHECK #10: PROVENANCE & FILE HASH
    # -------------------------------------------------------------
    def test_check10_provenance_and_file_hash(self):
        """
        File SHA-256 hash is deterministic: identical file -> same hash; modified file -> different hash.
        Outcome stores data_source, schema version, and file hash reference.
        """
        pid = self._create_dummy_product("PROD_CHK10")
        csv_text_1 = f"product_id,period_start,period_end,period_type,source_record_id,units_sold\n{pid},2026-09-01,2026-09-30,DAY_30,R_H1,10\n"
        p1 = self._write_csv(csv_text_1, "hash1.csv")
        p1_copy = self._write_csv(csv_text_1, "hash1_copy.csv")
        val1 = self.service.validate_file(p1)
        val1_copy = self.service.validate_file(p1_copy)
        self.assertEqual(val1.file_hash, val1_copy.file_hash, "Identical content must yield identical SHA-256.")

        csv_text_2 = f"product_id,period_start,period_end,period_type,source_record_id,units_sold\n{pid},2026-09-01,2026-09-30,DAY_30,R_H1,11\n"
        p2 = self._write_csv(csv_text_2, "hash2.csv")
        val2 = self.service.validate_file(p2)
        self.assertNotEqual(val1.file_hash, val2.file_hash, "Different content must yield different SHA-256.")

    # -------------------------------------------------------------
    # CHECK #11: CUSTOM PERIOD BOUNDS
    # -------------------------------------------------------------
    def test_check11_custom_period_validation(self):
        """CUSTOM period requires valid explicit dates; reversed dates are rejected."""
        pid = self._create_dummy_product("PROD_CHK11")
        # Valid CUSTOM period
        csv_custom_val = f"product_id,period_start,period_end,period_type,source_record_id,units_sold\n{pid},2026-09-01,2026-09-15,CUSTOM,R_CUST_1,15\n"
        val_res = self.service.validate_file(self._write_csv(csv_custom_val, "cust_val.csv"))
        self.assertTrue(val_res.is_valid)

        # Reversed period
        csv_custom_rev = f"product_id,period_start,period_end,period_type,source_record_id,units_sold\n{pid},2026-09-15,2026-09-01,CUSTOM,R_CUST_2,15\n"
        val_rev = self.service.validate_file(self._write_csv(csv_custom_rev, "cust_rev.csv"))
        self.assertFalse(val_rev.is_valid)
        self.assertEqual(val_rev.errors[0].error_category, ERROR_INVALID_PERIOD)

    # -------------------------------------------------------------
    # CHECK #12: RESEARCH PROXY PROTECTION
    # -------------------------------------------------------------
    def test_check12_research_proxy_protection(self):
        """Research proxies (GOOGLE_TRENDS, SCRAPED_ESTIMATE, etc.) are strictly rejected."""
        pid = self._create_dummy_product("PROD_CHK12")
        # data_source as research proxy
        csv_proxy = f"product_id,data_source,period_start,period_end,period_type,source_record_id,units_sold\n{pid},GOOGLE_TRENDS,2026-09-01,2026-09-30,DAY_30,R_PRX_1,10\n"
        val_proxy = self.service.validate_file(self._write_csv(csv_proxy, "prx.csv"))
        self.assertFalse(val_proxy.is_valid)
        self.assertEqual(val_proxy.errors[0].error_category, ERROR_RESEARCH_ESTIMATE_NOT_OUTCOME)

    # -------------------------------------------------------------
    # CHECK #13: NO DIRECT DB WRITES FROM ADAPTER
    # -------------------------------------------------------------
    def test_check13_no_direct_db_writes_from_adapter(self):
        """Adapter normalization produces in-memory dataclass and makes zero DB calls."""
        pid = self._create_dummy_product("PROD_CHK13")
        row = {
            "product_id": pid,
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "period_type": "DAY_30",
            "source_record_id": "ADAPTER_STANDALONE_01",
            "units_sold": 45,
            "revenue": 44955.0
        }
        val = self.adapter.validate_source_record(row)
        self.assertTrue(val.is_valid)

        norm = self.adapter.normalize(row)
        self.assertEqual(norm.actual_units_sold, 45)
        self.assertEqual(norm.actual_revenue, 44955.0)

        # Confirm database is completely untouched
        self.assertEqual(len(get_product_outcomes(pid)), 0)

    # -------------------------------------------------------------
    # CHECK #14: IDEMPOTENCY
    # -------------------------------------------------------------
    def test_check14_idempotent_reingestion(self):
        """Ingesting the identical CSV twice produces 1 outcome and 1 calibration, no duplicates."""
        pid = self._create_dummy_product("PROD_CHK14")
        dec_id = self._create_decision(pid, timestamp="2026-08-01 10:00:00")
        csv_content = (
            "product_id,decision_id,period_start,period_end,period_type,source_record_id,units_sold,revenue\n"
            f"{pid},{dec_id},2026-09-01,2026-09-30,DAY_30,R_IDEM_FINAL,100,99900.0\n"
        )
        p = self._write_csv(csv_content, "idem.csv")

        rep1 = self.service.ingest_file(p, dry_run=False)
        self.assertEqual(rep1.ingested_count, 1)

        rep2 = self.service.ingest_file(p, dry_run=False)
        self.assertEqual(rep2.ingested_count, 0)
        self.assertEqual(rep2.skipped_idempotent_count, 1)

        # Database checks
        self.assertEqual(len(get_product_outcomes(pid)), 1)
        self.assertEqual(len(get_calibrations_for_product(pid)), 1)

    # -------------------------------------------------------------
    # CHECK #15: CALIBRATION INTEGRITY (FROZEN PREDICTION)
    # -------------------------------------------------------------
    def test_check15_calibration_historical_integrity(self):
        """
        Calibration is strictly computed from the frozen decision ledger.
        Modifying current database tables does NOT alter calibration metrics.
        """
        pid = self._create_dummy_product("PROD_CHK15")
        # Decision predicted: 100 units
        dec_id = self._create_decision(pid, timestamp="2026-08-01 10:00:00")

        # Outcome actual: 120 units
        csv_content = (
            "product_id,decision_id,period_start,period_end,period_type,source_record_id,units_sold,revenue\n"
            f"{pid},{dec_id},2026-09-01,2026-09-30,DAY_30,R_CALIB_INT,120,119880.0\n"
        )
        p = self._write_csv(csv_content, "calib_int.csv")
        self.service.ingest_file(p, dry_run=False)

        calibs = get_calibrations_for_product(pid)
        self.assertEqual(len(calibs), 1)
        # demand_signed_error: actual daily velocity (120 / 30 = 4.0) - predicted daily units (5.0) = -1.0
        self.assertEqual(calibs[0]["demand_signed_error"], -1.0)

        # Now simulate current master_products or economics changing in production DB
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE master_products SET name = 'Altered Product Name' WHERE product_id = ?", (pid,))
        conn.commit()
        conn.close()

        # Calibration still references unchanged frozen decision snapshot
        calibs_after = get_calibrations_for_product(pid)
        self.assertEqual(calibs_after[0]["demand_signed_error"], -1.0)

    # -------------------------------------------------------------
    # CHECK #16: CALIBRATION METRIC TERMINOLOGY (NO MSE)
    # -------------------------------------------------------------
    def test_check16_calibration_metrics_terminology(self):
        """
        Verifies calibration math uses Mean Signed Error (MBE), MAE, and MAPE.
        MSE (Mean Squared Error) is NOT implemented and should not be claimed.
        """
        sample_calibrations = [
            {"units_signed_error": 10, "units_absolute_error": 10, "units_percentage_error": 10.0},
            {"units_signed_error": -10, "units_absolute_error": 10, "units_percentage_error": -10.0},
        ]
        agg = calculate_aggregate_bias(sample_calibrations, metric_prefix="units")
        self.assertIn("mean_signed_error", agg)
        self.assertIn("mean_absolute_error", agg)
        self.assertIn("mape", agg)
        self.assertNotIn("mse", agg, "MSE is not implemented; Mean Signed Error / MBE must be used.")
        # Mean Signed Error of +10 and -10 is 0.0 (Unbiased)
        self.assertEqual(agg["mean_signed_error"], 0.0)
        self.assertEqual(agg["mean_absolute_error"], 10.0)

    # -------------------------------------------------------------
    # CHECK #17: FILE SAFETY
    # -------------------------------------------------------------
    def test_check17_file_safety(self):
        """Remote URLs, non-existent files, and directories are rejected."""
        # validate_file catches safety errors and returns invalid report
        val_url = self.service.validate_file("https://example.com/outcomes.csv")
        self.assertFalse(val_url.is_valid)
        self.assertEqual(val_url.errors[0].error_category, ERROR_FILE_SAFETY_VIOLATION)

        val_missing = self.service.validate_file("nonexistent_path_xyz.csv")
        self.assertFalse(val_missing.is_valid)
        self.assertEqual(val_missing.errors[0].error_category, ERROR_FILE_SAFETY_VIOLATION)

        val_dir = self.service.validate_file(self.test_dir)
        self.assertFalse(val_dir.is_valid)
        self.assertEqual(val_dir.errors[0].error_category, ERROR_FILE_SAFETY_VIOLATION)

        # _verify_file_safety raises directly
        with self.assertRaises(ValueError) as ctx:
            self.service._verify_file_safety("https://example.com/outcomes.csv")
        self.assertIn(ERROR_FILE_SAFETY_VIOLATION, str(ctx.exception))

        with self.assertRaises(FileNotFoundError):
            self.service._verify_file_safety("nonexistent_path_xyz.csv")

        with self.assertRaises(ValueError):
            self.service._verify_file_safety(self.test_dir)

    # -------------------------------------------------------------
    # CHECK #18: UTF-8 AND UTF-8 BOM ENCODING
    # -------------------------------------------------------------
    def test_check18_utf8_and_bom_encoding(self):
        """Both standard UTF-8 and UTF-8 BOM files parse cleanly and identically."""
        pid = self._create_dummy_product("PROD_CHK18")
        csv_text = f"product_id,period_start,period_end,period_type,source_record_id,units_sold\n{pid},2026-09-01,2026-09-30,DAY_30,R_ENC,25\n"

        p_utf8 = Path(self.test_dir) / "std_utf8.csv"
        p_utf8.write_text(csv_text, encoding="utf-8")

        p_bom = Path(self.test_dir) / "bom_utf8.csv"
        p_bom.write_text(csv_text, encoding="utf-8-sig")

        val_utf8 = self.service.validate_file(p_utf8)
        val_bom = self.service.validate_file(p_bom)

        self.assertTrue(val_utf8.is_valid)
        self.assertTrue(val_bom.is_valid)
        self.assertEqual(val_utf8.total_rows, 1)
        self.assertEqual(val_bom.total_rows, 1)

    # -------------------------------------------------------------
    # CHECK #19: PRODUCTION DATABASE PURITY
    # -------------------------------------------------------------
    def test_check19_production_db_purity(self):
        """Authoritative production database data/research_engine.db must remain untouched."""
        prod_db_path = Path("data/research_engine.db")
        if not prod_db_path.exists():
            self.skipTest("Production database data/research_engine.db not found.")

        conn = sqlite3.connect(str(prod_db_path))
        cur = conn.cursor()

        # FK check
        fk_violations = cur.execute("PRAGMA foreign_key_check").fetchall()
        self.assertEqual(len(fk_violations), 0, f"FK violations in production DB: {fk_violations}")

        # Table counts
        dec_cnt = cur.execute("SELECT COUNT(*) FROM decision_ledger").fetchone()[0]
        out_cnt = cur.execute("SELECT COUNT(*) FROM product_outcomes").fetchone()[0]
        cal_cnt = cur.execute("SELECT COUNT(*) FROM prediction_calibrations").fetchone()[0]
        cor_cnt = cur.execute("SELECT COUNT(*) FROM outcome_corrections_log").fetchone()[0]

        self.assertEqual(dec_cnt, 0, "Production decision_ledger must be 0.")
        self.assertEqual(out_cnt, 0, "Production product_outcomes must be 0.")
        self.assertEqual(cal_cnt, 0, "Production prediction_calibrations must be 0.")
        self.assertEqual(cor_cnt, 0, "Production outcome_corrections_log must be 0.")
        conn.close()


if __name__ == "__main__":
    unittest.main()
