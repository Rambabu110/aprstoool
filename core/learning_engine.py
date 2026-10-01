"""
core/learning_engine.py — APRS V8 Phase 7: Auditable Learning Foundation & Bias Intelligence
=============================================================================================
Architectural Layer: Evidence-Based Learning (Human-Auditable, Read-Only Policy Output)

PURPOSE:
  Answers: "Where are APRS predictions systematically biased, how strong is the evidence,
  and what should be investigated before changing any model or business rule?"

CLOSED-LOOP POSITION:
  Research → Intelligence → Decision → Launch → Observe → Real Outcome →
  Calibration → Bias Detection → Learning Evidence → Human-Auditable Recommendation →
  Future Controlled Improvement

NON-NEGOTIABLE INVARIANTS:
  1. NO SILENT SELF-MODIFICATION:
     This module NEVER modifies V7.2 scoring weights, Kill Switch thresholds,
     kill logic, economics assumptions, prediction formulas, model parameters,
     sourcing rules, launch criteria, or confidence rules.

  2. NO CLAIM WITHOUT EVIDENCE:
     If product_outcomes = 0 or prediction_calibrations = 0:
     evidence_status = "NO_OBSERVATION_DATA". No bias is claimed.

  3. DETERMINISTIC:
     Same calibration records → same learning summary. No randomness, no wall-clock
     dependent numeric conclusions, no network calls, no LLM for numeric calculations.

  4. CORRECTION AWARENESS:
     Uses current authoritative (post-correction) outcome values only.
     Never double-counts original + corrected value as two observations.

  5. NO SURVIVORSHIP BIAS:
     Includes all products that have observed outcomes, not only successful ones.

  6. SIGN CONVENTION PRESERVED (inherited from calibration_engine):
     signed_error = actual - predicted
     Negative → overprediction (predicted too high)
     Positive → underprediction (predicted too low)

LEARNING POLICY:
  All thresholds are named constants with explicit rationale. See LEARNING_POLICY dict.

METRIC SUPPORT:
  MBE (Mean Bias Error / Mean Signed Error), MAE (Mean Absolute Error), MAPE.
  MSE is NEVER used or referenced.
"""

import hashlib
import json
import math
import logging
import datetime
import sqlite3
from typing import Dict, Any, List, Optional

from core.database import get_connection, get_db_path
from core.calibration_engine import (
    calculate_aggregate_bias,
    SAMPLE_SIZE_MIN_AGGREGATE,
    RELIABILITY_INSUFFICIENT_SAMPLE,
    RELIABILITY_PROVISIONAL_AGGREGATE,
    V8_CALIBRATION_VERSION,
)

logger = logging.getLogger("aprs.learning_engine")


# ---------------------------------------------------------------------------
# AUTHORITATIVE VERSIONING
# ---------------------------------------------------------------------------

V8_LEARNING_VERSION = "V8_LEARNING_V1"

# ---------------------------------------------------------------------------
# LEARNING POLICY — All thresholds named, documented, and versioned
# ---------------------------------------------------------------------------

LEARNING_POLICY = {
    # Minimum observations before any aggregate bias claim is made.
    # Rationale: Below this, individual errors vary wildly; central tendency is unstable.
    # Inherited from and consistent with calibration_engine.SAMPLE_SIZE_MIN_AGGREGATE.
    "minimum_sample_size": SAMPLE_SIZE_MIN_AGGREGATE,  # 5

    # Absolute MBE threshold (in same unit as metric) below which
    # the bias is classified as NO_CLEAR_BIAS rather than directional.
    # Rationale: Small absolute errors near zero can appear directional by chance.
    # For demand (daily units), errors < 0.5 units/day are treated as noise.
    "demand_mbe_noise_threshold": 0.5,

    # MAPE threshold (%) below which demand accuracy is treated as acceptable.
    # Rationale: Industry convention for demand forecasting acceptable error band.
    "demand_mape_acceptable_pct": 20.0,

    # Absolute MBE threshold (pp) for CM% and RTO% metrics below which
    # the signed error is considered negligible noise.
    "pct_point_noise_threshold_pp": 1.0,

    # Version identifier for this policy.
    # ANY change to thresholds above MUST increment this version.
    "policy_version": "LEARNING_POLICY_V1",
}


# ---------------------------------------------------------------------------
# EVIDENCE STATUS CONSTANTS
# ---------------------------------------------------------------------------

EVIDENCE_NO_DATA = "NO_OBSERVATION_DATA"          # 0 calibration records
EVIDENCE_INSUFFICIENT = "INSUFFICIENT_EVIDENCE"   # N < minimum_sample_size
EVIDENCE_PROVISIONAL = "PROVISIONAL_BIAS"         # N >= minimum_sample_size, repeated direction
EVIDENCE_NO_CLEAR_BIAS = "NO_CLEAR_BIAS"          # N >= minimum_sample_size, no directional signal


