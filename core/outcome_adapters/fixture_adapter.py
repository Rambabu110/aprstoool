"""
APRS V8 PHASE 4B: FIXTURE OUTCOME ADAPTER
=========================================
Architectural Layer: Reference Test Adapter
Purpose:
  Provides an isolated, in-memory reference adapter demonstrating the
  OutcomeSourceAdapter contract without external API connections or DB writes.

Guarantees:
  - 100% in-memory deterministic transformation.
  - Zero database writes (does NOT touch product_outcomes or decision_ledger).
  - Preserves NULL semantics (None != 0).
  - Preserves source provenance metadata.
  - Strictly rejects research proxies and pre-launch estimates.
"""

from typing import Dict, Any, Optional, Callable

from core.outcome_adapters.base import (
    OutcomeSourceAdapter,
    NormalizedOutcome,
    ValidationResult,
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
from core.outcome_adapters.normalizer import (
    check_research_proxy_rejection,
    resolve_product_identity,
    validate_and_normalize_period,
    clean_non_negative_int,
    clean_non_negative_float,
    clean_percentage,
)


class FixtureOutcomeAdapter(OutcomeSourceAdapter):
    """
    Reference in-memory fixture adapter for APRS V8 outcome observations.
    Demonstrates source-specific field extraction, normalization, and validation.
    """

    def __init__(self, version: str = "1.0.0"):
        self._version = version

    @property
    def source_name(self) -> str:
        return SOURCE_FIXTURE

    @property
    def source_version(self) -> str:
        return self._version

    def validate_source_record(self, record: Dict[str, Any]) -> ValidationResult:
        """
        Validates source record structure without throwing exceptions.
        Returns a ValidationResult with errors and machine-readable error category.
        """
        result = ValidationResult(is_valid=True)
        if not isinstance(record, dict):
            result.add_error("Source record must be a dictionary.", ERROR_INVALID_SOURCE_RECORD)
            return result

        # Check research proxies
        try:
            data_src = record.get("data_source", self.source_name)
            check_research_proxy_rejection(data_src, record)
        except ValueError as e:
            result.add_error(str(e), ERROR_RESEARCH_ESTIMATE_NOT_OUTCOME)
            return result

        # Check product identity
        raw_pid = record.get("product_id") or record.get("aprs_product_id")
        src_pid = record.get("source_product_id") or record.get("sku") or record.get("asin")
        if not raw_pid and not src_pid:
            result.add_error("Record must contain product_id or source_product_id.", ERROR_MISSING_PRODUCT_ID)

        # Check period
        p_start = record.get("period_start")
        p_end = record.get("period_end")
        p_type = record.get("period_type", "DAY_30")
        try:
            validate_and_normalize_period(p_start, p_end, p_type)
        except ValueError as e:
            err_str = str(e)
            cat = ERROR_UNSUPPORTED_PERIOD_TYPE if ERROR_UNSUPPORTED_PERIOD_TYPE in err_str else ERROR_INVALID_PERIOD
            result.add_error(err_str, cat)

        # Check numeric types if provided
        for int_field in ("actual_units_sold", "units_sold", "units", "actual_returns_count", "returns", "actual_rto_count", "rto"):
            if int_field in record and record[int_field] is not None:
                try:
                    clean_non_negative_int(record[int_field], int_field)
                except ValueError as e:
                    result.add_error(str(e), ERROR_INVALID_NUMERIC_VALUE)

        for float_field in ("actual_revenue", "revenue", "actual_landed_cogs", "cogs", "actual_ad_spend", "ad_spend"):
            if float_field in record and record[float_field] is not None:
                try:
                    clean_non_negative_float(record[float_field], float_field)
                except ValueError as e:
                    result.add_error(str(e), ERROR_INVALID_NUMERIC_VALUE)

        for pct_field in ("actual_return_rate_pct", "return_rate_pct", "actual_rto_rate_pct", "rto_rate_pct"):
            if pct_field in record and record[pct_field] is not None:
                try:
                    clean_percentage(record[pct_field], pct_field)
                except ValueError as e:
                    result.add_error(str(e), ERROR_INVALID_PERCENTAGE)

        return result

    def normalize(
        self,
        record: Dict[str, Any],
        product_resolver: Optional[Callable[[str], Optional[str]]] = None
    ) -> NormalizedOutcome:
        """
        Normalizes a source record into a canonical NormalizedOutcome.
        
        Preserves:
          - NULL semantics (None != 0).
          - Source provenance (source_record_id, schema_version, raw_reference).
          - Exact period bounds.
        
        Raises ValueError with machine-readable category on invalid data.
        """
        if not isinstance(record, dict):
            raise ValueError(f"{ERROR_INVALID_SOURCE_RECORD}: Record must be a dictionary.")

        # 1. Enforce research proxy boundary
        data_src = record.get("data_source", self.source_name)
        check_research_proxy_rejection(data_src, record)

        # 2. Resolve Product Identity
        raw_pid = record.get("product_id") or record.get("aprs_product_id")
        src_pid = record.get("source_product_id") or record.get("sku") or record.get("asin")
        resolved_pid = resolve_product_identity(
            raw_product_id=raw_pid,
            source_product_id=src_pid,
            product_resolver=product_resolver
        )

        # 3. Validate & Normalize Calendar Period
        p_start = record.get("period_start")
        p_end = record.get("period_end")
        p_type = record.get("period_type", "DAY_30")
        clean_start, clean_end, clean_type = validate_and_normalize_period(p_start, p_end, p_type)

        # 4. Extract and preserve Decision Identity if present
        raw_dec_id = record.get("decision_id")
        clean_dec_id = None
        if raw_dec_id is not None and str(raw_dec_id).strip() != "":
            try:
                clean_dec_id = int(raw_dec_id)
            except (ValueError, TypeError):
                raise ValueError(f"{ERROR_INVALID_NUMERIC_VALUE}: decision_id must be an integer, got '{raw_dec_id}'.")

        # 5. Extract Metrics with strict NULL preservation (None != 0)
        def _get_int(*field_keys: str) -> Optional[int]:
            for key in field_keys:
                if key in record and record[key] is not None and record[key] != "":
                    return clean_non_negative_int(record[key], key)
            return None

        def _get_float(*field_keys: str) -> Optional[float]:
            for key in field_keys:
                if key in record and record[key] is not None and record[key] != "":
                    return clean_non_negative_float(record[key], key)
            return None

        def _get_pct(*field_keys: str) -> Optional[float]:
            for key in field_keys:
                if key in record and record[key] is not None and record[key] != "":
                    return clean_percentage(record[key], key)
            return None

        units = _get_int("actual_units_sold", "units_sold", "units")
        revenue = _get_float("actual_revenue", "revenue", "gross_sales")
        asp = _get_float("actual_avg_selling_price", "avg_selling_price", "asp", "selling_price")
        cogs = _get_float("actual_landed_cogs", "landed_cogs", "cogs")
        cm = _get_float("actual_contribution_margin", "contribution_margin", "cm")
        cm_pct = _get_float("actual_cm_pct", "cm_pct")
        returns = _get_int("actual_returns_count", "returns_count", "returns")
        return_rate_pct = _get_pct("actual_return_rate_pct", "return_rate_pct")
        rto = _get_int("actual_rto_count", "rto_count", "rto")
        rto_rate_pct = _get_pct("actual_rto_rate_pct", "rto_rate_pct")
        ad_spend = _get_float("actual_ad_spend", "ad_spend", "marketing_spend")
        cac = _get_float("actual_cac", "cac")
        inventory = _get_int("actual_inventory", "inventory", "ending_inventory")
        stockouts = _get_int("actual_stockout_days", "stockout_days")

        # Logical cross-checks at adapter boundary
        if returns is not None and units is not None and returns > units:
            raise ValueError(f"{ERROR_INVALID_NUMERIC_VALUE}: returns ({returns}) cannot exceed units sold ({units}).")
        if rto is not None and units is not None and rto > units:
            raise ValueError(f"{ERROR_INVALID_NUMERIC_VALUE}: rto ({rto}) cannot exceed units sold ({units}).")

        # 6. Extract Provenance
        src_rec_id = record.get("source_record_id") or record.get("id") or record.get("fixture_id")
        src_timestamp = record.get("source_timestamp") or record.get("timestamp")
        raw_ref = record.get("raw_reference") or record.get("reference")
        notes = record.get("notes")

        return NormalizedOutcome(
            product_id=resolved_pid,
            source_product_id=str(src_pid) if src_pid is not None else None,
            decision_id=clean_dec_id,
            period_start=clean_start,
            period_end=clean_end,
            period_type=clean_type,
            data_source=str(data_src or self.source_name),
            source_schema_version=self.source_version,
            source_record_id=str(src_rec_id) if src_rec_id is not None else None,
            source_timestamp=str(src_timestamp) if src_timestamp is not None else None,
            raw_reference=str(raw_ref) if raw_ref is not None else None,
            actual_units_sold=units,
            actual_revenue=revenue,
            actual_avg_selling_price=asp,
            actual_landed_cogs=cogs,
            actual_contribution_margin=cm,
            actual_cm_pct=cm_pct,
            actual_returns_count=returns,
            actual_return_rate_pct=return_rate_pct,
            actual_rto_count=rto,
            actual_rto_rate_pct=rto_rate_pct,
            actual_ad_spend=ad_spend,
            actual_cac=cac,
            actual_inventory=inventory,
            actual_stockout_days=stockouts,
            notes=str(notes) if notes is not None else None,
        )


# Alias for explicit naming
ManualFixtureAdapter = FixtureOutcomeAdapter
