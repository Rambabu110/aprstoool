"""
APRS V8 PHASE 4B: SOURCE ADAPTER & OUTCOME NORMALIZATION TESTS
==============================================================
Comprehensive tests validating:
  1. Adapter interface and contract (source_name, source_version, validate_source_record)
  2. Provenance preservation (data_source, source_record_id, schema_version, notes)
  3. NULL semantics preservation (NULL != 0; missing values remain None, explicit 0 preserved)
  4. Product identity resolution and strict rejection of unresolvable SKUs
  5. Decision identity preservation and non-invention
  6. Calendar period semantics (DAY_30, DAY_60, DAY_90, LIFETIME, CUSTOM; end >= start)
  7. Validation and numeric bounds (non-negative, percentage 0-100, returns <= units)
  8. Research proxy and estimate protection (rejection of scraped proxies / estimate fields)
  9. Batch normalization determinism and error isolation
  10. Persistence boundary (adapter never writes directly to SQLite)
  11. End-to-end integration: Adapter -> NormalizedOutcome -> Phase 3 Ingestion -> Calibration
  12. Production database purity verification
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
    FixtureOutcomeAdapter,
    ManualFixtureAdapter,
    NormalizedOutcome,
    ValidationResult,
    BatchNormalizationResult,
    SOURCE_FIXTURE,
    ERROR_INVALID_SOURCE_RECORD,
    ERROR_MISSING_PRODUCT_ID,
    ERROR_UNRESOLVED_PRODUCT,
    ERROR_INVALID_PERIOD,
    ERROR_UNSUPPORTED_PERIOD_TYPE,
    ERROR_INVALID_NUMERIC_VALUE,
    ERROR_INVALID_PERCENTAGE,
    ERROR_RESEARCH_ESTIMATE_NOT_OUTCOME,
)


class TestAPRSV8OutcomeAdapters(unittest.TestCase):

    def setUp(self):
        """Create an isolated temporary SQLite database for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_v8_adapters.db"
        self.orig_db_path = os.environ.get("APRS_DB_PATH")
        os.environ["APRS_DB_PATH"] = str(self.db_path)
        init_db()
        self.conn = get_connection()
        self.adapter = FixtureOutcomeAdapter(version="1.0.0")

    def tearDown(self):
        """Clean up test database and restore environment."""
        self.conn.close()
        if self.orig_db_path:
            os.environ["APRS_DB_PATH"] = self.orig_db_path
        elif "APRS_DB_PATH" in os.environ:
            del os.environ["APRS_DB_PATH"]
        self.temp_dir.cleanup()

    def _create_dummy_product(self, product_id="PROD_ADAPT_001", name="Ceramic Coffee Mug", msrp=999.0, cogs=250.0):
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

    # -------------------------------------------------------------
    # 1. ADAPTER CONTRACT
    # -------------------------------------------------------------
    def test_adapter_exposes_source_identity_and_version(self):
        """Adapter must expose canonical source name and version string."""
        self.assertEqual(self.adapter.source_name, SOURCE_FIXTURE)
        self.assertEqual(self.adapter.source_version, "1.0.0")
        custom_adapter = FixtureOutcomeAdapter(version="2.1.0")
        self.assertEqual(custom_adapter.source_version, "2.1.0")
        # Check alias
        self.assertIs(ManualFixtureAdapter, FixtureOutcomeAdapter)

    def test_valid_fixture_normalizes_successfully(self):
        """Valid source record produces a complete NormalizedOutcome."""
        pid = self._create_dummy_product()
        record = {
            "product_id": pid,
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "period_type": "DAY_30",
            "units_sold": 150,
            "revenue": 149850.0,
            "cogs": 37500.0,
            "source_record_id": "REC_FIX_001",
            "timestamp": "2026-10-01T10:00:00Z"
        }
        res = self.adapter.normalize(record)
        self.assertIsInstance(res, NormalizedOutcome)
        self.assertEqual(res.product_id, pid)
        self.assertEqual(res.actual_units_sold, 150)
        self.assertEqual(res.actual_revenue, 149850.0)
        self.assertEqual(res.actual_landed_cogs, 37500.0)
        self.assertEqual(res.data_source, SOURCE_FIXTURE)
        self.assertEqual(res.source_record_id, "REC_FIX_001")
        self.assertEqual(res.source_timestamp, "2026-10-01T10:00:00Z")

    def test_validate_source_record_non_throwing(self):
        """validate_source_record returns ValidationResult without raising exceptions."""
        pid = self._create_dummy_product()
        valid_rec = {
            "product_id": pid,
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "units_sold": 50,
        }
        v_res = self.adapter.validate_source_record(valid_rec)
        self.assertTrue(v_res.is_valid)
        self.assertEqual(len(v_res.errors), 0)

        invalid_rec = {
            "product_id": pid,
            "period_start": "2026-09-30",
            "period_end": "2026-09-01",  # End before start
            "units_sold": -10,  # Negative units
        }
        inv_res = self.adapter.validate_source_record(invalid_rec)
        self.assertFalse(inv_res.is_valid)
        self.assertGreater(len(inv_res.errors), 0)

    # -------------------------------------------------------------
    # 2. PROVENANCE PRESERVATION
    # -------------------------------------------------------------
    def test_provenance_preservation(self):
        """Source provenance fields must be preserved exactly."""
        pid = self._create_dummy_product()
        record = {
            "product_id": pid,
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "period_type": "DAY_30",
            "source_record_id": "EXT_ORD_88992",
            "sku": "EXT-SKU-MUG-BLUE",
            "timestamp": "2026-10-01T08:30:00Z",
            "reference": "BATCH_RUN_OCT_01",
            "notes": "Verified against warehouse inventory audit"
        }
        res = self.adapter.normalize(record)
        self.assertEqual(res.data_source, SOURCE_FIXTURE)
        self.assertEqual(res.source_record_id, "EXT_ORD_88992")
        self.assertEqual(res.source_product_id, "EXT-SKU-MUG-BLUE")
        self.assertEqual(res.source_schema_version, "1.0.0")
        self.assertEqual(res.source_timestamp, "2026-10-01T08:30:00Z")
        self.assertEqual(res.raw_reference, "BATCH_RUN_OCT_01")
        self.assertEqual(res.notes, "Verified against warehouse inventory audit")

    def test_provenance_in_phase3_payload_notes(self):
        """to_phase3_payload serializes provenance metadata cleanly into notes."""
        pid = self._create_dummy_product()
        record = {
            "product_id": pid,
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "source_record_id": "REC_PROV_77",
            "sku": "SKU_77",
            "timestamp": "2026-10-02T12:00:00",
            "notes": "Monthly close"
        }
        norm = self.adapter.normalize(record)
        payload = norm.to_phase3_payload()
        self.assertIn("Monthly close", payload["notes"])
        self.assertIn("schema_v:1.0.0", payload["notes"])
        self.assertIn("src_sku:SKU_77", payload["notes"])
        self.assertIn("src_time:2026-10-02T12:00:00", payload["notes"])

    # -------------------------------------------------------------
    # 3. NULL SEMANTICS (NULL != 0)
    # -------------------------------------------------------------
    def test_null_semantics_missing_values_remain_none(self):
        """Missing metrics must remain None; never converted to zero."""
        pid = self._create_dummy_product()
        record = {
            "product_id": pid,
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "period_type": "DAY_30",
            "units_sold": 100,
            # revenue, ad_spend, cogs, returns omitted
        }
        res = self.adapter.normalize(record)
        self.assertEqual(res.actual_units_sold, 100)
        self.assertIsNone(res.actual_revenue)
        self.assertIsNone(res.actual_landed_cogs)
        self.assertIsNone(res.actual_returns_count)
        self.assertIsNone(res.actual_ad_spend)
        self.assertIsNone(res.actual_cac)
        self.assertIsNone(res.actual_stockout_days)

    def test_null_semantics_explicit_zero_preserved(self):
        """Explicit zero reported by source must remain 0, not None."""
        pid = self._create_dummy_product()
        record = {
            "product_id": pid,
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "units_sold": 0,
            "revenue": 0.0,
            "returns": 0,
            "ad_spend": 0.0,
            "stockout_days": 0,
        }
        res = self.adapter.normalize(record)
        self.assertEqual(res.actual_units_sold, 0)
        self.assertEqual(res.actual_revenue, 0.0)
        self.assertEqual(res.actual_returns_count, 0)
        self.assertEqual(res.actual_ad_spend, 0.0)
        self.assertEqual(res.actual_stockout_days, 0)

    def test_null_semantics_missing_units_not_converted_to_zero(self):
        """Missing units_sold must remain None and not convert to 0."""
        pid = self._create_dummy_product()
        record = {
            "product_id": pid,
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "revenue": 5000.0,
        }
        res = self.adapter.normalize(record)
        self.assertIsNone(res.actual_units_sold)
        self.assertNotEqual(res.actual_units_sold, 0)

    # -------------------------------------------------------------
    # 4. PRODUCT IDENTITY
    # -------------------------------------------------------------
    def test_product_identity_valid_aprs_product_resolves(self):
        """Valid APRS product_id in catalog resolves cleanly."""
        pid = self._create_dummy_product("PROD_ADAPT_VALID")
        record = {
            "product_id": pid,
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "units_sold": 20
        }
        res = self.adapter.normalize(record)
        self.assertEqual(res.product_id, "PROD_ADAPT_VALID")

    def test_product_identity_unknown_product_rejected(self):
        """Nonexistent product in APRS catalog is rejected with UNRESOLVED_PRODUCT."""
        record = {
            "product_id": "UNKNOWN_NONEXISTENT_SKU_999",
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "units_sold": 10
        }
        with self.assertRaises(ValueError) as ctx:
            self.adapter.normalize(record)
        self.assertIn(ERROR_UNRESOLVED_PRODUCT, str(ctx.exception))

    def test_product_identity_missing_product_rejected(self):
        """Record lacking product identifiers raises MISSING_PRODUCT_ID."""
        record = {
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "units_sold": 10
        }
        with self.assertRaises(ValueError) as ctx:
            self.adapter.normalize(record)
        self.assertIn(ERROR_MISSING_PRODUCT_ID, str(ctx.exception))

    def test_product_identity_external_resolver_mapping(self):
        """Custom resolver maps source SKU/ASIN to verified APRS product_id."""
        pid = self._create_dummy_product("PROD_INTERNAL_001")
        
        sku_map = {"AMZN_ASIN_B09XYZ": pid}
        resolver = lambda src_id: sku_map.get(src_id)

        record = {
            "source_product_id": "AMZN_ASIN_B09XYZ",
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "units_sold": 75
        }
        res = self.adapter.normalize(record, product_resolver=resolver)
        self.assertEqual(res.product_id, pid)
        self.assertEqual(res.source_product_id, "AMZN_ASIN_B09XYZ")

    def test_product_identity_adapter_does_not_create_master_product(self):
        """Adapter never inserts unresolvable products into master_products."""
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM master_products")
        count_before = cur.fetchone()[0]

        record = {
            "product_id": "AUTO_CREATE_ATTEMPT_99",
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "units_sold": 5
        }
        try:
            self.adapter.normalize(record)
        except ValueError:
            pass

        cur.execute("SELECT COUNT(*) FROM master_products")
        count_after = cur.fetchone()[0]
        self.assertEqual(count_before, count_after)

    # -------------------------------------------------------------
    # 5. DECISION IDENTITY
    # -------------------------------------------------------------
    def test_decision_identity_explicit_decision_id_preserved(self):
        """Explicit decision ID in source record is preserved."""
        pid = self._create_dummy_product()
        record = {
            "product_id": pid,
            "decision_id": 42,
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "units_sold": 10
        }
        res = self.adapter.normalize(record)
        self.assertEqual(res.decision_id, 42)

    def test_decision_identity_missing_decision_id_remains_none(self):
        """Missing decision ID remains None without inventing or selecting latest decision."""
        pid = self._create_dummy_product()
        record = {
            "product_id": pid,
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "units_sold": 10
        }
        res = self.adapter.normalize(record)
        self.assertIsNone(res.decision_id)

    # -------------------------------------------------------------
    # 6. PERIOD SEMANTICS
    # -------------------------------------------------------------
    def test_period_semantics_supported_types(self):
        """Supported period types (DAY_30, DAY_60, DAY_90, LIFETIME, CUSTOM) are accepted."""
        pid = self._create_dummy_product()
        for p_type in ("DAY_30", "DAY_60", "DAY_90", "LIFETIME", "CUSTOM"):
            rec = {
                "product_id": pid,
                "period_start": "2026-09-01",
                "period_end": "2026-09-30",
                "period_type": p_type,
                "units_sold": 10
            }
            res = self.adapter.normalize(rec)
            self.assertEqual(res.period_type, p_type)

    def test_period_semantics_invalid_type_rejected(self):
        """Unsupported period type raises UNSUPPORTED_PERIOD_TYPE."""
        pid = self._create_dummy_product()
        rec = {
            "product_id": pid,
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "period_type": "ANNUAL_Q4_2026",
            "units_sold": 10
        }
        with self.assertRaises(ValueError) as ctx:
            self.adapter.normalize(rec)
        self.assertIn(ERROR_UNSUPPORTED_PERIOD_TYPE, str(ctx.exception))

    def test_period_semantics_end_before_start_rejected(self):
        """period_end preceding period_start raises INVALID_PERIOD."""
        pid = self._create_dummy_product()
        rec = {
            "product_id": pid,
            "period_start": "2026-09-30",
            "period_end": "2026-09-01",
            "units_sold": 10
        }
        with self.assertRaises(ValueError) as ctx:
            self.adapter.normalize(rec)
        self.assertIn(ERROR_INVALID_PERIOD, str(ctx.exception))

    def test_period_semantics_invalid_date_format_rejected(self):
        """Non-ISO date string raises INVALID_PERIOD."""
        pid = self._create_dummy_product()
        rec = {
            "product_id": pid,
            "period_start": "yesterday",
            "period_end": "tomorrow",
            "units_sold": 10
        }
        with self.assertRaises(ValueError) as ctx:
            self.adapter.normalize(rec)
        self.assertIn(ERROR_INVALID_PERIOD, str(ctx.exception))

    # -------------------------------------------------------------
    # 7. VALIDATION & VALUE BOUNDS
    # -------------------------------------------------------------
    def test_validation_negative_units_rejected(self):
        """Negative units_sold raises INVALID_NUMERIC_VALUE."""
        pid = self._create_dummy_product()
        rec = {
            "product_id": pid,
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "units_sold": -50
        }
        with self.assertRaises(ValueError) as ctx:
            self.adapter.normalize(rec)
        self.assertIn(ERROR_INVALID_NUMERIC_VALUE, str(ctx.exception))

    def test_validation_negative_revenue_rejected(self):
        """Negative revenue raises INVALID_NUMERIC_VALUE."""
        pid = self._create_dummy_product()
        rec = {
            "product_id": pid,
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "revenue": -1200.0
        }
        with self.assertRaises(ValueError) as ctx:
            self.adapter.normalize(rec)
        self.assertIn(ERROR_INVALID_NUMERIC_VALUE, str(ctx.exception))

    def test_validation_invalid_percentage_rejected(self):
        """Percentages exceeding 100% or below 0% raise INVALID_PERCENTAGE."""
        pid = self._create_dummy_product()
        rec = {
            "product_id": pid,
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "return_rate_pct": 115.0
        }
        with self.assertRaises(ValueError) as ctx:
            self.adapter.normalize(rec)
        self.assertIn(ERROR_INVALID_PERCENTAGE, str(ctx.exception))

    def test_validation_returns_exceeding_units_rejected(self):
        """returns_count exceeding units_sold raises INVALID_NUMERIC_VALUE."""
        pid = self._create_dummy_product()
        rec = {
            "product_id": pid,
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "units_sold": 50,
            "returns": 65
        }
        with self.assertRaises(ValueError) as ctx:
            self.adapter.normalize(rec)
        self.assertIn(ERROR_INVALID_NUMERIC_VALUE, str(ctx.exception))

    # -------------------------------------------------------------
    # 8. RESEARCH PROXY & PRE-LAUNCH ESTIMATE PROTECTION
    # -------------------------------------------------------------
    def test_research_proxy_source_rejected(self):
        """Scraped research sources (GOOGLE_TRENDS, COMPETITOR_BSR, etc.) are strictly rejected."""
        pid = self._create_dummy_product()
        for forbidden in ("GOOGLE_TRENDS", "COMPETITOR_BSR", "SCRAPED_ESTIMATE", "HELIUM_ESTIMATE"):
            rec = {
                "product_id": pid,
                "data_source": forbidden,
                "period_start": "2026-09-01",
                "period_end": "2026-09-30",
                "units_sold": 100
            }
            with self.assertRaises(ValueError) as ctx:
                self.adapter.normalize(rec)
            self.assertIn(ERROR_RESEARCH_ESTIMATE_NOT_OUTCOME, str(ctx.exception))

    def test_research_estimate_field_rejected(self):
        """Pre-launch estimate fields (estimated_daily_units, helium_monthly_revenue) are rejected."""
        pid = self._create_dummy_product()
        rec = {
            "product_id": pid,
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "estimated_daily_units": 25,
            "units_sold": 100
        }
        with self.assertRaises(ValueError) as ctx:
            self.adapter.normalize(rec)
        self.assertIn(ERROR_RESEARCH_ESTIMATE_NOT_OUTCOME, str(ctx.exception))

    # -------------------------------------------------------------
    # 9. BATCH NORMALIZATION
    # -------------------------------------------------------------
    def test_batch_normalization_deterministic_ordering(self):
        """Batch normalization preserves exact ordering of successful records."""
        p1 = self._create_dummy_product("PROD_BATCH_1")
        p2 = self._create_dummy_product("PROD_BATCH_2")
        records = [
            {"product_id": p1, "period_start": "2026-09-01", "period_end": "2026-09-30", "units_sold": 10},
            {"product_id": p2, "period_start": "2026-09-01", "period_end": "2026-09-30", "units_sold": 20},
        ]
        b_res = self.adapter.normalize_many(records)
        self.assertIsInstance(b_res, BatchNormalizationResult)
        self.assertEqual(b_res.total_count, 2)
        self.assertEqual(b_res.success_count, 2)
        self.assertEqual(b_res.failure_count, 0)
        self.assertEqual(b_res.successful[0].product_id, p1)
        self.assertEqual(b_res.successful[1].product_id, p2)

    def test_batch_normalization_isolation(self):
        """One invalid record in a batch does not corrupt or abort valid records."""
        p1 = self._create_dummy_product("PROD_ISO_1")
        p2 = self._create_dummy_product("PROD_ISO_2")
        records = [
            {"product_id": p1, "period_start": "2026-09-01", "period_end": "2026-09-30", "units_sold": 10},
            {"product_id": "NONEXISTENT_SKU", "period_start": "2026-09-01", "period_end": "2026-09-30", "source_record_id": "FAIL_01"},
            {"product_id": p2, "period_start": "2026-09-01", "period_end": "2026-09-30", "units_sold": 30},
        ]
        b_res = self.adapter.normalize_many(records)
        self.assertEqual(b_res.total_count, 3)
        self.assertEqual(b_res.success_count, 2)
        self.assertEqual(b_res.failure_count, 1)

        failed_item = b_res.failed[0]
        self.assertEqual(failed_item.index, 1)
        self.assertEqual(failed_item.source_record_id, "FAIL_01")
        self.assertEqual(failed_item.error_category, ERROR_UNRESOLVED_PRODUCT)

    # -------------------------------------------------------------
    # 10. PERSISTENCE BOUNDARY (RULE 1)
    # -------------------------------------------------------------
    def test_adapter_does_not_write_to_database(self):
        """Normalizing single or batch records creates zero rows in database tables."""
        pid = self._create_dummy_product("PROD_NO_WRITE")
        cur = self.conn.cursor()

        rec = {
            "product_id": pid,
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "units_sold": 150,
            "revenue": 149850.0
        }
        # Run normalization
        norm = self.adapter.normalize(rec)
        self.assertIsNotNone(norm)

        # Assert 0 rows in product_outcomes
        cur.execute("SELECT COUNT(*) FROM product_outcomes")
        self.assertEqual(cur.fetchone()[0], 0)

        # Assert 0 rows in prediction_calibrations
        cur.execute("SELECT COUNT(*) FROM prediction_calibrations")
        self.assertEqual(cur.fetchone()[0], 0)

        # Assert 0 rows in decision_ledger
        cur.execute("SELECT COUNT(*) FROM decision_ledger")
        self.assertEqual(cur.fetchone()[0], 0)

    # -------------------------------------------------------------
    # 11. END-TO-END PIPELINE INTEGRATION WITH PHASE 3
    # -------------------------------------------------------------
    def test_pipeline_integration_adapter_to_phase3_ingestion(self):
        """
        Demonstrates complete isolated pipeline:
          FixtureOutcomeAdapter -> NormalizedOutcome -> OutcomeIngestionService -> DB
        """
        pid = self._create_dummy_product("PROD_E2E_001")

        # 1. Freeze historical decision snapshot
        dec_id = record_decision_snapshot(
            product_id=pid,
            decision_type="GO_DECISION",
            override_predictions={
                "predicted_daily_units": 4,  # ~120 for 30 days
                "predicted_selling_price": 999.0,
                "predicted_cogs": 250.0,
                "predicted_cm_pct": 74.97,
                "predicted_rto_pct": 5.0,
                "predicted_cac": 150.0,
                "frozen_score": 85.0,
                "frozen_confidence": 0.85
            },
            decision_timestamp="2026-08-15 10:00:00"
        )

        # 2. Source adapter receives raw external record
        source_record = {
            "product_id": pid,
            "decision_id": dec_id,
            "period_start": "2026-09-01",
            "period_end": "2026-09-30",
            "period_type": "DAY_30",
            "units_sold": 120,
            "revenue": 119880.0,
            "cogs": 30000.0,
            "cm": 71880.0,
            "returns": 6,
            "rto": 2,
            "ad_spend": 18000.0,
            "source_record_id": "EXT_INVOICE_9001",
            "timestamp": "2026-10-01T09:00:00Z"
        }

        # 3. Adapter validates and normalizes
        norm_outcome = self.adapter.normalize(source_record)
        self.assertEqual(norm_outcome.actual_units_sold, 120)

        # 4. Convert to Phase 3 payload and ingest
        phase3_payload = norm_outcome.to_phase3_payload()
        ingest_res = OutcomeIngestionService.ingest_outcome(phase3_payload)
        self.assertEqual(ingest_res["status"], "CREATED")

        # 5. Verify database state
        outcomes = get_product_outcomes(pid)
        self.assertEqual(len(outcomes), 1)
        db_out = outcomes[0]
        self.assertEqual(db_out["actual_units_sold"], 120)
        self.assertEqual(db_out["actual_revenue"], 119880.0)
        # Transparently derived by Phase 3:
        self.assertEqual(db_out["actual_avg_selling_price"], 999.0)
        self.assertEqual(db_out["actual_return_rate_pct"], 5.0)

        # 6. Verify deterministic calibration triggered
        calibrations = get_calibrations_for_product(pid)
        self.assertEqual(len(calibrations), 1)
        cal = calibrations[0]
        self.assertEqual(cal["calibration_status"], "CALIBRATED")
        self.assertEqual(cal["demand_actual"], 4.0)  # 120 units / 30 days = 4.0 daily velocity
        self.assertEqual(cal["demand_predicted"], 4.0)
        self.assertEqual(cal["demand_signed_error"], 0.0)
        self.assertEqual(cal["decision_id"], dec_id)

    # -------------------------------------------------------------
    # 12. PRODUCTION DATABASE PURITY
    # -------------------------------------------------------------
    def test_no_synthetic_production_contamination(self):
        """Authoritative production database data/research_engine.db must have 0 V8 rows."""
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


if __name__ == "__main__":
    unittest.main()