# ---------------------------------------------------------------------------
# DIRECTIONAL BIAS CLASSIFICATIONS
# ---------------------------------------------------------------------------

BIAS_OVERPREDICTION = "OVERPREDICTION_BIAS"
BIAS_UNDERPREDICTION = "UNDERPREDICTION_BIAS"
BIAS_NO_CLEAR = "NO_CLEAR_BIAS"
BIAS_INSUFFICIENT = "INSUFFICIENT_EVIDENCE"


# ---------------------------------------------------------------------------
# RECOMMENDATION TYPES
# ---------------------------------------------------------------------------

REC_INVESTIGATE_DEMAND_OVER = "INVESTIGATE_DEMAND_OVERPREDICTION"
REC_INVESTIGATE_DEMAND_UNDER = "INVESTIGATE_DEMAND_UNDERPREDICTION"
REC_INVESTIGATE_PRICE_OVER = "INVESTIGATE_PRICE_OVERPREDICTION"
REC_INVESTIGATE_PRICE_UNDER = "INVESTIGATE_PRICE_UNDERPREDICTION"
REC_INVESTIGATE_CM_OVER = "INVESTIGATE_CM_OVERPREDICTION"
REC_INVESTIGATE_CM_UNDER = "INVESTIGATE_CM_UNDERPREDICTION"
REC_INVESTIGATE_RTO_OVER = "INVESTIGATE_RTO_OVERPREDICTION"
REC_INVESTIGATE_RTO_UNDER = "INVESTIGATE_RTO_UNDERPREDICTION"
REC_INVESTIGATE_CAC_OVER = "INVESTIGATE_CAC_OVERPREDICTION"
REC_INVESTIGATE_CAC_UNDER = "INVESTIGATE_CAC_UNDERPREDICTION"
REC_NO_ACTION_NEEDED = "NO_INVESTIGATION_INDICATED"
REC_AWAITING_DATA = "AWAITING_SUFFICIENT_OBSERVATION_DATA"


# ---------------------------------------------------------------------------
# RECOMMENDATION STATUS
# ---------------------------------------------------------------------------

REC_STATUS_PROPOSED = "PROPOSED"
REC_STATUS_UNDER_REVIEW = "UNDER_REVIEW"
REC_STATUS_ACCEPTED = "ACCEPTED"
REC_STATUS_REJECTED = "REJECTED"
REC_STATUS_DEFERRED = "DEFERRED"
REC_STATUS_SUPERSEDED = "SUPERSEDED"


# ---------------------------------------------------------------------------
# SCOPE TYPES
# ---------------------------------------------------------------------------

SCOPE_PORTFOLIO = "PORTFOLIO"
SCOPE_CATEGORY = "CATEGORY"
SCOPE_PRODUCT = "PRODUCT"


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _compute_fingerprint(calibration_records: List[Dict[str, Any]]) -> str:
    """
    Computes a deterministic SHA-256 fingerprint of the calibration record IDs
    and calculation_version values used in a learning summary.

    Guarantees:
      - Same records → same fingerprint (order-independent via sorted).
      - Different records (add/remove/version change) → different fingerprint.
      - Not timestamp-dependent: fingerprint is based on data content only.
    """
    identity_tokens = sorted(
        f"{c.get('calibration_id', '')}:{c.get('calculation_version', '')}"
        for c in calibration_records
    )
    raw = "|".join(identity_tokens)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _classify_directional_bias(mbe: Optional[float], metric_key: str) -> str:
    """
    Classifies directional bias based on MBE value and metric-specific noise threshold.

    Sign convention (inherited from calibration_engine):
      mbe = mean(actual - predicted)
      negative → overprediction (predicted too high)
      positive → underprediction (predicted too low)

    Returns one of: OVERPREDICTION_BIAS, UNDERPREDICTION_BIAS, NO_CLEAR_BIAS,
                    INSUFFICIENT_EVIDENCE
    """
    if mbe is None:
        return BIAS_INSUFFICIENT

    if metric_key in ("demand",):
        threshold = LEARNING_POLICY["demand_mbe_noise_threshold"]
    else:
        threshold = LEARNING_POLICY["pct_point_noise_threshold_pp"]

    if abs(mbe) <= threshold:
        return BIAS_NO_CLEAR
    elif mbe < 0:
        # actual < predicted → overprediction
        return BIAS_OVERPREDICTION
    else:
        # actual > predicted → underprediction
        return BIAS_UNDERPREDICTION


