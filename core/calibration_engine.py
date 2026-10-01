"""
APRS V8 PHASE 2: PREDICTION CALIBRATION & ERROR ENGINE
======================================================
Architectural Layer: Calibration & Observational Mathematics
Purpose:
  Compares frozen historical predictions from `decision_ledger`
  against real-world observations from `product_outcomes`.
  Calculates deterministic, auditable prediction errors safely
  preserving NULL and zero semantics.

Non-Negotiable Invariants:
  1. Authoritative Snapshot: Frozen predictions in `decision_ledger` are NEVER
     recalculated or altered.
  2. Pure Mathematical Layer: Error functions are deterministic, safe against
     division by zero, and maintain NULL-propagation semantics.
  3. No Self-Learning: This module is strictly analytical; it contains zero
     autonomous policy modification, score-weight adjustment, or threshold changes.
  4. Temporal Integrity: An outcome cannot be matched to a decision that was
     recorded after the outcome observation period began.
  5. Sample-Size Safeguards: No product or category is deemed reliable or biased
     without meeting the minimum sample-size threshold (N >= 5).
"""

import json
import math
import datetime
from typing import Dict, Any, List, Optional, Tuple, Union

from core.database import (
    get_connection,
    get_decision_snapshot,
    get_outcome_by_id,
    save_prediction_calibration,
    get_calibration_by_id,
    get_calibrations_for_product,
    get_all_calibrations
)

# -------------------------------------------------------------
# 1. AUTHORITATIVE CONSTANTS & VERSIONING
# -------------------------------------------------------------

V8_CALIBRATION_VERSION = "V8_CALIBRATION_V1"

# Directional Accuracy Classifications
DIRECTION_UNDERPREDICTED = "UNDERPREDICTED"
DIRECTION_OVERPREDICTED = "OVERPREDICTED"
DIRECTION_EXACT = "EXACT"
DIRECTION_UNKNOWN = "UNKNOWN"

# Calibration Statuses
STATUS_CALIBRATED = "CALIBRATED"
STATUS_PARTIAL_DATA = "PARTIAL_DATA"
STATUS_INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
STATUS_NO_MATCHING_DECISION = "NO_MATCHING_DECISION"
STATUS_NO_UNAMBIGUOUS_DECISION = "NO_UNAMBIGUOUS_DECISION"
STATUS_TEMPORAL_MISMATCH = "TEMPORAL_MISMATCH"
STATUS_INVALID_INPUT = "INVALID_INPUT"
STATUS_NOT_CALCULABLE = "NOT_CALCULABLE"

# Sample-Size Reliability Tiers
SAMPLE_SIZE_MIN_AGGREGATE = 5
RELIABILITY_INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
RELIABILITY_PROVISIONAL_AGGREGATE = "PROVISIONAL_AGGREGATE"


# -------------------------------------------------------------
# 2. PURE DETERMINISTIC MATHEMATICAL ERROR FUNCTIONS
# -------------------------------------------------------------

def calculate_signed_error(
    actual: Optional[Union[int, float]],
    predicted: Optional[Union[int, float]]
) -> Optional[float]:
    """
    Calculates signed prediction error: actual - predicted.
    Convention:
      - Negative value (< 0): Overprediction (APRS predicted higher than actual).
      - Positive value (> 0): Underprediction (APRS predicted lower than actual).
      - Zero (== 0): Exact prediction.
      - If either value is None: returns None (NULL preservation).
    """
    if actual is None or predicted is None:
        return None
    return round(float(actual) - float(predicted), 4)


def calculate_absolute_error(
    actual: Optional[Union[int, float]],
    predicted: Optional[Union[int, float]]
) -> Optional[float]:
    """
    Calculates absolute prediction error: abs(actual - predicted).
    - If either value is None: returns None.
    """
    if actual is None or predicted is None:
        return None
    return round(abs(float(actual) - float(predicted)), 4)


