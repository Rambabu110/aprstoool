"""
APRS V8 PHASE 4B: OUTCOME NORMALIZATION SERVICE & VALIDATION HELPERS
====================================================================
Architectural Layer: Normalization Service
Purpose:
  Provides deterministic validation, product resolution, period validation,
  and numeric/NULL cleaning routines shared across outcome adapters.
"""

import datetime
from typing import Dict, Any, Optional, Callable, Tuple

from core.database import get_connection
from core.outcome_adapters.base import (
    ERROR_INVALID_SOURCE_RECORD,
    ERROR_MISSING_PRODUCT_ID,
    ERROR_UNRESOLVED_PRODUCT,
    ERROR_INVALID_PERIOD,
    ERROR_UNSUPPORTED_PERIOD_TYPE,
    ERROR_INVALID_NUMERIC_VALUE,
    ERROR_INVALID_PERCENTAGE,
    ERROR_RESEARCH_ESTIMATE_NOT_OUTCOME,
    FORBIDDEN_RESEARCH_PROXIES,
    FORBIDDEN_ESTIMATE_FIELDS,
    SUPPORTED_PERIOD_TYPES,
)


def check_aprs_product_exists(product_id: str, conn=None) -> bool:
    """
    Checks if a product_id exists in APRS master_products.
    Returns False if nonexistent or on lookup failure.
    """
    if not product_id or not isinstance(product_id, str):
        return False

    close_at_end = False
    if conn is None:
        try:
            conn = get_connection()
            close_at_end = True
        except Exception:
            return False

    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM master_products WHERE product_id = ?", (product_id.strip(),))
        row = cur.fetchone()
        return row is not None
    except Exception:
        return False
    finally:
        if close_at_end and conn:
            conn.close()


def check_research_proxy_rejection(data_source: str, record: Dict[str, Any]) -> None:
    """
    Enforces the strict boundary between actual seller outcomes and scraped/research estimates.
    Raises ValueError if data_source is a forbidden research proxy or if estimate fields
    are passed in place of actuals.
    """
    src_clean = str(data_source or "").strip().upper()
    if src_clean in FORBIDDEN_RESEARCH_PROXIES:
        raise ValueError(
            f"{ERROR_RESEARCH_ESTIMATE_NOT_OUTCOME}: Data source '{data_source}' represents "
            "pre-launch research/scraped estimates, not observed seller business outcomes."
        )

    for field_name in FORBIDDEN_ESTIMATE_FIELDS:
        if field_name in record and record[field_name] is not None:
            raise ValueError(
                f"{ERROR_RESEARCH_ESTIMATE_NOT_OUTCOME}: Found research proxy field '{field_name}' in record. "
                "Research estimates cannot be converted to actual post-launch outcomes."
            )


def resolve_product_identity(
    raw_product_id: Optional[str] = None,
    source_product_id: Optional[str] = None,
    product_resolver: Optional[Callable[[str], Optional[str]]] = None,
    db_conn=None,
) -> str:
    """
    Deterministically resolves a product identifier to a verified APRS product_id.
    
    Rules:
      1. Never guess or fuzzy match.
      2. If neither identifier is provided -> MISSING_PRODUCT_ID.
      3. If product_resolver is provided, it is invoked to map source_product_id -> aprs_product_id.
      4. If resolved ID does not exist in master_products -> UNRESOLVED_PRODUCT.
      5. Never auto-create a master product record.
    """
    candidate_id = raw_product_id or source_product_id
    if not candidate_id or not isinstance(candidate_id, str) or not candidate_id.strip():
        raise ValueError(f"{ERROR_MISSING_PRODUCT_ID}: Missing product identifier in source record.")

    clean_candidate = candidate_id.strip()

    # Step 1: Use external resolver function if supplied
    if product_resolver is not None:
        try:
            resolved = product_resolver(clean_candidate)
        except Exception as e:
            raise ValueError(
                f"{ERROR_UNRESOLVED_PRODUCT}: Resolver error for '{clean_candidate}': {e}"
            )
        if not resolved:
            raise ValueError(
                f"{ERROR_UNRESOLVED_PRODUCT}: Product '{clean_candidate}' could not be resolved to an APRS product."
            )
        clean_candidate = str(resolved).strip()

    # Step 2: Verify candidate exists in master_products unless product_resolver explicitly passed
    # If db_conn is provided or default DB is accessible, check existence
    if db_conn is not None or product_resolver is None:
        exists = check_aprs_product_exists(clean_candidate, conn=db_conn)
        if not exists:
            raise ValueError(
                f"{ERROR_UNRESOLVED_PRODUCT}: Product '{clean_candidate}' does not exist in APRS catalog."
            )

    return clean_candidate