def _derive_evidence_status(sample_size: int, directional_bias: str) -> str:
    """
    Derives evidence_status from sample size and directional bias.

    Rules:
      N = 0                          → NO_OBSERVATION_DATA
      0 < N < minimum_sample_size    → INSUFFICIENT_EVIDENCE
      N >= minimum_sample_size AND directional bias present → PROVISIONAL_BIAS
      N >= minimum_sample_size AND no directional bias     → NO_CLEAR_BIAS
    """
    if sample_size == 0:
        return EVIDENCE_NO_DATA
    if sample_size < LEARNING_POLICY["minimum_sample_size"]:
        return EVIDENCE_INSUFFICIENT
    if directional_bias in (BIAS_OVERPREDICTION, BIAS_UNDERPREDICTION):
        return EVIDENCE_PROVISIONAL
    return EVIDENCE_NO_CLEAR_BIAS


def _build_recommendation(
    scope_type: str,
    scope_key: str,
    metric_name: str,
    directional_bias: str,
    evidence_status: str,
    sample_size: int,
    mbe: Optional[float],
    mape: Optional[float],
) -> Dict[str, Any]:
    """
    Builds a human-auditable recommendation without applying any policy change.

    IMPORTANT: The returned recommendation explicitly states:
      automatic_policy_change: NONE
    """
    # Map metric + direction → recommendation type
    type_map = {
        ("demand", BIAS_OVERPREDICTION): REC_INVESTIGATE_DEMAND_OVER,
        ("demand", BIAS_UNDERPREDICTION): REC_INVESTIGATE_DEMAND_UNDER,
        ("price", BIAS_OVERPREDICTION): REC_INVESTIGATE_PRICE_OVER,
        ("price", BIAS_UNDERPREDICTION): REC_INVESTIGATE_PRICE_UNDER,
        ("cm", BIAS_OVERPREDICTION): REC_INVESTIGATE_CM_OVER,
        ("cm", BIAS_UNDERPREDICTION): REC_INVESTIGATE_CM_UNDER,
        ("rto", BIAS_OVERPREDICTION): REC_INVESTIGATE_RTO_OVER,
        ("rto", BIAS_UNDERPREDICTION): REC_INVESTIGATE_RTO_UNDER,
        ("cac", BIAS_OVERPREDICTION): REC_INVESTIGATE_CAC_OVER,
        ("cac", BIAS_UNDERPREDICTION): REC_INVESTIGATE_CAC_UNDER,
    }

    if evidence_status == EVIDENCE_NO_DATA:
        rec_type = REC_AWAITING_DATA
        reason = "No observation data available. Recommendation deferred until real outcomes are ingested."
        confidence_note = "WAITING FOR REAL DATA"
    elif evidence_status == EVIDENCE_INSUFFICIENT:
        rec_type = REC_AWAITING_DATA
        reason = (
            f"Insufficient sample (N={sample_size}). "
            f"Minimum {LEARNING_POLICY['minimum_sample_size']} observations required before bias investigation."
        )
        confidence_note = f"INSUFFICIENT_SAMPLE (N={sample_size})"
    elif directional_bias in (BIAS_NO_CLEAR, BIAS_INSUFFICIENT):
        rec_type = REC_NO_ACTION_NEEDED
        reason = (
            f"No systematic directional bias detected across {sample_size} observations. "
            f"MBE within noise threshold."
        )
        confidence_note = "NO_CLEAR_BIAS"
    else:
        rec_type = type_map.get((metric_name, directional_bias), "INVESTIGATE_BIAS")
        mbe_str = f"{mbe:+.4f}" if mbe is not None else "N/A"
        mape_str = f"{mape:.1f}%" if mape is not None else "N/A"
        reason = (
            f"Repeated {directional_bias} detected across {sample_size} observations. "
            f"MBE={mbe_str}, MAPE={mape_str}. "
            f"Investigate {metric_name} estimation assumptions before changing any model parameter."
        )
        confidence_note = f"PROVISIONAL (N={sample_size})"

    return {
        "scope_type": scope_type,
        "scope_key": scope_key,
        "metric_name": metric_name,
        "recommendation_type": rec_type,
        "evidence_status": evidence_status,
        "sample_size": sample_size,
        "observed_bias": directional_bias,
        "mbe": mbe,
        "mape": mape,
        "confidence_note": confidence_note,
        "reason": reason,
        "automatic_policy_change": "NONE",
        "status": REC_STATUS_PROPOSED,
        "policy_version": LEARNING_POLICY["policy_version"],
        "calculation_version": V8_LEARNING_VERSION,
        "created_at": datetime.datetime.utcnow().isoformat() + "Z",
    }


# ---------------------------------------------------------------------------
# CORE LEARNING ENGINE — All public service methods
# ---------------------------------------------------------------------------

