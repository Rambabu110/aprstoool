"""
core/prediction_reality_report.py — APRS V8 Phase 6 Read-Only Reporting Service
==============================================================================
Exposes closed-loop Prediction vs Reality evidence comparing frozen decision-time
predictions against real-world observed outcomes and calibration metrics.

ABSOLUTE ARCHITECTURAL INVARIANTS:
1. PURE READ-ONLY SERVICE: Never mutates master_products, decision_ledger,
   product_outcomes, prediction_calibrations, or outcome_corrections_log.
2. STRICT NULL VS ZERO SEMANTICS:
   - 0 is a valid observed numeric value (e.g. 0 units sold, ₹0 revenue, 0% CM).
   - NULL (None) signifies unobserved / unavailable data.
   - None is NEVER formatted as 0, ₹0, or 0.0%.
3. ACCURATE ERROR TERMINOLOGY:
   - Mean Signed Error / Mean Bias Error (MBE): sum(actual - predicted) / N
   - Mean Absolute Error (MAE): sum(abs(actual - predicted)) / N
   - Mean Absolute Percentage Error (MAPE): sum(abs(pct_err)) / valid_N
   - Mean Squared Error is NEVER used as APRS calculates Signed Error (MBE), MAE, and MAPE.
4. NO FAKE DATA: Returns structural readiness indicators when 0 outcomes exist
   without fabricating charts, estimates, or synthetic records.
"""

import sqlite3
import datetime
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

from core.database import get_connection, get_db_path
from core.calibration_engine import (
    calculate_aggregate_bias,
    DIRECTION_OVERPREDICTED,
    DIRECTION_UNDERPREDICTED,
    DIRECTION_EXACT,
    DIRECTION_UNKNOWN,
    STATUS_CALIBRATED,
    STATUS_PARTIAL_DATA,
    SAMPLE_SIZE_MIN_AGGREGATE
)
from core.observation_scheduler import ObservationScheduler

logger = logging.getLogger("aprs.prediction_reality_report")

# Coverage status constants
COVERAGE_NO_DECISION = "NO_DECISION"
COVERAGE_DECISION_NO_OUTCOME = "DECISION_NO_OUTCOME"
COVERAGE_OUTCOME_NO_CALIBRATION = "OUTCOME_NO_CALIBRATION"
COVERAGE_PARTIAL_OUTCOME = "PARTIAL_OUTCOME"
COVERAGE_COMPLETE_CALIBRATED = "COMPLETE_CALIBRATED"


def format_metric(
    val: Any,
    metric_type: str = "number",
    default_str: str = "Not observed"
) -> str:
    """
    Format a metric value, strictly distinguishing between 0 (observed zero)
    and None (unobserved / unavailable).
    """
    if val is None:
        return default_str

    try:
        val_float = float(val)
    except (ValueError, TypeError):
        return str(val)

    if metric_type == "currency":
        if abs(val_float) < 100 and val_float != int(val_float):
            return f"₹{val_float:,.2f}"
        return f"₹{val_float:,.0f}"
    elif metric_type == "percentage":
        return f"{val_float:+.1f}%" if val_float != 0 else "0.0%"
    elif metric_type == "percentage_abs":
        return f"{abs(val_float):.1f}%"
    elif metric_type == "pp":
        return f"{val_float:+.1f} pp" if val_float != 0 else "0.0 pp"
    elif metric_type == "signed_number":
        return f"{val_float:+.2f}" if val_float != 0 else "0.00"
    elif metric_type == "integer":
        return f"{int(round(val_float)):,}"
    else:
        if val_float == int(val_float):
            return f"{int(val_float):,}"
        return f"{val_float:,.2f}"


def format_currency_pvr(val: Any, default_str: str = "Not observed") -> str:
    return format_metric(val, metric_type="currency", default_str=default_str)


def format_pct_pvr(val: Any, default_str: str = "Not observed") -> str:
    return format_metric(val, metric_type="percentage", default_str=default_str)