def calculate_percentage_error(
    actual: Optional[Union[int, float]],
    predicted: Optional[Union[int, float]]
) -> Optional[float]:
    """
    Calculates percentage error relative to prediction magnitude:
      ((actual - predicted) / abs(predicted)) * 100.0

    Critical Zero & NULL Safety:
      1. If actual is None or predicted is None: returns None.
      2. If predicted == 0: returns None (Zero-Prediction Safety: avoids division by zero;
         does NOT fabricate an arbitrary percentage).
      3. If actual == 0 and predicted > 0: returns -100.0% (Valid zero-actual observation).
    """
    if actual is None or predicted is None:
        return None
    pred_val = float(predicted)
    act_val = float(actual)
    if math.isclose(pred_val, 0.0, abs_tol=1e-9):
        # Zero-prediction safety: denominator is 0 -> percentage error undefined
        return None
    pct_err = ((act_val - pred_val) / abs(pred_val)) * 100.0
    return round(pct_err, 2)


def calculate_percentage_point_error(
    actual_pct: Optional[Union[int, float]],
    predicted_pct: Optional[Union[int, float]]
) -> Tuple[Optional[float], Optional[float]]:
    """
    Calculates percentage-point error for metrics expressed in % (e.g. CM%, RTO%):
      Signed error: actual_pct - predicted_pct
      Absolute error: abs(actual_pct - predicted_pct)
    Units: Percentage points (not relative percentage).
    If either value is None: returns (None, None).
    """
    if actual_pct is None or predicted_pct is None:
        return (None, None)
    signed_pp = round(float(actual_pct) - float(predicted_pct), 2)
    abs_pp = round(abs(float(actual_pct) - float(predicted_pct)), 2)
    return (signed_pp, abs_pp)


def classify_prediction_direction(
    actual: Optional[Union[int, float]],
    predicted: Optional[Union[int, float]]
) -> str:
    """
    Deterministic directional classification comparing actual vs predicted:
      - actual > predicted: UNDERPREDICTED
      - actual < predicted: OVERPREDICTED
      - actual == predicted: EXACT
      - either is None: UNKNOWN
    """
    if actual is None or predicted is None:
        return DIRECTION_UNKNOWN
    act_val = float(actual)
    pred_val = float(predicted)
    if math.isclose(act_val, pred_val, abs_tol=1e-9):
        return DIRECTION_EXACT
    elif act_val > pred_val:
        return DIRECTION_UNDERPREDICTED
    else:
        return DIRECTION_OVERPREDICTED


def calculate_data_completeness(
    evaluated_pairs: Dict[str, Tuple[Optional[Any], Optional[Any]]]
) -> float:
    """
    Calculates data completeness percentage based ONLY on metrics that have
    a frozen prediction.
      Denominator: Count of metrics where predicted is not None.
      Numerator: Count of those predicted metrics where actual is also not None.
      Formula: (numerator / denominator) * 100.0
      If denominator == 0: returns 0.0%.
    """
    denominator = 0
    numerator = 0
    for _metric, (pred_val, act_val) in evaluated_pairs.items():
        if pred_val is not None:
            denominator += 1
            if act_val is not None:
                numerator += 1
    if denominator == 0:
        return 0.0
    return round((numerator / denominator) * 100.0, 1)


# -------------------------------------------------------------
# 3. CORE CALIBRATION CALCULATION ENGINE
# -------------------------------------------------------------