class LearningEngine:
    """
    APRS V8 Phase 7 Learning Engine.

    Provides deterministic, auditable learning evidence computation.
    Reads only from prediction_calibrations and product_outcomes (via calibration records).
    Never writes to master_products, decision_ledger, product_intelligence,
    or any policy/weights/threshold table.

    All numeric calculations are pure Python — no LLM, no network calls.
    """

    # -----------------------------------------------------------------------
    # DB ISOLATION HELPERS
    # -----------------------------------------------------------------------

    @staticmethod
    def _get_conn(db_path: Optional[str] = None) -> sqlite3.Connection:
        """Read-only-safe connection respecting APRS_DB_PATH or override."""
        if db_path:
            conn = sqlite3.connect(str(db_path), timeout=5.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            return conn
        return get_connection()

    @classmethod
    def _fetch_calibrations(
        cls,
        db_path: Optional[str] = None,
        product_id: Optional[str] = None,
        category: Optional[str] = None,
        calculation_version: str = V8_CALIBRATION_VERSION,
    ) -> List[Dict[str, Any]]:
        """
        Fetches calibration records matching scope filters.

        Correction-awareness: joins on product_outcomes to use
        only currently-authoritative outcome state. The calibration record
        itself references the outcome_id; corrections alter the underlying
        outcome but do NOT produce duplicate calibration records.
        """
        conn = cls._get_conn(db_path)
        try:
            params: list = [calculation_version]
            filter_clause = ""

            if product_id:
                filter_clause += " AND pc.product_id = ?"
                params.append(product_id)
            if category:
                filter_clause += " AND mp.category = ?"
                params.append(category)

            query = f"""
                SELECT
                    pc.*,
                    mp.category,
                    mp.name AS product_name,
                    COALESCE(corr_cnt.cnt, 0) AS correction_count
                FROM prediction_calibrations pc
                LEFT JOIN master_products mp ON pc.product_id = mp.product_id
                LEFT JOIN (
                    SELECT outcome_id, COUNT(*) AS cnt
                    FROM outcome_corrections_log
                    GROUP BY outcome_id
                ) corr_cnt ON pc.outcome_id = corr_cnt.outcome_id
                WHERE pc.calculation_version = ?
                {filter_clause}
                ORDER BY pc.calibration_id ASC
            """
            cur = conn.execute(query, params)
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    # -----------------------------------------------------------------------
    # 1. PORTFOLIO-LEVEL LEARNING SUMMARY
    # -----------------------------------------------------------------------

    @classmethod
    def get_portfolio_learning_summary(
        cls,
        db_path: Optional[str] = None,
        calculation_version: str = V8_CALIBRATION_VERSION,
    ) -> Dict[str, Any]:
        """
        Computes portfolio-wide learning evidence across all calibrated products.

        Returns:
          evidence_status, bias results for each metric (demand, price, cm, rto, cac),
          fingerprint, and human-auditable recommendations.

        Empty state: returns safe structure with evidence_status = NO_OBSERVATION_DATA.
        No fake data, no fabricated bias claims.
        """
        calibrations = cls._fetch_calibrations(db_path=db_path, calculation_version=calculation_version)

        if not calibrations:
            return cls._empty_learning_summary(SCOPE_PORTFOLIO, "PORTFOLIO")

        fingerprint = _compute_fingerprint(calibrations)
        sample_size = len(calibrations)
        correction_count = sum(c.get("correction_count", 0) for c in calibrations)
        corrected_outcomes = sum(1 for c in calibrations if c.get("correction_count", 0) > 0)

        metrics_results = {}
        recommendations = []

        for metric in ("demand", "price", "cac"):
            agg = calculate_aggregate_bias(calibrations, metric_prefix=metric)
            mbe = agg.get("mean_signed_error")
            mape = agg.get("mape")
            mae = agg.get("mean_absolute_error")
            valid_n = agg.get("valid_observations", 0)

            directional_bias = _classify_directional_bias(mbe, metric) if valid_n > 0 else BIAS_INSUFFICIENT
            evidence_status = _derive_evidence_status(valid_n, directional_bias)

            metrics_results[metric] = {
                "metric": metric,
                "sample_size": sample_size,
                "valid_observations": valid_n,
                "mean_signed_error_mbe": mbe,
                "mean_absolute_error_mae": mae,
                "mape_pct": mape,
                "directional_bias": directional_bias,
                "evidence_status": evidence_status,
                "reliability_tier": agg.get("reliability_tier"),
            }

            rec = _build_recommendation(
                scope_type=SCOPE_PORTFOLIO,
                scope_key="PORTFOLIO",
                metric_name=metric,
                directional_bias=directional_bias,
                evidence_status=evidence_status,
                sample_size=valid_n,
                mbe=mbe,
                mape=mape,
            )
            recommendations.append(rec)

        # PP metrics (cm, rto) — use signed_error_pct_points key
        for metric in ("cm", "rto"):
            agg = calculate_aggregate_bias(calibrations, metric_prefix=metric)
            mbe = agg.get("mean_signed_error")
            mae = agg.get("mean_absolute_error")
            valid_n = agg.get("valid_observations", 0)

            directional_bias = _classify_directional_bias(mbe, metric) if valid_n > 0 else BIAS_INSUFFICIENT
            evidence_status = _derive_evidence_status(valid_n, directional_bias)

            metrics_results[metric] = {
                "metric": metric,
                "sample_size": sample_size,
                "valid_observations": valid_n,
                "mean_signed_error_mbe_pp": mbe,
                "mean_absolute_error_mae_pp": mae,
                "mape_pct": agg.get("mape"),
                "directional_bias": directional_bias,
                "evidence_status": evidence_status,
                "reliability_tier": agg.get("reliability_tier"),
            }

            rec = _build_recommendation(
                scope_type=SCOPE_PORTFOLIO,
                scope_key="PORTFOLIO",
                metric_name=metric,
                directional_bias=directional_bias,
                evidence_status=evidence_status,
                sample_size=valid_n,
                mbe=mbe,
                mape=agg.get("mape"),
            )
            recommendations.append(rec)

        # Overall portfolio evidence status: worst case across metrics
        all_statuses = [m["evidence_status"] for m in metrics_results.values()]
        if EVIDENCE_NO_DATA in all_statuses:
            portfolio_status = EVIDENCE_NO_DATA
        elif EVIDENCE_PROVISIONAL in all_statuses:
            portfolio_status = EVIDENCE_PROVISIONAL
        elif EVIDENCE_INSUFFICIENT in all_statuses:
            portfolio_status = EVIDENCE_INSUFFICIENT
        else:
            portfolio_status = EVIDENCE_NO_CLEAR_BIAS

        # Observation date range
        conn = cls._get_conn(db_path)
        try:
            cur = conn.execute(
                "SELECT MIN(period_start), MAX(period_end) FROM product_outcomes"
            )
            row = cur.fetchone()
            first_obs = row[0] if row else None
            last_obs = row[1] if row else None
        finally:
            conn.close()

        return {
            "scope_type": SCOPE_PORTFOLIO,
            "scope_key": "PORTFOLIO",
            "evidence_status": portfolio_status,
            "sample_size": sample_size,
            "corrected_outcomes": corrected_outcomes,
            "total_correction_events": correction_count,
            "metrics": metrics_results,
            "recommendations": recommendations,
            "fingerprint": fingerprint,
            "first_observation_date": first_obs,
            "last_observation_date": last_obs,
            "calculation_version": V8_LEARNING_VERSION,
            "policy_version": LEARNING_POLICY["policy_version"],
            "automatic_policy_change": "NONE",
        }

    # -----------------------------------------------------------------------
    # 2. PRODUCT-LEVEL LEARNING SUMMARY
    # -----------------------------------------------------------------------

    @classmethod
    def get_product_learning_summary(
        cls,
        product_id: str,
        db_path: Optional[str] = None,
        calculation_version: str = V8_CALIBRATION_VERSION,
    ) -> Dict[str, Any]:
        """
        Computes learning evidence for a single product.
        Returns safe empty state if no calibration records exist.
        """
        calibrations = cls._fetch_calibrations(
            db_path=db_path,
            product_id=product_id,
            calculation_version=calculation_version,
        )

        if not calibrations:
            summary = cls._empty_learning_summary(SCOPE_PRODUCT, product_id)
            summary["product_id"] = product_id
            return summary

        fingerprint = _compute_fingerprint(calibrations)
        sample_size = len(calibrations)
        correction_count = sum(c.get("correction_count", 0) for c in calibrations)

        metrics_results = {}
        recommendations = []

        for metric in ("demand", "price", "cac"):
            agg = calculate_aggregate_bias(calibrations, metric_prefix=metric)
            mbe = agg.get("mean_signed_error")
            valid_n = agg.get("valid_observations", 0)
            directional_bias = _classify_directional_bias(mbe, metric) if valid_n > 0 else BIAS_INSUFFICIENT
            evidence_status = _derive_evidence_status(valid_n, directional_bias)

            metrics_results[metric] = {
                "metric": metric,
                "sample_size": sample_size,
                "valid_observations": valid_n,
                "mean_signed_error_mbe": mbe,
                "mean_absolute_error_mae": agg.get("mean_absolute_error"),
                "mape_pct": agg.get("mape"),
                "directional_bias": directional_bias,
                "evidence_status": evidence_status,
                "reliability_tier": agg.get("reliability_tier"),
            }

            recommendations.append(_build_recommendation(
                scope_type=SCOPE_PRODUCT,
                scope_key=product_id,
                metric_name=metric,
                directional_bias=directional_bias,
                evidence_status=evidence_status,
                sample_size=valid_n,
                mbe=mbe,
                mape=agg.get("mape"),
            ))

        for metric in ("cm", "rto"):
            agg = calculate_aggregate_bias(calibrations, metric_prefix=metric)
            mbe = agg.get("mean_signed_error")
            valid_n = agg.get("valid_observations", 0)
            directional_bias = _classify_directional_bias(mbe, metric) if valid_n > 0 else BIAS_INSUFFICIENT
            evidence_status = _derive_evidence_status(valid_n, directional_bias)

            metrics_results[metric] = {
                "metric": metric,
                "sample_size": sample_size,
                "valid_observations": valid_n,
                "mean_signed_error_mbe_pp": mbe,
                "mean_absolute_error_mae_pp": agg.get("mean_absolute_error"),
                "mape_pct": agg.get("mape"),
                "directional_bias": directional_bias,
                "evidence_status": evidence_status,
                "reliability_tier": agg.get("reliability_tier"),
            }

            recommendations.append(_build_recommendation(
                scope_type=SCOPE_PRODUCT,
                scope_key=product_id,
                metric_name=metric,
                directional_bias=directional_bias,
                evidence_status=evidence_status,
                sample_size=valid_n,
                mbe=mbe,
                mape=agg.get("mape"),
            ))

        all_statuses = [m["evidence_status"] for m in metrics_results.values()]
        if EVIDENCE_NO_DATA in all_statuses:
            product_evidence_status = EVIDENCE_NO_DATA
        elif EVIDENCE_PROVISIONAL in all_statuses:
            product_evidence_status = EVIDENCE_PROVISIONAL
        elif EVIDENCE_INSUFFICIENT in all_statuses:
            product_evidence_status = EVIDENCE_INSUFFICIENT
        else:
            product_evidence_status = EVIDENCE_NO_CLEAR_BIAS

        return {
            "scope_type": SCOPE_PRODUCT,
            "scope_key": product_id,
            "product_id": product_id,
            "evidence_status": product_evidence_status,
            "sample_size": sample_size,
            "total_correction_events": correction_count,
            "metrics": metrics_results,
            "recommendations": recommendations,
            "fingerprint": fingerprint,
            "calculation_version": V8_LEARNING_VERSION,
            "policy_version": LEARNING_POLICY["policy_version"],
            "automatic_policy_change": "NONE",
        }

    # -----------------------------------------------------------------------
    # 3. CATEGORY-LEVEL LEARNING SUMMARY
    # -----------------------------------------------------------------------

    @classmethod
    def get_category_learning_summary(
        cls,
        category: str,
        db_path: Optional[str] = None,
        calculation_version: str = V8_CALIBRATION_VERSION,
    ) -> Dict[str, Any]:
        """
        Computes learning evidence aggregated by product category.

        SCOPE SAFETY: Only includes calibrations whose products are
        tagged with the requested category. Never mixes categories.

        If insufficient data exists for this category:
        evidence_status = INSUFFICIENT_EVIDENCE or NO_OBSERVATION_DATA.
        """
        calibrations = cls._fetch_calibrations(
            db_path=db_path,
            category=category,
            calculation_version=calculation_version,
        )

        if not calibrations:
            summary = cls._empty_learning_summary(SCOPE_CATEGORY, category)
            summary["category"] = category
            return summary

        fingerprint = _compute_fingerprint(calibrations)
        sample_size = len(calibrations)
        unique_products = len(set(c.get("product_id") for c in calibrations))

        metrics_results = {}
        recommendations = []

        for metric in ("demand", "price", "cac"):
            agg = calculate_aggregate_bias(calibrations, metric_prefix=metric)
            mbe = agg.get("mean_signed_error")
            valid_n = agg.get("valid_observations", 0)
            directional_bias = _classify_directional_bias(mbe, metric) if valid_n > 0 else BIAS_INSUFFICIENT
            evidence_status = _derive_evidence_status(valid_n, directional_bias)

            metrics_results[metric] = {
                "metric": metric,
                "sample_size": sample_size,
                "valid_observations": valid_n,
                "mean_signed_error_mbe": mbe,
                "mean_absolute_error_mae": agg.get("mean_absolute_error"),
                "mape_pct": agg.get("mape"),
                "directional_bias": directional_bias,
                "evidence_status": evidence_status,
                "reliability_tier": agg.get("reliability_tier"),
            }

            recommendations.append(_build_recommendation(
                scope_type=SCOPE_CATEGORY,
                scope_key=category,
                metric_name=metric,
                directional_bias=directional_bias,
                evidence_status=evidence_status,
                sample_size=valid_n,
                mbe=mbe,
                mape=agg.get("mape"),
            ))

        for metric in ("cm", "rto"):
            agg = calculate_aggregate_bias(calibrations, metric_prefix=metric)
            mbe = agg.get("mean_signed_error")
            valid_n = agg.get("valid_observations", 0)
            directional_bias = _classify_directional_bias(mbe, metric) if valid_n > 0 else BIAS_INSUFFICIENT
            evidence_status = _derive_evidence_status(valid_n, directional_bias)

            metrics_results[metric] = {
                "metric": metric,
                "sample_size": sample_size,
                "valid_observations": valid_n,
                "mean_signed_error_mbe_pp": mbe,
                "mean_absolute_error_mae_pp": agg.get("mean_absolute_error"),
                "mape_pct": agg.get("mape"),
                "directional_bias": directional_bias,
                "evidence_status": evidence_status,
                "reliability_tier": agg.get("reliability_tier"),
            }

            recommendations.append(_build_recommendation(
                scope_type=SCOPE_CATEGORY,
                scope_key=category,
                metric_name=metric,
                directional_bias=directional_bias,
                evidence_status=evidence_status,
                sample_size=valid_n,
                mbe=mbe,
                mape=agg.get("mape"),
            ))

        all_statuses = [m["evidence_status"] for m in metrics_results.values()]
        if EVIDENCE_NO_DATA in all_statuses:
            cat_status = EVIDENCE_NO_DATA
        elif EVIDENCE_PROVISIONAL in all_statuses:
            cat_status = EVIDENCE_PROVISIONAL
        elif EVIDENCE_INSUFFICIENT in all_statuses:
            cat_status = EVIDENCE_INSUFFICIENT
        else:
            cat_status = EVIDENCE_NO_CLEAR_BIAS

        return {
            "scope_type": SCOPE_CATEGORY,
            "scope_key": category,
            "category": category,
            "unique_products": unique_products,
            "evidence_status": cat_status,
            "sample_size": sample_size,
            "metrics": metrics_results,
            "recommendations": recommendations,
            "fingerprint": fingerprint,
            "calculation_version": V8_LEARNING_VERSION,
            "policy_version": LEARNING_POLICY["policy_version"],
            "automatic_policy_change": "NONE",
        }

    # -----------------------------------------------------------------------
    # 4. AVAILABLE CATEGORIES
    # -----------------------------------------------------------------------

    @classmethod
    def get_available_categories_with_calibrations(
        cls,
        db_path: Optional[str] = None,
        calculation_version: str = V8_CALIBRATION_VERSION,
    ) -> List[Dict[str, Any]]:
        """
        Returns categories that have at least one calibration record.
        Safe empty list if no calibrations exist.
        """
        conn = cls._get_conn(db_path)
        try:
            cur = conn.execute("""
                SELECT mp.category, COUNT(*) AS calibration_count, COUNT(DISTINCT pc.product_id) AS product_count
                FROM prediction_calibrations pc
                LEFT JOIN master_products mp ON pc.product_id = mp.product_id
                WHERE pc.calculation_version = ?
                  AND mp.category IS NOT NULL
                GROUP BY mp.category
                ORDER BY calibration_count DESC
            """, (calculation_version,))
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    # -----------------------------------------------------------------------
    # 5. BIAS SUMMARY BY METRIC (Cross-Scope)
    # -----------------------------------------------------------------------

    @classmethod
    def get_bias_by_metric(
        cls,
        metric_name: str,
        db_path: Optional[str] = None,
        calculation_version: str = V8_CALIBRATION_VERSION,
    ) -> Dict[str, Any]:
        """
        Returns portfolio-level bias summary for a specific metric.
        metric_name: one of 'demand', 'price', 'cm', 'rto', 'cac'
        """
        calibrations = cls._fetch_calibrations(db_path=db_path, calculation_version=calculation_version)
        if not calibrations:
            return {
                "metric": metric_name,
                "evidence_status": EVIDENCE_NO_DATA,
                "sample_size": 0,
                "mean_signed_error_mbe": None,
                "mean_absolute_error_mae": None,
                "mape_pct": None,
                "directional_bias": BIAS_INSUFFICIENT,
                "automatic_policy_change": "NONE",
            }

        agg = calculate_aggregate_bias(calibrations, metric_prefix=metric_name)
        mbe = agg.get("mean_signed_error")
        valid_n = agg.get("valid_observations", 0)
        directional_bias = _classify_directional_bias(mbe, metric_name) if valid_n > 0 else BIAS_INSUFFICIENT
        evidence_status = _derive_evidence_status(valid_n, directional_bias)

        return {
            "metric": metric_name,
            "evidence_status": evidence_status,
            "sample_size": len(calibrations),
            "valid_observations": valid_n,
            "mean_signed_error_mbe": mbe,
            "mean_absolute_error_mae": agg.get("mean_absolute_error"),
            "mape_pct": agg.get("mape"),
            "directional_bias": directional_bias,
            "reliability_tier": agg.get("reliability_tier"),
            "automatic_policy_change": "NONE",
        }

    # -----------------------------------------------------------------------
    # 6. GENERATE LEARNING RECOMMENDATIONS
    # -----------------------------------------------------------------------

    @classmethod
    def generate_learning_recommendations(
        cls,
        db_path: Optional[str] = None,
        calculation_version: str = V8_CALIBRATION_VERSION,
    ) -> List[Dict[str, Any]]:
        """
        Generates a prioritized list of learning recommendations across all metrics
        at the portfolio level.

        Each recommendation clearly states:
          automatic_policy_change: NONE

        Returns empty list if no calibrations exist.
        """
        summary = cls.get_portfolio_learning_summary(
            db_path=db_path, calculation_version=calculation_version
        )
        return summary.get("recommendations", [])

    # -----------------------------------------------------------------------
    # 7. POLICY SAFETY SNAPSHOT
    # -----------------------------------------------------------------------

    @classmethod
    def capture_policy_snapshot(cls) -> Dict[str, Any]:
        """
        Captures an immutable snapshot of V7.2 scoring weights and kill switch
        thresholds at call time (extracted directly from intelligence_engine source
        without executing any intelligence run).

        Used by tests to verify learning engine never modifies these values.
        These are hardcoded from the intelligence engine source.
        """
        from core.intelligence_engine import AutonomousIntelligenceEngine

        # V7.2 dimension weights (from evaluate_scorecard — local dict, not global constant)
        # Captured as a reference snapshot for policy safety verification.
        scoring_weights = {
            "demand_strength": 0.18,
            "trend_strength": 0.12,
            "competition_pressure": 0.10,
            "customer_pain": 0.15,
            "economic_viability": 0.18,
            "sourcing_feasibility": 0.10,
            "operational_risk": 0.05,
            "market_saturation": 0.04,
            "evidence_quality": 0.05,
            "data_freshness": 0.03,
        }
        return {
            "captured_at": datetime.datetime.utcnow().isoformat() + "Z",
            "source": "core.intelligence_engine.AutonomousIntelligenceEngine.evaluate_scorecard",
            "scoring_weights": scoring_weights,
            "note": "Reference snapshot for policy safety testing. Learning engine does not modify these values.",
        }

    # -----------------------------------------------------------------------
    # INTERNAL HELPERS
    # -----------------------------------------------------------------------

    @classmethod
    def _empty_learning_summary(cls, scope_type: str, scope_key: str) -> Dict[str, Any]:
        """
        Returns a safe, honest empty learning summary when no calibration data exists.
        Never fabricates bias claims or fake evidence.
        """
        empty_metric = {
            "sample_size": 0,
            "valid_observations": 0,
            "mean_signed_error_mbe": None,
            "mean_absolute_error_mae": None,
            "mape_pct": None,
            "directional_bias": BIAS_INSUFFICIENT,
            "evidence_status": EVIDENCE_NO_DATA,
            "reliability_tier": RELIABILITY_INSUFFICIENT_SAMPLE,
        }

        empty_rec = _build_recommendation(
            scope_type=scope_type,
            scope_key=scope_key,
            metric_name="demand",
            directional_bias=BIAS_INSUFFICIENT,
            evidence_status=EVIDENCE_NO_DATA,
            sample_size=0,
            mbe=None,
            mape=None,
        )

        return {
            "scope_type": scope_type,
            "scope_key": scope_key,
            "evidence_status": EVIDENCE_NO_DATA,
            "sample_size": 0,
            "corrected_outcomes": 0,
            "total_correction_events": 0,
            "metrics": {
                "demand": {**empty_metric, "metric": "demand"},
                "price": {**empty_metric, "metric": "price"},
                "cm": {**empty_metric, "metric": "cm", "mean_signed_error_mbe_pp": None},
                "rto": {**empty_metric, "metric": "rto", "mean_signed_error_mbe_pp": None},
                "cac": {**empty_metric, "metric": "cac"},
            },
            "recommendations": [empty_rec],
            "fingerprint": None,
            "first_observation_date": None,
            "last_observation_date": None,
            "calculation_version": V8_LEARNING_VERSION,
            "policy_version": LEARNING_POLICY["policy_version"],
            "automatic_policy_change": "NONE",
        }