def format_pp_pvr(val: Any, default_str: str = "Not observed") -> str:
    return format_metric(val, metric_type="pp", default_str=default_str)


class PredictionRealityReportService:
    """
    Read-only service providing portfolio summaries, product comparison dossiers,
    and maturity reporting for APRS V8 Closed-Loop Outcome Intelligence.
    """

    @staticmethod
    def _get_read_conn(db_path: Optional[str] = None) -> sqlite3.Connection:
        """Get an isolated read connection respecting db_path or default."""
        if db_path:
            conn = sqlite3.connect(str(db_path), timeout=5.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            return conn
        return get_connection()

    @classmethod
    def get_portfolio_summary(cls, db_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Aggregate portfolio-level Prediction vs Reality summary.
        Safe against zero outcomes, zero decisions, and empty databases.
        """
        conn = cls._get_read_conn(db_path)
        try:
            # 1. Master product count
            cur = conn.execute("SELECT COUNT(*) FROM master_products")
            total_master_products = cur.fetchone()[0]

            # 2. Decision counts
            cur = conn.execute("SELECT COUNT(*), COUNT(DISTINCT product_id) FROM decision_ledger")
            row = cur.fetchone()
            total_decisions = row[0]
            products_with_decisions = row[1]

            # 3. Outcome counts
            cur = conn.execute("SELECT COUNT(*), COUNT(DISTINCT product_id) FROM product_outcomes")
            row = cur.fetchone()
            total_outcomes = row[0]
            products_with_outcomes = row[1]

            # 4. Calibration counts
            cur = conn.execute("SELECT COUNT(*), COUNT(DISTINCT product_id) FROM prediction_calibrations")
            row = cur.fetchone()
            total_calibrations = row[0]
            products_with_calibrations = row[1]

            # 5. Corrections count
            cur = conn.execute("SELECT COUNT(*) FROM outcome_corrections_log")
            total_corrections = cur.fetchone()[0]

            # 6. Observed volume totals (None if 0 outcomes exist)
            if total_outcomes > 0:
                cur = conn.execute("""
                    SELECT 
                        SUM(actual_units_sold),
                        SUM(actual_revenue)
                    FROM product_outcomes
                """)
                vol_row = cur.fetchone()
                total_observed_units = vol_row[0]
                total_observed_revenue = vol_row[1]
            else:
                total_observed_units = None
                total_observed_revenue = None

            # 7. Products awaiting observation:
            # Launched or committed products without any outcome records
            cur = conn.execute("""
                SELECT COUNT(DISTINCT p.product_id)
                FROM master_products p
                LEFT JOIN product_outcomes o ON p.product_id = o.product_id
                WHERE o.outcome_id IS NULL
                  AND (
                      p.product_id IN (SELECT product_id FROM decision_ledger)
                      OR p.product_id IN (SELECT product_id FROM launchpad_items WHERE launch_status = 'LAUNCHED')
                  )
            """)
            products_awaiting_observation = cur.fetchone()[0]

            # 8. Products with partial observations
            cur = conn.execute("""
                SELECT COUNT(DISTINCT product_id)
                FROM product_outcomes
                WHERE actual_units_sold IS NULL
                   OR actual_revenue IS NULL
                   OR actual_landed_cogs IS NULL
            """)
            products_with_partial_observations = cur.fetchone()[0]

            # 9. Calibration aggregations (demand & price bias, MAE, MAPE)
            cur = conn.execute("SELECT * FROM prediction_calibrations ORDER BY calibration_id")
            calibrations = [dict(r) for r in cur.fetchall()]

            if calibrations:
                demand_bias = calculate_aggregate_bias(calibrations, metric_prefix="demand")
                price_bias = calculate_aggregate_bias(calibrations, metric_prefix="price")

                demand_mbe = demand_bias.get("mean_signed_error")
                demand_mae = demand_bias.get("mean_absolute_error")
                demand_mape = demand_bias.get("mape")
                price_mbe = price_bias.get("mean_signed_error")
                sample_size = demand_bias.get("sample_size", len(calibrations))
                calibration_reliability = demand_bias.get("reliability_tier", "INSUFFICIENT_SAMPLE")

                # Directional distribution
                dir_counts = {
                    DIRECTION_OVERPREDICTED: 0,
                    DIRECTION_UNDERPREDICTED: 0,
                    DIRECTION_EXACT: 0,
                    DIRECTION_UNKNOWN: 0
                }
                for c in calibrations:
                    d = c.get("directional_accuracy", DIRECTION_UNKNOWN)
                    dir_counts[d] = dir_counts.get(d, 0) + 1
            else:
                demand_mbe = None
                demand_mae = None
                demand_mape = None
                price_mbe = None
                sample_size = 0
                calibration_reliability = "NO_CALIBRATIONS"
                dir_counts = {
                    DIRECTION_OVERPREDICTED: 0,
                    DIRECTION_UNDERPREDICTED: 0,
                    DIRECTION_EXACT: 0,
                    DIRECTION_UNKNOWN: 0
                }

            # 10. Observation maturity integration
            try:
                maturity_summary = ObservationScheduler.get_maturity_summary()
            except Exception as e:
                logger.warning(f"Error fetching maturity summary: {e}")
                maturity_summary = {
                    "total_launched_products": 0,
                    "total_scheduled_windows": 0,
                    "observed_count": 0,
                    "partially_observed_count": 0,
                    "due_count": 0,
                    "overdue_count": 0,
                    "not_due_count": 0,
                    "as_of_date": datetime.date.today().isoformat()
                }

            return {
                "total_master_products": total_master_products,
                "products_with_decisions": products_with_decisions,
                "products_with_outcomes": products_with_outcomes,
                "products_awaiting_observation": products_awaiting_observation,
                "products_with_partial_observations": products_with_partial_observations,
                "products_with_calibrations": products_with_calibrations,
                "total_decisions": total_decisions,
                "total_outcomes": total_outcomes,
                "total_calibrations": total_calibrations,
                "total_corrections": total_corrections,
                "total_observed_units": total_observed_units,
                "total_observed_revenue": total_observed_revenue,
                "demand_bias_mbe": demand_mbe,
                "demand_mae": demand_mae,
                "demand_mape": demand_mape,
                "price_bias_mbe": price_mbe,
                "directional_accuracy_counts": dir_counts,
                "calibration_reliability": calibration_reliability,
                "sample_size": sample_size,
                "structural_readiness": {
                    "decision_ledger_ready": True,
                    "outcome_ingestion_ready": True,
                    "calibration_engine_ready": True,
                    "observation_scheduler_ready": True,
                },
                "maturity_summary": maturity_summary
            }
        finally:
            conn.close()

    @classmethod
    def get_products_pvr_catalog(
        cls,
        limit: int = 200,
        db_path: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        High-efficiency catalog query returning products prioritized by outcome
        and decision presence. Zero N+1 query overhead.
        """
        conn = cls._get_read_conn(db_path)
        try:
            query = """
            SELECT 
                p.product_id, 
                p.name, 
                p.category, 
                p.status,
                COALESCE(d.d_count, 0) AS decision_count,
                d.latest_decision_timestamp,
                COALESCE(o.o_count, 0) AS outcome_count,
                o.latest_period_end,
                COALESCE(c_agg.c_count, 0) AS calibration_count,
                c.directional_accuracy AS latest_directional_accuracy,
                lp.launch_status,
                lp.target_launch_date
            FROM master_products p
            LEFT JOIN (
                SELECT product_id, COUNT(*) AS d_count, MAX(decision_timestamp) AS latest_decision_timestamp
                FROM decision_ledger
                GROUP BY product_id
            ) d ON p.product_id = d.product_id
            LEFT JOIN (
                SELECT product_id, COUNT(*) AS o_count, MAX(period_end) AS latest_period_end
                FROM product_outcomes
                GROUP BY product_id
            ) o ON p.product_id = o.product_id
            LEFT JOIN (
                SELECT product_id, COUNT(*) AS c_count, MAX(calibration_id) AS max_cid
                FROM prediction_calibrations
                GROUP BY product_id
            ) c_agg ON p.product_id = c_agg.product_id
            LEFT JOIN prediction_calibrations c ON c.calibration_id = c_agg.max_cid
            LEFT JOIN launchpad_items lp ON p.product_id = lp.product_id
            ORDER BY 
                CASE 
                    WHEN COALESCE(o.o_count, 0) > 0 THEN 0 
                    WHEN COALESCE(d.d_count, 0) > 0 THEN 1 
                    WHEN lp.launch_status = 'LAUNCHED' THEN 2
                    ELSE 3 
                END,
                p.product_id ASC
            LIMIT ?
            """
            cur = conn.execute(query, (limit,))
            rows = cur.fetchall()

            catalog = []
            for r in rows:
                d_count = r["decision_count"]
                o_count = r["outcome_count"]
                c_count = r["calibration_count"]

                if c_count > 0:
                    coverage = COVERAGE_COMPLETE_CALIBRATED
                elif o_count > 0:
                    coverage = COVERAGE_OUTCOME_NO_CALIBRATION
                elif d_count > 0:
                    coverage = COVERAGE_DECISION_NO_OUTCOME
                else:
                    coverage = COVERAGE_NO_DECISION

                catalog.append({
                    "product_id": r["product_id"],
                    "name": r["name"] or r["product_id"],
                    "category": r["category"] or "General",
                    "status": r["status"] or "PENDING",
                    "decision_count": d_count,
                    "latest_decision_timestamp": r["latest_decision_timestamp"],
                    "outcome_count": o_count,
                    "latest_period_end": r["latest_period_end"],
                    "calibration_count": c_count,
                    "latest_directional_accuracy": r["latest_directional_accuracy"] or "UNKNOWN",
                    "launch_status": r["launch_status"] or "NOT_LAUNCHED",
                    "target_launch_date": r["target_launch_date"],
                    "coverage_status": coverage
                })
            return catalog
        finally:
            conn.close()

    @classmethod
    def get_product_pvr_dossier(
        cls,
        product_id: str,
        db_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Retrieves the complete closed-loop Prediction vs Reality dossier for a product.
        Includes frozen historical decision ledger, observed outcomes, calibration records,
        paired comparisons, and observation maturity schedules.
        """
        conn = cls._get_read_conn(db_path)
        try:
            # 1. Master product
            cur = conn.execute("""
                SELECT 
                    product_id, name, category, region, planned_msrp, landed_cogs,
                    gross_margin_pct, estimated_cac, estimated_daily_units,
                    overall_score, status, created_at, updated_at
                FROM master_products 
                WHERE product_id = ?
            """, (product_id,))
            prod_row = cur.fetchone()
            if not prod_row:
                return {
                    "product_id": product_id,
                    "exists": False,
                    "coverage_status": "PRODUCT_NOT_FOUND"
                }

            master_info = dict(prod_row)

            # 2. Current intelligence (V7.2) for current comparison
            cur = conn.execute("""
                SELECT 
                    opportunity_score, 
                    kill_status, 
                    confidence_score, 
                    freshness_status,
                    created_at,
                    updated_at
                FROM product_intelligence 
                WHERE product_id = ?
            """, (product_id,))
            intel_row = cur.fetchone()
            current_intelligence = dict(intel_row) if intel_row else None

            # 3. Decision ledger records (frozen history)
            cur = conn.execute("""
                SELECT 
                    decision_id,
                    product_id,
                    research_run_id,
                    decision_type,
                    decision_timestamp,
                    frozen_score,
                    frozen_confidence,
                    frozen_kill_status,
                    predicted_daily_units,
                    predicted_selling_price,
                    predicted_cogs,
                    predicted_cm_pct,
                    predicted_rto_pct,
                    predicted_cac,
                    policy_version,
                    model_version,
                    snapshot_payload_json,
                    created_at
                FROM decision_ledger 
                WHERE product_id = ? 
                ORDER BY decision_timestamp DESC, decision_id DESC
            """, (product_id,))
            decisions = [dict(r) for r in cur.fetchall()]

            # 4. Product outcomes
            cur = conn.execute("""
                SELECT 
                    outcome_id,
                    product_id,
                    decision_id,
                    period_start,
                    period_end,
                    period_type,
                    actual_units_sold,
                    actual_revenue,
                    actual_avg_selling_price,
                    actual_landed_cogs,
                    actual_contribution_margin,
                    actual_cm_pct,
                    actual_returns_count,
                    actual_return_rate_pct,
                    actual_rto_count,
                    actual_rto_rate_pct,
                    actual_ad_spend,
                    actual_cac,
                    actual_inventory,
                    actual_stockout_days,
                    data_source,
                    source_record_id,
                    notes,
                    ingested_at,
                    updated_at
                FROM product_outcomes 
                WHERE product_id = ? 
                ORDER BY period_start DESC, outcome_id DESC
            """, (product_id,))
            outcomes = [dict(r) for r in cur.fetchall()]

            # 5. Fetch corrections for each outcome
            for out in outcomes:
                oid = out["outcome_id"]
                cur = conn.execute("""
                    SELECT 
                        correction_id,
                        outcome_id,
                        field_name,
                        previous_value,
                        new_value,
                        correction_reason,
                        corrected_by,
                        correction_timestamp
                    FROM outcome_corrections_log 
                    WHERE outcome_id = ? 
                    ORDER BY correction_timestamp DESC
                """, (oid,))
                corrs = [dict(r) for r in cur.fetchall()]
                out["corrections"] = corrs
                out["is_corrected"] = len(corrs) > 0
                out["correction_count"] = len(corrs)

            # 6. Prediction calibrations
            cur = conn.execute("""
                SELECT 
                    calibration_id,
                    decision_id,
                    outcome_id,
                    product_id,
                    calibration_timestamp,
                    demand_predicted,
                    demand_actual,
                    demand_signed_error,
                    demand_absolute_error,
                    demand_percentage_error,
                    cm_predicted_pct,
                    cm_actual_pct,
                    cm_signed_error_pct_points,
                    cm_absolute_error_pct_points,
                    rto_predicted_pct,
                    rto_actual_pct,
                    rto_signed_error_pct_points,
                    rto_absolute_error_pct_points,
                    cac_predicted,
                    cac_actual,
                    cac_signed_error,
                    cac_absolute_error,
                    cac_percentage_error,
                    price_predicted,
                    price_actual,
                    price_signed_error,
                    directional_accuracy,
                    data_completeness_pct,
                    calibration_status,
                    calculation_version,
                    details_json,
                    notes,
                    created_at
                FROM prediction_calibrations 
                WHERE product_id = ? 
                ORDER BY calibration_timestamp DESC, calibration_id DESC
            """, (product_id,))
            calibrations = [dict(r) for r in cur.fetchall()]

            # 7. Map paired comparisons (decision + outcome + calibration)
            comparisons = []
            calib_by_outcome = {c["outcome_id"]: c for c in calibrations}
            decisions_by_id = {d["decision_id"]: d for d in decisions}

            for out in outcomes:
                oid = out["outcome_id"]
                calib = calib_by_outcome.get(oid)

                # Match decision
                dec = None
                if out.get("decision_id") and out["decision_id"] in decisions_by_id:
                    dec = decisions_by_id[out["decision_id"]]
                elif calib and calib.get("decision_id") in decisions_by_id:
                    dec = decisions_by_id[calib["decision_id"]]
                elif decisions:
                    # Fallback to latest decision preceding or at period_start
                    p_start = str(out.get("period_start", ""))
                    for candidate in decisions:
                        c_ts = str(candidate.get("decision_timestamp", ""))[:10]
                        if c_ts <= p_start:
                            dec = candidate
                            break
                    if not dec and decisions:
                        dec = decisions[0]

                # Compute period days & daily velocity
                p_start = out.get("period_start")
                p_end = out.get("period_end")
                days_in_period = 30
                try:
                    d_start = datetime.date.fromisoformat(str(p_start))
                    d_end = datetime.date.fromisoformat(str(p_end))
                    days_in_period = max(1, (d_end - d_start).days + 1)
                except Exception:
                    pass

                actual_units = out.get("actual_units_sold")
                actual_daily_velocity = round(actual_units / days_in_period, 2) if actual_units is not None else None

                # Build comparison metrics structure
                comp_metrics = {
                    "demand": {
                        "label": "Demand (Daily Units)",
                        "predicted": dec.get("predicted_daily_units") if dec else None,
                        "actual_daily_velocity": actual_daily_velocity,
                        "actual_total_units": actual_units,
                        "signed_error_mbe": calib.get("demand_signed_error") if calib else None,
                        "absolute_error_mae": calib.get("demand_absolute_error") if calib else None,
                        "percentage_error_mape": calib.get("demand_percentage_error") if calib else None,
                        "directional_accuracy": calib.get("directional_accuracy") if calib else None,
                    },
                    "price": {
                        "label": "Selling Price (ASP)",
                        "predicted": dec.get("predicted_selling_price") if dec else None,
                        "actual": out.get("actual_avg_selling_price"),
                        "signed_error_mbe": calib.get("price_signed_error") if calib else None,
                    },
                    "cogs": {
                        "label": "Landed COGS",
                        "predicted": dec.get("predicted_cogs") if dec else None,
                        "actual": out.get("actual_landed_cogs"),
                        "signed_error": (
                            round(out["actual_landed_cogs"] - dec["predicted_cogs"], 2)
                            if (dec and dec.get("predicted_cogs") is not None and out.get("actual_landed_cogs") is not None)
                            else None
                        ),
                    },
                    "cm": {
                        "label": "Contribution Margin %",
                        "predicted": dec.get("predicted_cm_pct") if dec else None,
                        "actual": out.get("actual_cm_pct"),
                        "signed_error_pp": calib.get("cm_signed_error_pct_points") if calib else None,
                        "absolute_error_pp": calib.get("cm_absolute_error_pct_points") if calib else None,
                    },
                    "rto": {
                        "label": "RTO Rate %",
                        "predicted": dec.get("predicted_rto_pct") if dec else None,
                        "actual": out.get("actual_rto_rate_pct"),
                        "signed_error_pp": calib.get("rto_signed_error_pct_points") if calib else None,
                        "absolute_error_pp": calib.get("rto_absolute_error_pct_points") if calib else None,
                    },
                    "cac": {
                        "label": "Customer Acquisition Cost",
                        "predicted": dec.get("predicted_cac") if dec else None,
                        "actual": out.get("actual_cac"),
                        "signed_error": calib.get("cac_signed_error") if calib else None,
                        "absolute_error": calib.get("cac_absolute_error") if calib else None,
                        "percentage_error": calib.get("cac_percentage_error") if calib else None,
                    }
                }

                comparisons.append({
                    "outcome_id": oid,
                    "decision_id": dec.get("decision_id") if dec else None,
                    "calibration_id": calib.get("calibration_id") if calib else None,
                    "period_type": out.get("period_type"),
                    "period_start": p_start,
                    "period_end": p_end,
                    "period_range": f"{p_start} → {p_end}",
                    "days_in_period": days_in_period,
                    "data_source": out.get("data_source"),
                    "source_record_id": out.get("source_record_id"),
                    "ingested_at": out.get("ingested_at"),
                    "is_corrected": out.get("is_corrected", False),
                    "correction_count": out.get("correction_count", 0),
                    "corrections": out.get("corrections", []),
                    "decision_timestamp": dec.get("decision_timestamp") if dec else None,
                    "calibration_status": calib.get("calibration_status") if calib else "NOT_CALIBRATED",
                    "data_completeness_pct": calib.get("data_completeness_pct", 0.0) if calib else 0.0,
                    "metrics": comp_metrics
                })

            # 8. Observation schedule integration
            try:
                obs_schedule = ObservationScheduler.get_product_schedule(product_id)
            except Exception as e:
                logger.warning(f"Error fetching product schedule for {product_id}: {e}")
                obs_schedule = {
                    "product_id": product_id,
                    "schedule_status": "NOT_LAUNCHED",
                    "windows": [],
                    "next_due_window": None
                }

            # 9. Determine coverage status
            if any(c.get("calibration_status") == STATUS_CALIBRATED for c in calibrations):
                coverage = COVERAGE_COMPLETE_CALIBRATED
            elif any(c.get("calibration_status") == STATUS_PARTIAL_DATA for c in calibrations):
                coverage = COVERAGE_PARTIAL_OUTCOME
            elif outcomes:
                coverage = COVERAGE_OUTCOME_NO_CALIBRATION
            elif decisions:
                coverage = COVERAGE_DECISION_NO_OUTCOME
            else:
                coverage = COVERAGE_NO_DECISION

            return {
                "product_id": product_id,
                "exists": True,
                "master": master_info,
                "coverage_status": coverage,
                "current_intelligence": current_intelligence,
                "decisions": decisions,
                "outcomes": outcomes,
                "calibrations": calibrations,
                "comparisons": comparisons,
                "observation_schedule": obs_schedule,
            }
        finally:
            conn.close()

    @classmethod
    def get_all_decision_history(
        cls,
        product_id: Optional[str] = None,
        limit: int = 50,
        db_path: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetches immutable historical decision snapshots.
        Optionally filtered by product_id.
        """
        conn = cls._get_read_conn(db_path)
        try:
            if product_id:
                cur = conn.execute("""
                    SELECT d.*, p.name AS product_name 
                    FROM decision_ledger d
                    LEFT JOIN master_products p ON d.product_id = p.product_id
                    WHERE d.product_id = ?
                    ORDER BY d.decision_timestamp DESC, d.decision_id DESC
                    LIMIT ?
                """, (product_id, limit))
            else:
                cur = conn.execute("""
                    SELECT d.*, p.name AS product_name 
                    FROM decision_ledger d
                    LEFT JOIN master_products p ON d.product_id = p.product_id
                    ORDER BY d.decision_timestamp DESC, d.decision_id DESC
                    LIMIT ?
                """, (limit,))
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    @classmethod
    def get_corrections_audit_log(
        cls,
        product_id: Optional[str] = None,
        limit: int = 50,
        db_path: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetches read-only audit log of outcome corrections.
        Optionally filtered by product_id.
        """
        conn = cls._get_read_conn(db_path)
        try:
            if product_id:
                cur = conn.execute("""
                    SELECT c.*, p.name AS product_name
                    FROM outcome_corrections_log c
                    LEFT JOIN master_products p ON c.product_id = p.product_id
                    WHERE c.product_id = ?
                    ORDER BY c.correction_timestamp DESC, c.correction_id DESC
                    LIMIT ?
                """, (product_id, limit))
            else:
                cur = conn.execute("""
                    SELECT c.*, p.name AS product_name
                    FROM outcome_corrections_log c
                    LEFT JOIN master_products p ON c.product_id = p.product_id
                    ORDER BY c.correction_timestamp DESC, c.correction_id DESC
                    LIMIT ?
                """, (limit,))
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()