def calculate_prediction_calibration(
    decision_data: Dict[str, Any],
    outcome_data: Dict[str, Any],
    calculation_version: str = V8_CALIBRATION_VERSION
) -> Dict[str, Any]:
    """
    Performs pure prediction-vs-reality calibration given a decision snapshot
    and an outcome record. Does NOT modify the database.

    Metrics calibrated:
      1. Demand (daily units velocity or period total)
      2. Contribution Margin % (in percentage points)
      3. Return to Origin (RTO) % (in percentage points)
      4. Customer Acquisition Cost (CAC)
      5. Average Selling Price (MSRP vs actual realized price)
    """
    # 1. Date normalization & period days calculation
    days_in_period = 1
    period_start_str = outcome_data.get("period_start")
    period_end_str = outcome_data.get("period_end")
    if period_start_str and period_end_str:
        try:
            d_start = datetime.datetime.strptime(str(period_start_str)[:10], "%Y-%m-%d").date()
            d_end = datetime.datetime.strptime(str(period_end_str)[:10], "%Y-%m-%d").date()
            days_in_period = max(1, (d_end - d_start).days + 1)
        except Exception:
            days_in_period = 1

    # 2. Demand calibration
    pred_daily_units = decision_data.get("predicted_daily_units")
    act_units_sold = outcome_data.get("actual_units_sold")

    demand_predicted: Optional[float] = None
    demand_actual: Optional[float] = None

    if pred_daily_units is not None:
        demand_predicted = float(pred_daily_units)

    if outcome_data.get("actual_daily_units") is not None:
        demand_actual = float(outcome_data["actual_daily_units"])
    elif act_units_sold is not None:
        # Standardize to daily velocity: actual_units_sold / days_in_period
        demand_actual = round(float(act_units_sold) / float(days_in_period), 2)

    demand_signed = calculate_signed_error(demand_actual, demand_predicted)
    demand_abs = calculate_absolute_error(demand_actual, demand_predicted)
    demand_pct = calculate_percentage_error(demand_actual, demand_predicted)
    directional_accuracy = classify_prediction_direction(demand_actual, demand_predicted)

    # 3. Contribution Margin calibration (percentage points)
    cm_pred_pct = decision_data.get("predicted_cm_pct")
    cm_act_pct = outcome_data.get("actual_cm_pct")
    cm_signed_pp, cm_abs_pp = calculate_percentage_point_error(cm_act_pct, cm_pred_pct)

    # 4. RTO calibration (percentage points)
    rto_pred_pct = decision_data.get("predicted_rto_pct")
    rto_act_pct = outcome_data.get("actual_rto_rate_pct")
    rto_signed_pp, rto_abs_pp = calculate_percentage_point_error(rto_act_pct, rto_pred_pct)

    # 5. CAC calibration
    cac_pred = decision_data.get("predicted_cac")
    cac_act = outcome_data.get("actual_cac")
    cac_signed = calculate_signed_error(cac_act, cac_pred)
    cac_abs = calculate_absolute_error(cac_act, cac_pred)
    cac_pct = calculate_percentage_error(cac_act, cac_pred)

    # 6. Selling Price calibration
    price_pred = decision_data.get("predicted_selling_price")
    price_act = outcome_data.get("actual_avg_selling_price")
    price_signed = calculate_signed_error(price_act, price_pred)

    # 7. Data Completeness Calculation
    # Evaluates the 4 core commercial forecast metrics: demand, CM, RTO, CAC
    core_pairs = {
        "demand": (demand_predicted, demand_actual),
        "cm": (cm_pred_pct, cm_act_pct),
        "rto": (rto_pred_pct, rto_act_pct),
        "cac": (cac_pred, cac_act)
    }
    completeness_pct = calculate_data_completeness(core_pairs)

    # 8. Calibration Status Determination
    predicted_count = sum(1 for p, _ in core_pairs.values() if p is not None)
    observed_count = sum(1 for p, a in core_pairs.values() if p is not None and a is not None)

    if predicted_count == 0:
        calibration_status = STATUS_NOT_CALCULABLE
    elif observed_count == 0:
        calibration_status = STATUS_INSUFFICIENT_DATA
    elif observed_count == predicted_count:
        calibration_status = STATUS_CALIBRATED
    else:
        calibration_status = STATUS_PARTIAL_DATA

    details = {
        "days_in_period": days_in_period,
        "actual_units_total": act_units_sold,
        "demand_basis": "DAILY_UNITS_VELOCITY",
        "predicted_metrics_count": predicted_count,
        "observed_metrics_count": observed_count,
        "frozen_score": decision_data.get("frozen_score"),
        "frozen_confidence": decision_data.get("frozen_confidence"),
        "frozen_kill_status": decision_data.get("frozen_kill_status")
    }

    return {
        "decision_id": decision_data.get("decision_id"),
        "outcome_id": outcome_data.get("outcome_id"),
        "product_id": decision_data.get("product_id") or outcome_data.get("product_id"),
        "demand_predicted": demand_predicted,
        "demand_actual": demand_actual,
        "demand_signed_error": demand_signed,
        "demand_absolute_error": demand_abs,
        "demand_percentage_error": demand_pct,
        "cm_predicted_pct": cm_pred_pct,
        "cm_actual_pct": cm_act_pct,
        "cm_signed_error_pct_points": cm_signed_pp,
        "cm_absolute_error_pct_points": cm_abs_pp,
        "rto_predicted_pct": rto_pred_pct,
        "rto_actual_pct": rto_act_pct,
        "rto_signed_error_pct_points": rto_signed_pp,
        "rto_absolute_error_pct_points": rto_abs_pp,
        "cac_predicted": cac_pred,
        "cac_actual": cac_act,
        "cac_signed_error": cac_signed,
        "cac_absolute_error": cac_abs,
        "cac_percentage_error": cac_pct,
        "price_predicted": price_pred,
        "price_actual": price_act,
        "price_signed_error": price_signed,
        "directional_accuracy": directional_accuracy,
        "data_completeness_pct": completeness_pct,
        "calibration_status": calibration_status,
        "calculation_version": calculation_version,
        "details_json": json.dumps(details, sort_keys=True),
        "notes": outcome_data.get("notes")
    }


