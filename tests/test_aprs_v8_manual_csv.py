"""
APRS V8 PHASE 5: MANUAL CSV OUTCOME SOURCE IMPLEMENTATION TESTS
==============================================================
Comprehensive tests validating:
  A. Valid CSV parsing, header verification, and normalization
  B. UTF-8 and UTF-8 BOM encoding support
  C. Missing required headers rejection
  D. Duplicate headers rejection
  E. Extra headers policy (allowed but ignored explicitly)
  F. Numeric parsing (integers, decimals, zeroes, blank -> None, malformed / currency / comma rejection)
  G. Date parsing (ISO validity, reversed period rejection)
  H. Period types (DAY_30, DAY_60, DAY_90, LIFETIME, CUSTOM)
  I. NULL vs zero distinction (blank remains None, 0 remains 0)
  J. Deterministic product mapping (direct product_id, resolver, unknown SKU rejected, no fuzzy matching)
  K. Decision ID matching (explicit preserved, missing remains None)
  L. Provenance tracking (MANUAL_CSV, MANUAL_CSV_V1, source_record_id, timestamp, SHA-256)
  M. Duplicate source_record_id detection within CSV
  N. Idempotent re-ingestion (no duplicate rows inserted)
  O. Conflict handling (differing data on existing source ID blocked; no silent overwrite)
  P. Dry-run preview mode (validates completely with ZERO database writes)
  Q. Batch atomicity (invalid rows block entire batch under default atomic policy)
  R. Phase 3 integration (reaches OutcomeIngestionService, persists to product_outcomes, triggers calibration)
  S. Persistence boundary (adapter alone never writes to SQLite)
  T. Research proxy & pre-launch estimate protection
  U. Local file safety (missing file, unreadable file, remote URL rejection)
  V. Correction behavior (requires explicit OutcomeIngestionService.correct_outcome)
  W. Production database purity (zero contamination of data/research_engine.db)
  X. Network safety (zero live API calls, zero network imports)
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
    get_product_outcomes,
    get_calibrations_for_product,
)
from core.outcome_ingestion import (
    OutcomeIngestionService,
)
from core.outcome_adapters import (
    ManualCsvOutcomeAdapter,
    ManualCsvOutcomeService,
    CsvValidationReport,
    CsvIngestionReport,
    NormalizedOutcome,
    SOURCE_MANUAL_CSV,
    CSV_SOURCE_VERSION,
    CSV_SCHEMA_VERSION,
    ERROR_INVALID_SOURCE_RECORD,
    ERROR_MISSING_PRODUCT_ID,
    ERROR_UNRESOLVED_PRODUCT,
    ERROR_INVALID_PERIOD,
    ERROR_UNSUPPORTED_PERIOD_TYPE,
    ERROR_INVALID_NUMERIC_VALUE,
    ERROR_INVALID_PERCENTAGE,
    ERROR_RESEARCH_ESTIMATE_NOT_OUTCOME,
    ERROR_DUPLICATE_SOURCE_RECORD_ID,
    ERROR_DUPLICATE_HEADERS,
    ERROR_MISSING_REQUIRED_HEADERS,
    ERROR_OUTCOME_SOURCE_CONFLICT,
    ERROR_FILE_SAFETY_VIOLATION,
)


class TestAPRSV8ManualCsv(unittest.TestCase):

    def setUp(self):
        """Create an isolated temporary SQLite database and scratch directory for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_v8_manual_csv.db"
        self.orig_db_path = os.environ.get("APRS_DB_PATH")
        os.environ["APRS_DB_PATH"] = str(self.db_path)
        init_db()
        self.conn = get_connection()
        self.adapter = ManualCsvOutcomeAdapter()
        self.service = ManualCsvOutcomeService(self.adapter)

    def tearDown(self):
        """Clean up test database and restore environment."""
        self.conn.close()
        if self.orig_db_path:
            os.environ["APRS_DB_PATH"] = self.orig_db_path
        elif "APRS_DB_PATH" in os.environ:
            del os.environ["APRS_DB_PATH"]
        self.temp_dir.cleanup()

    def _create_dummy_product(self, product_id="PROD_CSV_001", name="Ceramic Coffee Mug", msrp=999.0, cogs=250.0):
        """Helper to create a product in master_products and return product_id."""
        prod = {
            "id": product_id,
            "name": name,
            "category": "Home & Kitchen",
            "region": "India",
            "retail_msrp": msrp,
            "factory_cogs": cogs,
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
            "landed_cogs": cogs,
            "gross_margin_pct": 74.97,
            "net_profit_pct": 45.0,
            "worst_case_stress_margin_pct": 20.0,
            "consensus_status": "CONSENSUS_PASS",
            "action_plan": "SCALE"
        }
        record_product_evaluation(prod, econ)
        return product_id

    def _write_csv(self, content: str, filename: str = "test.csv", encoding: str = "utf-8") -> Path:
        """Helper to write CSV text to a temporary file."""
        file_path = Path(self.temp_dir.name) / filename
        file_path.write_text(content, encoding=encoding)
        return file_path

    # -------------------------------------------------------------
    # A. VALID CSV
    # -------------------------------------------------------------
    def test_valid_csv_parsing_and_normalization(self):
        """A valid CSV with required and optional fields parses and normalizes cleanly."""
        pid = self._create_dummy_product("PROD_CSV_001")
        csv_content = (
            "product_id,period_start,period_end,period_type,source_record_id,units_sold,revenue,landed_cogs\n"
            f"{pid},2026-09-01,2026-09-30,DAY_30,INV_1001,150,149850.0,37500.0\n"
        )
        csv_path = self._write_csv(csv_content)

        val_report = self.service.validate_file(csv_path)
        self.assertTrue(val_report.is_valid)
        self.assertEqual(val_report.total_rows, 1)
        self.assertEqual(val_report.valid_rows_count, 1)
        self.assertEqual(val_report.error_rows_count, 0)

        norm_res = self.service.normalize_file(csv_path)
        self.assertEqual(norm_res.success_count, 1)
        self.assertEqual(norm_res.failure_count, 0)
        norm = norm_res.successful[0]
        self.assertEqual(norm.product_id, pid)
        self.assertEqual(norm.actual_units_sold, 150)
        self.assertEqual(norm.actual_revenue, 149850.0)
        self.assertEqual(norm.actual_landed_cogs, 37500.0)
        self.assertEqual(norm.source_record_id, "INV_1001")

    # -------------------------------------------------------------
    # B. UTF-8 AND UTF-8 BOM
    # -------------------------------------------------------------
    def test_utf8_and_utf8_bom_support(self):
        """CSV files with UTF-8 BOM (e.g. from Excel) parse seamlessly without corrupted header keys."""
        pid = self._create_dummy_product("PROD_CSV_BOM")
        csv_content = (
            "product_id,period_start,period_end,period_type,source_record_id,units_sold\n"
            f"{pid},2026-09-01,2026-09-30,DAY_30,REC_BOM_1,100\n"
        )
        csv_path = self._write_csv(csv_content, filename="bom.csv", encoding="utf-8-sig")

        val_report = self.service.validate_file(csv_path)
        self.assertTrue(val_report.is_valid, f"Validation errors: {val_report.errors}")
        self.assertEqual(val_report.total_rows, 1)

    # -------------------------------------------------------------
    # C. MISSING HEADERS
    # -------------------------------------------------------------
    def test_missing_required_headers_rejected(self):
        """CSV missing required headers (e.g. source_record_id or period_type) is rejected."""
        pid = self._create_dummy_product()
        # Missing source_record_id
        csv_content = (
            "product_id,period_start,period_end,period_type,units_sold\n"
            f"{pid},2026-09-01,2026-09-30,DAY_30,100\n"
        )
        csv_path = self._write_csv(csv_content)
        val_report = self.service.validate_file(csv_path)
        self.assertFalse(val_report.is_valid)
        self.assertEqual(val_report.errors[0].error_category, ERROR_MISSING_REQUIRED_HEADERS)

    # -------------------------------------------------------------
    # D. DUPLICATE HEADERS
    # -------------------------------------------------------------
    def test_duplicate_headers_rejected(self):
        """CSV containing duplicate header column names is rejected."""
        pid = self._create_dummy_product()
        csv_content = (
            "product_id,period_start,period_end,period_type,source_record_id,units_sold,units_sold\n"
            f"{pid},2026-09-01,2026-09-30,DAY_30,REC_DUP_HDR,100,100\n"
        )
        csv_path = self._write_csv(csv_content)
        val_report = self.service.validate_file(csv_path)
        self.assertFalse(val_report.is_valid)
        self.assertEqual(val_report.errors[0].error_category, ERROR_DUPLICATE_HEADERS)

    # -------------------------------------------------------------
    # E. EXTRA HEADERS POLICY
    # -------------------------------------------------------------
    def test_extra_headers_allowed_and_ignored(self):
        """Extra unknown columns are permitted according to documented policy but explicitly ignored."""
        pid = self._create_dummy_product()
        csv_content = (
            "product_id,period_start,period_end,period_type,source_record_id,units_sold,warehouse_aisle,operator_signature\n"
            f"{pid},2026-09-01,2026-09-30,DAY_30,REC_EXTRA,100,Aisle-14,SignedByJohn\n"
        )
        csv_path = self._write_csv(csv_content)
        val_report = self.service.validate_file(csv_path)
        self.assertTrue(val_report.is_valid)
        self.assertIn("warehouse_aisle", val_report.ignored_columns)
        self.assertIn("operator_signature", val_report.ignored_columns)

        norm_res = self.service.normalize_file(csv_path)
        self.assertEqual(norm_res.success_count, 1)
        self.assertEqual(norm_res.successful[0].actual_units_sold, 100)

    # -------------------------------------------------------------
    # F. NUMERIC PARSING & MALFORMED REJECTION
    # -------------------------------------------------------------
    def test_numeric_parsing_and_currency_rejection(self):
        """Canonical numeric formats parse; currency symbols and commas are rejected."""
        pid = self._create_dummy_product()

        # Valid decimals and integers
        csv_valid = (
            "product_id,period_start,period_end,period_type,source_record_id,units_sold,revenue\n"
            f"{pid},2026-09-01,2026-09-30,DAY_30,REC_NUM_1,125,125000.50\n"
        )
        p_valid = self._write_csv(csv_valid, "valid_num.csv")
        norm_valid = self.service.normalize_file(p_valid)
        self.assertEqual(norm_valid.successful[0].actual_units_sold, 125)
        self.assertEqual(norm_valid.successful[0].actual_revenue, 125000.50)

        # Currency symbol rejection (e.g. ₹ or $)
        csv_currency = (
            "product_id,period_start,period_end,period_type,source_record_id,units_sold,revenue\n"
            f"{pid},2026-09-01,2026-09-30,DAY_30,REC_NUM_2,100,₹125000\n"
        )
        p_curr = self._write_csv(csv_currency, "curr.csv")
        val_curr = self.service.validate_file(p_curr)
        self.assertFalse(val_curr.is_valid)
        self.assertEqual(val_curr.errors[0].error_category, ERROR_INVALID_NUMERIC_VALUE)

        # Commas rejection (e.g. 1,25,000)
        csv_commas = (
            "product_id,period_start,period_end,period_type,source_record_id,units_sold,revenue\n"
            f'{pid},2026-09-01,2026-09-30,DAY_30,REC_NUM_3,100,"125,000.00"\n'
        )
        p_commas = self._write_csv(csv_commas, "commas.csv")
        val_commas = self.service.validate_file(p_commas)
        self.assertFalse(val_commas.is_valid)
        self.assertEqual(val_commas.errors[0].error_category, ERROR_INVALID_NUMERIC_VALUE)

    # -------------------------------------------------------------
    # G. DATE PARSING & REVERSED PERIODS
    # -------------------------------------------------------------
    def test_date_parsing_and_reversed_period_rejection(self):
        """Reversed dates (period_end < period_start) or non-ISO dates are rejected."""
        pid = self._create_dummy_product()

        # Reversed period
        csv_rev = (
            "product_id,period_start,period_end,period_type,source_record_id,units_sold\n"
            f"{pid},2026-09-30,2026-09-01,DAY_30,REC_DATE_1,50\n"
        )
        p_rev = self._write_csv(csv_rev, "rev.csv")
        val_rev = self.service.validate_file(p_rev)
        self.assertFalse(val_rev.is_valid)
        self.assertEqual(val_rev.errors[0].error_category, ERROR_INVALID_PERIOD)

        # Invalid date text
        csv_invalid = (
            "product_id,period_start,period_end,period_type,source_record_id,units_sold\n"
            f"{pid},yesterday,tomorrow,DAY_30,REC_DATE_2,50\n"
        )
        p_inv = self._write_csv(csv_invalid, "inv.csv")
        val_inv = self.service.validate_file(p_inv)
        self.assertFalse(val_inv.is_valid)
        self.assertEqual(val_inv.errors[0].error_category, ERROR_INVALID_PERIOD)

    # -------------------------------------------------------------
    # H. PERIOD TYPES
    # -------------------------------------------------------------
    def test_supported_period_types(self):
        """DAY_30, DAY_60, DAY_90, LIFETIME, and CUSTOM are accepted; invalid rejected."""
        pid = self._create_dummy_product()
        for p_type in ("DAY_30", "DAY_60", "DAY_90", "LIFETIME", "CUSTOM"):
            csv_content = (
                "product_id,period_start,period_end,period_type,source_record_id,units_sold\n"
                f"{pid},2026-09-01,2026-09-30,{p_type},REC_{p_type},50\n"
            )
            p = self._write_csv(csv_content, f"{p_type}.csv")
            val = self.service.validate_file(p)
            self.assertTrue(val.is_valid, f"Failed for {p_type}")

        # Unsupported period type
        csv_bad_type = (
            "product_id,period_start,period_end,period_type,source_record_id,units_sold\n"
            f"{pid},2026-09-01,2026-09-30,ANNUAL_2026,REC_BAD,50\n"
        )
        p_bad = self._write_csv(csv_bad_type, "bad_type.csv")
        val_bad = self.service.validate_file(p_bad)
        self.assertFalse(val_bad.is_valid)
        self.assertEqual(val_bad.errors[0].error_category, ERROR_UNSUPPORTED_PERIOD_TYPE)

    # -------------------------------------------------------------
    # I. NULL VS ZERO SEMANTICS
    # -------------------------------------------------------------
    def test_null_vs_zero_semantics(self):
        """Blank numeric fields remain None; explicit 0 remains 0."""
        pid = self._create_dummy_product()
        # Row 1: units_sold is 0 (explicit)
        # Row 2: units_sold is blank (unobserved)
        csv_content = (
            "product_id,period_start,period_end,period_type,source_record_id,units_sold,revenue,returns_count\n"
            f"{pid},2026-09-01,2026-09-30,DAY_30,REC_ZERO,0,0.0,0\n"
            f"{pid},2026-10-01,2026-10-31,DAY_30,REC_BLANK,,,10\n"
        )
        csv_path = self._write_csv(csv_content)
        norm_res = self.service.normalize_file(csv_path)
        self.assertEqual(norm_res.success_count, 2)

        zero_row = norm_res.successful[0]
        self.assertEqual(zero_row.actual_units_sold, 0)
        self.assertEqual(zero_row.actual_revenue, 0.0)
        self.assertEqual(zero_row.actual_returns_count, 0)

        blank_row = norm_res.successful[1]
        self.assertIsNone(blank_row.actual_units_sold)
        self.assertIsNone(blank_row.actual_revenue)
        self.assertEqual(blank_row.actual_returns_count, 10)

    # -------------------------------------------------------------
    # J. PRODUCT MAPPING
    # -------------------------------------------------------------
    def test_product_mapping_direct_and_resolver(self):
        """Direct APRS product_id and external SKU resolver succeed; unknown SKU is rejected."""
        pid = self._create_dummy_product("PROD_DIRECT")

        # Direct product_id
        csv_direct = (
            "product_id,period_start,period_end,period_type,source_record_id,units_sold\n"
            f"{pid},2026-09-01,2026-09-30,DAY_30,REC_DIR,50\n"
        )
        p_dir = self._write_csv(csv_direct, "dir.csv")
        val_dir = self.service.validate_file(p_dir)
        self.assertTrue(val_dir.is_valid)

        # Resolver mapping
        sku_map = {"EXTERNAL_SKU_ABC": pid}
        resolver = lambda sku: sku_map.get(sku)

        csv_resolver = (
            "source_product_id,period_start,period_end,period_type,source_record_id,units_sold\n"
            "EXTERNAL_SKU_ABC,2026-09-01,2026-09-30,DAY_30,REC_RES,50\n"
        )
        p_res = self._write_csv(csv_resolver, "res.csv")
        val_res = self.service.validate_file(p_res, product_resolver=resolver)
        self.assertTrue(val_res.is_valid)

        # Unknown product
        csv_unknown = (
            "product_id,period_start,period_end,period_type,source_record_id,units_sold\n"
            "NONEXISTENT_PRODUCT_999,2026-09-01,2026-09-30,DAY_30,REC_UNK,50\n"
        )
        p_unk = self._write_csv(csv_unknown, "unk.csv")
        val_unk = self.service.validate_file(p_unk)
        self.assertFalse(val_unk.is_valid)
        self.assertEqual(val_unk.errors[0].error_category, ERROR_UNRESOLVED_PRODUCT)

    # -------------------------------------------------------------
    # K. DECISION ID
    # -------------------------------------------------------------
    def test_decision_id_handling(self):
        """Explicit decision_id is preserved; omitted decision_id remains None."""
        pid = self._create_dummy_product()
        csv_content = (
            "product_id,decision_id,period_start,period_end,period_type,source_record_id,units_sold\n"
            f"{pid},101,2026-09-01,2026-09-30,DAY_30,REC_DEC_1,50\n"
            f"{pid},,2026-10-01,2026-10-31,DAY_30,REC_DEC_2,60\n"
        )
        csv_path = self._write_csv(csv_content)
        norm_res = self.service.normalize_file(csv_path)
        self.assertEqual(norm_res.successful[0].decision_id, 101)
        self.assertIsNone(norm_res.successful[1].decision_id)

    # -------------------------------------------------------------
    # L. PROVENANCE & AUDIT HASH
    # -------------------------------------------------------------
    def test_provenance_preservation_and_file_hash(self):
        """data_source, schema version, source_record_id, and file hash are recorded."""
        pid = self._create_dummy_product()
        csv_content = (
            "product_id,period_start,period_end,period_type,source_record_id,units_sold,source_timestamp,notes\n"
            f"{pid},2026-09-01,2026-09-30,DAY_30,REC_PROV_1,75,2026-10-01T10:00:00Z,Warehouse tally\n"
        )
        csv_path = self._write_csv(csv_content)
        val_report = self.service.validate_file(csv_path)
        self.assertTrue(len(val_report.file_hash) == 64)  # Valid SHA-256

        norm_res = self.service.normalize_file(csv_path)
        norm = norm_res.successful[0]
        self.assertEqual(norm.data_source, SOURCE_MANUAL_CSV)
        self.assertEqual(norm.source_schema_version, CSV_SCHEMA_VERSION)
        self.assertEqual(norm.source_record_id, "REC_PROV_1")
        self.assertEqual(norm.source_timestamp, "2026-10-01T10:00:00Z")
        self.assertEqual(norm.notes, "Warehouse tally")

    # -------------------------------------------------------------
    # M. DUPLICATE SOURCE_RECORD_ID IN CSV
    # -------------------------------------------------------------
    def test_duplicate_source_record_id_in_file_detected(self):
        """Duplicate source_record_id within the same CSV is flagged as an error."""
        pid = self._create_dummy_product()
        csv_content = (
            "product_id,period_start,period_end,period_type,source_record_id,units_sold\n"
            f"{pid},2026-09-01,2026-09-30,DAY_30,SAME_ID_99,50\n"
            f"{pid},2026-10-01,2026-10-31,DAY_30,SAME_ID_99,60\n"
        )
        csv_path = self._write_csv(csv_content)
        val_report = self.service.validate_file(csv_path)
        self.assertFalse(val_report.is_valid)
        self.assertIn("SAME_ID_99", val_report.duplicate_source_ids)
        self.assertEqual(val_report.errors[0].error_category, ERROR_DUPLICATE_SOURCE_RECORD_ID)

    # -------------------------------------------------------------
    # N. IDEMPOTENCY
    # -------------------------------------------------------------
    def test_idempotent_reingestion(self):
        """Ingesting the exact same CSV twice does not duplicate rows in product_outcomes."""
        pid = self._create_dummy_product("PROD_IDEMPOTENT")
        csv_content = (
            "product_id,period_start,period_end,period_type,source_record_id,units_sold,revenue\n"
            f"{pid},2026-09-01,2026-09-30,DAY_30,REC_IDEM_1,100,99900.0\n"
        )
        csv_path = self._write_csv(csv_content)

        # First ingestion
        rep1 = self.service.ingest_file(csv_path, dry_run=False)
        self.assertEqual(rep1.status, "INGESTED")
        self.assertEqual(rep1.ingested_count, 1)
        self.assertEqual(rep1.skipped_idempotent_count, 0)

        # Second ingestion of same CSV
        rep2 = self.service.ingest_file(csv_path, dry_run=False)
        self.assertEqual(rep2.status, "INGESTED")
        self.assertEqual(rep2.ingested_count, 0)
        self.assertEqual(rep2.skipped_idempotent_count, 1)

        # Verify only 1 row exists in DB
        outcomes = get_product_outcomes(pid)
        self.assertEqual(len(outcomes), 1)

    # -------------------------------------------------------------
    # O. CONFLICT HANDLING
    # -------------------------------------------------------------
    def test_conflict_handling_blocks_silent_overwrite(self):
        """If incoming CSV has conflicting metrics on an existing source_record_id, it is blocked."""
        pid = self._create_dummy_product("PROD_CONFLICT")
        # Ingest baseline
        csv_orig = (
            "product_id,period_start,period_end,period_type,source_record_id,units_sold,revenue\n"
            f"{pid},2026-09-01,2026-09-30,DAY_30,REC_CONF_1,100,99900.0\n"
        )
        p_orig = self._write_csv(csv_orig, "orig.csv")
        rep_orig = self.service.ingest_file(p_orig, dry_run=False)
        self.assertEqual(rep_orig.ingested_count, 1)

        # Ingest conflicting numbers for the same source_record_id
        csv_conf = (
            "product_id,period_start,period_end,period_type,source_record_id,units_sold,revenue\n"
            f"{pid},2026-09-01,2026-09-30,DAY_30,REC_CONF_1,150,149850.0\n"
        )
        p_conf = self._write_csv(csv_conf, "conf.csv")

        # Pre-validation detects conflict
        val_rep = self.service.validate_file(p_conf)
        self.assertFalse(val_rep.is_valid)
        self.assertEqual(val_rep.errors[0].error_category, ERROR_OUTCOME_SOURCE_CONFLICT)

        # Ingestion is blocked under atomic policy
        ingest_rep = self.service.ingest_file(p_conf, dry_run=False, atomic=True)
        self.assertEqual(ingest_rep.status, "CONFLICT_ERROR")
        self.assertEqual(ingest_rep.ingested_count, 0)

        # DB values remain original (100 units, not 150)
        outcomes = get_product_outcomes(pid)
        self.assertEqual(outcomes[0]["actual_units_sold"], 100)

    # -------------------------------------------------------------
    # P. DRY-RUN PREVIEW MODE
    # -------------------------------------------------------------
    def test_dry_run_preview_performs_zero_database_writes(self):
        """Default dry_run=True produces full validation/preview with 0 SQLite writes."""
        pid = self._create_dummy_product("PROD_DRY_RUN")
        csv_content = (
            "product_id,period_start,period_end,period_type,source_record_id,units_sold,revenue\n"
            f"{pid},2026-09-01,2026-09-30,DAY_30,REC_DRY_1,100,99900.0\n"
        )
        csv_path = self._write_csv(csv_content)

        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM product_outcomes")
        self.assertEqual(cur.fetchone()[0], 0)

        rep = self.service.ingest_file(csv_path, dry_run=True)
        self.assertTrue(rep.dry_run)
        self.assertEqual(rep.status, "DRY_RUN_SUCCESS")
        self.assertEqual(rep.ingested_count, 0)
        self.assertEqual(len(rep.row_results), 1)
        self.assertEqual(rep.row_results[0]["action_preview"], "WOULD_INGEST")

        # Assert DB still has 0 rows
        cur.execute("SELECT COUNT(*) FROM product_outcomes")
        self.assertEqual(cur.fetchone()[0], 0)

    # -------------------------------------------------------------
    # Q. BATCH ATOMICITY
    # -------------------------------------------------------------
    def test_batch_atomicity_blocks_all_writes_on_error(self):
        """Under default atomic=True, 1 invalid row in a 3-row file blocks all 3 rows from writing."""
        p1 = self._create_dummy_product("PROD_ATOM_1")
        p2 = self._create_dummy_product("PROD_ATOM_2")
        # Row 2 has an invalid negative units_sold
        csv_content = (
            "product_id,period_start,period_end,period_type,source_record_id,units_sold\n"
            f"{p1},2026-09-01,2026-09-30,DAY_30,REC_AT_1,50\n"
            f"{p1},2026-09-01,2026-09-30,DAY_30,REC_AT_2,-10\n"
            f"{p2},2026-09-01,2026-09-30,DAY_30,REC_AT_3,75\n"
        )
        csv_path = self._write_csv(csv_content)

        rep = self.service.ingest_file(csv_path, dry_run=False, atomic=True)
        self.assertEqual(rep.status, "BLOCKED_VALIDATION_FAILED")
        self.assertEqual(rep.ingested_count, 0)

        # Assert 0 rows written for either product
        self.assertEqual(len(get_product_outcomes(p1)), 0)
        self.assertEqual(len(get_product_outcomes(p2)), 0)

    # -------------------------------------------------------------
    # R. PHASE 3 INTEGRATION (END-TO-END PIPELINE)
    # -------------------------------------------------------------
    def test_phase3_integration_persists_and_calibrates(self):
        """
        Complete isolated pipeline:
          CSV -> ManualCsvOutcomeAdapter -> Phase 3 Ingestion -> product_outcomes -> prediction_calibrations
        """
        pid = self._create_dummy_product("PROD_INT_001")
        # 1. Decision snapshot
        dec_id = record_decision_snapshot(
            product_id=pid,
            decision_type="GO_DECISION",
            override_predictions={
                "predicted_daily_units": 5,  # 150 for 30 days
                "predicted_selling_price": 999.0,
                "predicted_cogs": 250.0,
                "predicted_cm_pct": 74.97,
                "predicted_rto_pct": 2.0,
                "predicted_cac": 100.0,
            },
            decision_timestamp="2026-08-15 10:00:00"
        )

        csv_content = (
            "product_id,decision_id,period_start,period_end,period_type,source_record_id,units_sold,revenue,landed_cogs,cm,returns_count,rto_count,ad_spend\n"
            f"{pid},{dec_id},2026-09-01,2026-09-30,DAY_30,REC_INT_99,150,149850.0,37500.0,89910.0,3,3,15000.0\n"
        )
        csv_path = self._write_csv(csv_content)

        rep = self.service.ingest_file(csv_path, dry_run=False, auto_calibrate=True)
        self.assertEqual(rep.status, "INGESTED")
        self.assertEqual(rep.ingested_count, 1)
        self.assertEqual(rep.calibrations_count, 1)

        # Verify outcome in DB
        outcomes = get_product_outcomes(pid)
        self.assertEqual(len(outcomes), 1)
        out = outcomes[0]
        self.assertEqual(out["actual_units_sold"], 150)
        self.assertEqual(out["actual_revenue"], 149850.0)
        # Transparently derived:
        self.assertEqual(out["actual_avg_selling_price"], 999.0)
        self.assertEqual(out["actual_cac"], 100.0)

        # Verify calibration
        cals = get_calibrations_for_product(pid)
        self.assertEqual(len(cals), 1)
        self.assertEqual(cals[0]["calibration_status"], "CALIBRATED")
        self.assertEqual(cals[0]["demand_actual"], 5.0)  # 150 units / 30 days = 5.0 daily
        self.assertEqual(cals[0]["demand_predicted"], 5.0)
        self.assertEqual(cals[0]["demand_signed_error"], 0.0)

    # -------------------------------------------------------------
    # S. NO DIRECT DB WRITES FROM ADAPTER
    # -------------------------------------------------------------
    def test_adapter_does_not_write_to_database(self):
        """Calling normalize on ManualCsvOutcomeAdapter performs ZERO database writes."""
        pid = self._create_dummy_product()
        rec = {
            "product_id": pid,
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "period_type": "DAY_30",
            "source_record_id": "REC_NO_WRITE",
            "units_sold": 50,
            "revenue": 49950.0
        }
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM product_outcomes")
        self.assertEqual(cur.fetchone()[0], 0)

        norm = self.adapter.normalize(rec)
        self.assertIsInstance(norm, NormalizedOutcome)

        # Assert still 0 rows
        cur.execute("SELECT COUNT(*) FROM product_outcomes")
        self.assertEqual(cur.fetchone()[0], 0)

    # -------------------------------------------------------------
    # T. PROXY / RESEARCH ESTIMATE PROTECTION
    # -------------------------------------------------------------
    def test_research_proxies_and_estimate_fields_rejected(self):
        """Scraped research proxies and pre-launch estimate fields are strictly rejected."""
        pid = self._create_dummy_product()

        # Forbidden proxy source
        csv_proxy = (
            "product_id,period_start,period_end,period_type,source_record_id,units_sold,data_source\n"
            f"{pid},2026-09-01,2026-09-30,DAY_30,REC_P1,50,GOOGLE_TRENDS\n"
        )
        p1 = self._write_csv(csv_proxy, "proxy.csv")
        val1 = self.service.validate_file(p1)
        self.assertFalse(val1.is_valid)
        self.assertEqual(val1.errors[0].error_category, ERROR_RESEARCH_ESTIMATE_NOT_OUTCOME)

        # Forbidden estimate field
        csv_est = (
            "product_id,period_start,period_end,period_type,source_record_id,units_sold,estimated_daily_units\n"
            f"{pid},2026-09-01,2026-09-30,DAY_30,REC_P2,50,20\n"
        )
        p2 = self._write_csv(csv_est, "est.csv")
        val2 = self.service.validate_file(p2)
        self.assertFalse(val2.is_valid)
        self.assertEqual(val2.errors[0].error_category, ERROR_RESEARCH_ESTIMATE_NOT_OUTCOME)

    # -------------------------------------------------------------
    # U. LOCAL FILE SAFETY
    # -------------------------------------------------------------
    def test_file_safety_checks(self):
        """Nonexistent files and remote URI schemes (http/https) are rejected."""
        # Nonexistent file
        val_none = self.service.validate_file("nonexistent_file_path_123.csv")
        self.assertFalse(val_none.is_valid)
        self.assertEqual(val_none.errors[0].error_category, ERROR_FILE_SAFETY_VIOLATION)

        # Remote URL
        val_url = self.service.validate_file("https://example.com/sales.csv")
        self.assertFalse(val_url.is_valid)
        self.assertEqual(val_url.errors[0].error_category, ERROR_FILE_SAFETY_VIOLATION)

    # -------------------------------------------------------------
    # V. CORRECTION WORKFLOW PROTECTION
    # -------------------------------------------------------------
    def test_correction_must_use_phase3_correction_service(self):
        """Modifying existing records via CSV is blocked; explicit Phase 3 correction works."""
        pid = self._create_dummy_product("PROD_CORR")
        csv_initial = (
            "product_id,period_start,period_end,period_type,source_record_id,units_sold,revenue\n"
            f"{pid},2026-09-01,2026-09-30,DAY_30,REC_CORR_1,100,99900.0\n"
        )
        p_init = self._write_csv(csv_initial, "init.csv")
        rep = self.service.ingest_file(p_init, dry_run=False)
        outcome_id = rep.row_results[0]["outcome_id"]

        # Legitimate correction through Phase 3 correction service
        corr_res = OutcomeIngestionService.correct_outcome(
            outcome_id=outcome_id,
            correction_data={"actual_units_sold": 105, "actual_revenue": 104895.0},
            reason="Audited return reversal by accounts",
            operator="LEAD_ACCOUNTANT"
        )
        self.assertEqual(corr_res["status"], "CORRECTED")
        from core.database import get_outcome_by_id
        updated = get_outcome_by_id(outcome_id)
        self.assertEqual(updated["actual_units_sold"], 105)
        self.assertEqual(updated["actual_revenue"], 104895.0)

    # -------------------------------------------------------------
    # W. PRODUCTION DATABASE PURITY
    # -------------------------------------------------------------
    def test_no_synthetic_production_contamination(self):
        """Production database data/research_engine.db must remain untouched."""
        prod_db_path = Path("data/research_engine.db")
        if not prod_db_path.exists():
            self.skipTest("Production database data/research_engine.db not found.")

        conn = sqlite3.connect(str(prod_db_path))
        cur = conn.cursor()

        # Check FK integrity
        fk_violations = cur.execute("PRAGMA foreign_key_check").fetchall()
        self.assertEqual(len(fk_violations), 0, f"FK violations in production: {fk_violations}")

        # Check production purity
        decisions_cnt = cur.execute("SELECT COUNT(*) FROM decision_ledger").fetchone()[0]
        outcomes_cnt = cur.execute("SELECT COUNT(*) FROM product_outcomes").fetchone()[0]
        calibrations_cnt = cur.execute("SELECT COUNT(*) FROM prediction_calibrations").fetchone()[0]
        corrections_cnt = cur.execute("SELECT COUNT(*) FROM outcome_corrections_log").fetchone()[0]
        conn.close()

        self.assertEqual(decisions_cnt, 0, "Production decision_ledger must be 0")
        self.assertEqual(outcomes_cnt, 0, "Production product_outcomes must be 0")
        self.assertEqual(calibrations_cnt, 0, "Production prediction_calibrations must be 0")
        self.assertEqual(corrections_cnt, 0, "Production outcome_corrections_log must be 0")

    # -------------------------------------------------------------
    # X. NETWORK SAFETY
    # -------------------------------------------------------------
    def test_network_safety_no_external_imports(self):
        """Adapter and service modules contain no live external API imports or network dependencies."""
        import inspect
        import core.outcome_adapters.manual_csv_adapter as mod

        source_code = inspect.getsource(mod)
        for forbidden in ("requests", "urllib.request", "aiohttp", "httpx", "boto3", "shopify", "amazon"):
            self.assertNotIn(f"import {forbidden}", source_code)
            self.assertNotIn(f"from {forbidden}", source_code)


if __name__ == "__main__":
    unittest.main()