def validate_and_normalize_period(
    period_start: Any,
    period_end: Any,
    period_type: Any = "DAY_30"
) -> Tuple[str, str, str]:
    """
    Validates calendar period boundaries conforming to Phase 3 & Phase 4A inclusive semantics.
    Returns: (period_start_iso, period_end_iso, period_type)
    """
    if not period_start or not period_end:
        raise ValueError(f"{ERROR_INVALID_PERIOD}: Both period_start and period_end are required.")

    try:
        d_start = datetime.date.fromisoformat(str(period_start).split("T")[0].split(" ")[0])
        d_end = datetime.date.fromisoformat(str(period_end).split("T")[0].split(" ")[0])
    except (ValueError, TypeError) as e:
        raise ValueError(f"{ERROR_INVALID_PERIOD}: Invalid date format (expected YYYY-MM-DD): {e}")

    if d_end < d_start:
        raise ValueError(
            f"{ERROR_INVALID_PERIOD}: period_end ({period_end}) cannot be before period_start ({period_start})."
        )

    clean_p_type = str(period_type or "DAY_30").strip().upper()
    if clean_p_type not in SUPPORTED_PERIOD_TYPES:
        raise ValueError(
            f"{ERROR_UNSUPPORTED_PERIOD_TYPE}: Unsupported period_type '{period_type}'. "
            f"Must be one of: {sorted(list(SUPPORTED_PERIOD_TYPES))}"
        )

    return d_start.isoformat(), d_end.isoformat(), clean_p_type


def clean_non_negative_int(val: Any, field_name: str) -> Optional[int]:
    """Preserves None; validates non-negative integer."""
    if val is None or val == "":
        return None
    try:
        val_int = int(val)
    except (ValueError, TypeError):
        raise ValueError(f"{ERROR_INVALID_NUMERIC_VALUE}: Field '{field_name}' must be an integer, got '{val}'.")
    if val_int < 0:
        raise ValueError(f"{ERROR_INVALID_NUMERIC_VALUE}: Field '{field_name}' cannot be negative ({val_int}).")
    return val_int


def clean_non_negative_float(val: Any, field_name: str) -> Optional[float]:
    """Preserves None; validates non-negative float."""
    if val is None or val == "":
        return None
    try:
        val_flt = float(val)
    except (ValueError, TypeError):
        raise ValueError(f"{ERROR_INVALID_NUMERIC_VALUE}: Field '{field_name}' must be a number, got '{val}'.")
    if val_flt < 0.0:
        raise ValueError(f"{ERROR_INVALID_NUMERIC_VALUE}: Field '{field_name}' cannot be negative ({val_flt}).")
    return val_flt


def clean_percentage(val: Any, field_name: str) -> Optional[float]:
    """Preserves None; validates percentage between 0.0% and 100.0%."""
    if val is None or val == "":
        return None
    try:
        val_flt = float(val)
    except (ValueError, TypeError):
        raise ValueError(f"{ERROR_INVALID_PERCENTAGE}: Field '{field_name}' must be a numeric percentage, got '{val}'.")
    if val_flt < 0.0 or val_flt > 100.0:
        raise ValueError(
            f"{ERROR_INVALID_PERCENTAGE}: Field '{field_name}' must be between 0.0% and 100.0% ({val_flt}%)."
        )
    return val_flt