# -------------------------------------------------------------
# 4. DECISION-TO-OUTCOME MATCHING & TEMPORAL INTEGRITY
# -------------------------------------------------------------

def match_decision_for_outcome(
    outcome_record: Dict[str, Any]
) -> Tuple[Optional[Dict[str, Any]], str, str]:
    """
    Finds the authoritative, compatible decision record from `decision_ledger`
    for a given outcome record.

    Matching Rules:
      1. Explicit decision_id Linkage:
         If outcome_record has a non-null decision_id, look up that exact decision.
         - Verify product_id matches.
         - Enforce temporal integrity: decision_timestamp must not be strictly AFTER
           the outcome period began (period_start).
      2. Unambiguous Fallback Matching:
         If decision_id is None, query all decisions for product_id where
         decision_timestamp <= period_start.
         - If count == 1: Exactly one eligible decision exists -> Unambiguous match.
         - If count == 0: No prior decision exists -> NO_MATCHING_DECISION.
         - If count > 1: Multiple candidate decisions exist -> NO_UNAMBIGUOUS_DECISION.
           APRS will NOT guess.

    Returns:
      (matched_decision_dict_or_None, match_status, explanation_notes)
    """
    product_id = outcome_record.get("product_id")
    if not product_id:
        return (None, STATUS_INVALID_INPUT, "Outcome record missing product_id")

    period_start_str = outcome_record.get("period_start")
    if not period_start_str:
        return (None, STATUS_INVALID_INPUT, "Outcome record missing period_start")

    try:
        outcome_start_date = datetime.datetime.strptime(str(period_start_str)[:10], "%Y-%m-%d").date()
    except Exception as e:
        return (None, STATUS_INVALID_INPUT, f"Malformed period_start date: {e}")

    # Case 1: Explicit decision_id
    explicit_dec_id = outcome_record.get("decision_id")
    if explicit_dec_id is not None:
        dec = get_decision_snapshot(int(explicit_dec_id))
        if not dec:
            return (None, STATUS_NO_MATCHING_DECISION, f"Explicit decision_id {explicit_dec_id} does not exist.")
        if dec["product_id"] != product_id:
            return (None, STATUS_INVALID_INPUT, f"Product mismatch: outcome product {product_id} != decision product {dec['product_id']}")

        # Enforce temporal integrity
        dec_time_str = dec.get("decision_timestamp")
        if dec_time_str:
            try:
                dec_date = datetime.datetime.strptime(str(dec_time_str)[:10], "%Y-%m-%d").date()
                if dec_date > outcome_start_date:
                    return (
                        None,
                        STATUS_TEMPORAL_MISMATCH,
                        f"Temporal integrity violation: Decision recorded on {dec_date} occurs after outcome period began on {outcome_start_date}."
                    )
            except Exception:
                pass
        return (dec, STATUS_CALIBRATED, "Explicit decision_id matched successfully with temporal integrity.")

    # Case 2: Fallback chronological matching
    conn = get_connection()
    cur = conn.cursor()
    # Find all decisions for product that occurred on or before the outcome period start
    cur.execute('''
        SELECT decision_id FROM decision_ledger
        WHERE product_id = ? AND date(decision_timestamp) <= ?
        ORDER BY decision_timestamp DESC, decision_id DESC
    ''', (product_id, outcome_start_date.isoformat()))
    candidate_rows = cur.fetchall()
    conn.close()

    if not candidate_rows:
        return (None, STATUS_NO_MATCHING_DECISION, f"No decision snapshot exists on or before {outcome_start_date} for product {product_id}.")

    if len(candidate_rows) == 1:
        matched_id = candidate_rows[0][0]
        dec = get_decision_snapshot(matched_id)
        return (dec, STATUS_CALIBRATED, f"Unambiguous single prior decision {matched_id} matched chronologically.")

    # More than 1 candidate decision exists -> Ambiguous! Do not guess.
    return (
        None,
        STATUS_NO_UNAMBIGUOUS_DECISION,
        f"Multiple candidate decisions ({len(candidate_rows)}) exist prior to {outcome_start_date}. Explicit decision_id linkage required."
    )


# -------------------------------------------------------------
# 5. AGGREGATE BIAS & SAMPLE-SIZE RELIABILITY SERVICES
# -------------------------------------------------------------

def calculate_aggregate_bias(
    calibrations: List[Dict[str, Any]],
    metric_prefix: str = "demand"
) -> Dict[str, Any]:
    """
    Computes aggregate directional bias and error metrics across a sample
    of calibration records, enforcing strict sample-size gating:

      Sample Size Safeguards:
        - N < 5: INSUFFICIENT_SAMPLE (individual errors valid, but aggregate is provisional/unreliable)
        - N >= 5: PROVISIONAL_AGGREGATE

      Formulas:
        Mean Signed Error (or Mean Bias Error / MBE): sum(actual - predicted) / valid_n
          - positive -> systematic underprediction tendency
          - negative -> systematic overprediction tendency
        Mean Absolute Error (MAE): sum(abs(actual - predicted)) / valid_n
        Mean Absolute Percentage Error (MAPE): sum(abs(percentage_error)) / count(valid_pct_errors)
          - observations with undefined percentage error (predicted == 0 or NULL) are excluded
            from the MAPE denominator.
    """
    sample_size = len(calibrations)
    reliability_tier = RELIABILITY_PROVISIONAL_AGGREGATE if sample_size >= SAMPLE_SIZE_MIN_AGGREGATE else RELIABILITY_INSUFFICIENT_SAMPLE

    signed_key = f"{metric_prefix}_signed_error" if metric_prefix != "cm" and metric_prefix != "rto" else f"{metric_prefix}_signed_error_pct_points"
    abs_key = f"{metric_prefix}_absolute_error" if metric_prefix != "cm" and metric_prefix != "rto" else f"{metric_prefix}_absolute_error_pct_points"
    pct_key = f"{metric_prefix}_percentage_error"

    valid_signed = [c[signed_key] for c in calibrations if c.get(signed_key) is not None]
    valid_abs = [c[abs_key] for c in calibrations if c.get(abs_key) is not None]
    valid_pct = [c[pct_key] for c in calibrations if c.get(pct_key) is not None]

    valid_n = len(valid_signed)
    if valid_n == 0:
        return {
            "metric": metric_prefix,
            "sample_size": sample_size,
            "valid_observations": 0,
            "mean_signed_error": None,
            "mean_absolute_error": None,
            "mape": None,
            "systematic_bias": "NONE",
            "reliability_tier": reliability_tier,
            "notes": "No valid observations for requested metric."
        }

    mean_signed = round(sum(valid_signed) / float(valid_n), 4)
    mean_abs = round(sum(valid_abs) / float(len(valid_abs)), 4) if valid_abs else None
    mape = round(sum(abs(p) for p in valid_pct) / float(len(valid_pct)), 2) if valid_pct else None

    if math.isclose(mean_signed, 0.0, abs_tol=1e-4):
        bias_dir = "UNBIASED"
    elif mean_signed > 0:
        bias_dir = "UNDERPREDICTION_BIAS"
    else:
        bias_dir = "OVERPREDICTION_BIAS"

    return {
        "metric": metric_prefix,
        "sample_size": sample_size,
        "valid_observations": valid_n,
        "mean_signed_error": mean_signed,
        "mean_absolute_error": mean_abs,
        "mape": mape,
        "systematic_bias": bias_dir,
        "reliability_tier": reliability_tier,
        "notes": f"Evaluated across {sample_size} records ({valid_n} valid). Tier: {reliability_tier}."
    }


# -------------------------------------------------------------
# 6. ORCHESTRATION & DATABASE PERSISTENCE SERVICE
# -------------------------------------------------------------

def calibrate_outcome(
    outcome_id: int,
    calculation_version: str = V8_CALIBRATION_VERSION
) -> Dict[str, Any]:
    """
    Main entry point to calibrate an individual outcome against its
    authoritative frozen decision snapshot.

    Pipeline:
      1. Fetch outcome record.
      2. Match authoritative decision snapshot with temporal checks.
      3. Compute prediction calibration.
      4. Persist to `prediction_calibrations` (idempotent ON CONFLICT).
      5. Return result payload.
    """
    outcome = get_outcome_by_id(outcome_id)
    if not outcome:
        return {
            "status": "ERROR",
            "outcome_id": outcome_id,
            "error": f"Outcome record {outcome_id} not found."
        }

    # Match authoritative decision
    decision, match_status, explanation = match_decision_for_outcome(outcome)
    if not decision:
        return {
            "status": "SKIPPED",
            "outcome_id": outcome_id,
            "product_id": outcome.get("product_id"),
            "calibration_status": match_status,
            "reason": explanation
        }

    # Calculate calibration
    calib_payload = calculate_prediction_calibration(
        decision_data=decision,
        outcome_data=outcome,
        calculation_version=calculation_version
    )

    # Persist calibration idempotently
    calib_id = save_prediction_calibration(calib_payload)
    calib_payload["calibration_id"] = calib_id
    calib_payload["status"] = "SUCCESS"
    calib_payload["match_explanation"] = explanation
    return calib_payload


def calibrate_all_uncalibrated_outcomes(
    calculation_version: str = V8_CALIBRATION_VERSION
) -> Dict[str, Any]:
    """
    Batch calibrator: Identifies all outcomes in `product_outcomes` that do not yet
    have a calibration record for `calculation_version` and executes calibration.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT po.outcome_id
        FROM product_outcomes po
        LEFT JOIN prediction_calibrations pc
            ON po.outcome_id = pc.outcome_id AND pc.calculation_version = ?
        WHERE pc.calibration_id IS NULL
        ORDER BY po.period_start ASC, po.outcome_id ASC
    ''', (calculation_version,))
    uncalibrated_rows = cur.fetchall()
    conn.close()

    total_uncalibrated = len(uncalibrated_rows)
    processed = 0
    calibrated = 0
    partial = 0
    skipped_no_match = 0
    errors = 0

    results = []
    for (out_id,) in uncalibrated_rows:
        processed += 1
        res = calibrate_outcome(out_id, calculation_version=calculation_version)
        results.append(res)
        if res.get("status") == "SUCCESS":
            calib_stat = res.get("calibration_status")
            if calib_stat == STATUS_CALIBRATED:
                calibrated += 1
            elif calib_stat == STATUS_PARTIAL_DATA:
                partial += 1
        elif res.get("status") == "SKIPPED":
            skipped_no_match += 1
        else:
            errors += 1

    return {
        "total_uncalibrated": total_uncalibrated,
        "processed": processed,
        "calibrated": calibrated,
        "partial": partial,
        "skipped_no_match": skipped_no_match,
        "errors": errors,
        "calculation_version": calculation_version,
        "details": results
    }


def get_calibration_summary_for_product(
    product_id: str,
    calculation_version: str = V8_CALIBRATION_VERSION
) -> Dict[str, Any]:
    """
    Aggregates historical calibrations for a product and returns multi-metric
    directional bias and sample-size reliability status.
    """
    calibrations = get_calibrations_for_product(product_id)
    calibs = [c for c in calibrations if c.get("calculation_version") == calculation_version]

    demand_bias = calculate_aggregate_bias(calibs, metric_prefix="demand")
    cm_bias = calculate_aggregate_bias(calibs, metric_prefix="cm")
    rto_bias = calculate_aggregate_bias(calibs, metric_prefix="rto")
    cac_bias = calculate_aggregate_bias(calibs, metric_prefix="cac")

    return {
        "product_id": product_id,
        "calculation_version": calculation_version,
        "calibration_count": len(calibs),
        "reliability_tier": demand_bias["reliability_tier"],
        "demand_bias": demand_bias,
        "cm_bias": cm_bias,
        "rto_bias": rto_bias,
        "cac_bias": cac_bias,
        "calibrations": calibs
    }
