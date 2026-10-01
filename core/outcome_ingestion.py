"""
APRS V8 PHASE 3: REAL OUTCOME INGESTION & OBSERVATION FOUNDATION
================================================================
Architectural Layer: Post-Launch Observation & Outcome Ingestion
Purpose:
  Provides a deterministic, auditable, and idempotent service for recording
  real-world post-decision/post-launch seller business outcomes.

Non-Negotiable Invariants:
  1. Frozen Decision Ledger: The original historical predictions in `decision_ledger`
     are NEVER updated or altered upon outcome ingestion.
  2. Temporal Integrity: Outcomes must occur on or after their corresponding decision:
     decision_timestamp <= period_start <= period_end.
  3. No Ambiguous Matching: Never guess or silently attach an outcome to the latest
     decision if multiple historical decisions exist for the product.
  4. Explicit Auditability: Real business corrections must be explicit and logged to
     `outcome_corrections_log`, keeping previous values intact.
  5. Deterministic Calibration: Upon valid outcome ingestion or correction, the
     Prediction Calibration Engine is triggered deterministically.
  6. Transparent Metrics: Distinguish reported vs derived metrics; never invent cost components.
  7. Scraped Proxies Rejection: Pre-launch estimates (BSR, Helium, Google Trends) are
     strictly forbidden as actual post-launch outcomes.
  8. No Autonomous Learning: Observations and calibrations are analytical evidence;
     they do NOT modify underlying models, scores, or policy thresholds.
"""

import datetime
from typing import Dict, Any, List, Optional, Tuple

from core.database import (
    get_connection,
    get_outcome_by_id,
    get_product_outcomes,
    get_decision_snapshot,
    record_product_outcome,
    record_outcome_correction,
    get_outcome_corrections,
    validate_outcome_payload
)
from core.calibration_engine import (
    calibrate_outcome,
    V8_CALIBRATION_VERSION
)

# -------------------------------------------------------------
# 1. OBSERVATION STATUS CONSTANTS
# -------------------------------------------------------------

STATUS_NOT_LAUNCHED = "NOT_LAUNCHED"
STATUS_LAUNCHED_NOT_OBSERVED = "LAUNCHED_NOT_OBSERVED"
STATUS_OBSERVATION_AVAILABLE = "OBSERVATION_AVAILABLE"
STATUS_PARTIAL_OBSERVATION = "PARTIAL_OBSERVATION"

VALID_PERIOD_TYPES = ("DAY_30", "DAY_60", "DAY_90", "LIFETIME", "CUSTOM")

CORE_METRIC_FIELDS = (
    "actual_units_sold",
    "actual_revenue",
    "actual_avg_selling_price",
    "actual_landed_cogs",
    "actual_contribution_margin",
    "actual_cm_pct",
    "actual_returns_count",
    "actual_return_rate_pct",
    "actual_rto_count",
    "actual_rto_rate_pct",
    "actual_ad_spend",
    "actual_cac"
)


# -------------------------------------------------------------
# 2. DERIVED METRICS SERVICE (TRANSPARENT & AUDITABLE)
# -------------------------------------------------------------

def derive_outcome_metrics(data: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """
    Deterministically computes derived metrics ONLY when the target field is None
    and necessary inputs are available. Never silently overwrites supplied values.

    Returns:
      (enriched_dict, derived_fields_map) where derived_fields_map documents the derivation.
    """
    enriched = dict(data)
    derived: Dict[str, str] = {}

    units = enriched.get("actual_units_sold")
    rev = enriched.get("actual_revenue")
    price = enriched.get("actual_avg_selling_price")
    cm = enriched.get("actual_contribution_margin")
    cm_pct = enriched.get("actual_cm_pct")
    returns = enriched.get("actual_returns_count")
    return_pct = enriched.get("actual_return_rate_pct")
    rto = enriched.get("actual_rto_count")
    rto_pct = enriched.get("actual_rto_rate_pct")
    ad_spend = enriched.get("actual_ad_spend")
    cac = enriched.get("actual_cac")

    # 1. Price from Revenue and Units
    if price is None and rev is not None and units is not None and units > 0:
        enriched["actual_avg_selling_price"] = round(float(rev) / float(units), 2)
        derived["actual_avg_selling_price"] = "derived: revenue / units_sold"

    # 2. Revenue from Price and Units
    elif rev is None and price is not None and units is not None and units > 0:
        enriched["actual_revenue"] = round(float(price) * float(units), 2)
        derived["actual_revenue"] = "derived: avg_selling_price * units_sold"

    # 3. CM % from CM absolute and Revenue
    if cm_pct is None and cm is not None and rev is not None and rev > 0:
        enriched["actual_cm_pct"] = round((float(cm) / float(rev)) * 100.0, 2)
        derived["actual_cm_pct"] = "derived: (contribution_margin / revenue) * 100"

    # 4. CM absolute from CM % and Revenue
    elif cm is None and cm_pct is not None and rev is not None and rev > 0:
        enriched["actual_contribution_margin"] = round((float(cm_pct) / 100.0) * float(rev), 2)
        derived["actual_contribution_margin"] = "derived: (cm_pct / 100) * revenue"

    # 5. Return Rate % from Returns Count and Units
    if return_pct is None and returns is not None and units is not None and units > 0:
        enriched["actual_return_rate_pct"] = round((float(returns) / float(units)) * 100.0, 2)
        derived["actual_return_rate_pct"] = "derived: (returns_count / units_sold) * 100"

    # 6. RTO Rate % from RTO Count and Units
    if rto_pct is None and rto is not None and units is not None and units > 0:
        enriched["actual_rto_rate_pct"] = round((float(rto) / float(units)) * 100.0, 2)
        derived["actual_rto_rate_pct"] = "derived: (rto_count / units_sold) * 100"

    # 7. CAC from Ad Spend and Units
    if cac is None and ad_spend is not None and units is not None and units > 0:
        enriched["actual_cac"] = round(float(ad_spend) / float(units), 2)
        derived["actual_cac"] = "derived: ad_spend / units_sold"

    return enriched, derived


# -------------------------------------------------------------
# 3. DECISION MATCHING & TEMPORAL DISAMBIGUATION
# -------------------------------------------------------------

def resolve_decision_link(
    product_id: str,
    period_start: str,
    decision_id: Optional[int] = None
) -> Optional[int]:
    """
    Validates or resolves the decision_id for an outcome observation.

    Rules:
      1. If decision_id is provided:
         - Must exist in decision_ledger.
         - Must belong to product_id.
         - decision_timestamp <= period_start.
      2. If decision_id is None:
         - Query decisions for product_id where date(decision_timestamp) <= period_start.
         - If exactly 1 prior decision: auto-link chronologically.
         - If > 1 prior decisions: raise ValueError (ambiguous historical matching).
         - If 0 prior decisions: return None (unlinked outcome).
    """
    conn = get_connection()
    cur = conn.cursor()

    try:
        d_start = datetime.date.fromisoformat(str(period_start))
    except (ValueError, TypeError) as e:
        conn.close()
        raise ValueError(f"Invalid period_start format (expected YYYY-MM-DD): {e}")

    if decision_id is not None:
        cur.execute(
            "SELECT decision_id, product_id, decision_timestamp FROM decision_ledger WHERE decision_id = ?",
            (decision_id,)
        )
        dec_row = cur.fetchone()
        if not dec_row:
            conn.close()
            raise ValueError(f"Foreign Key Error: Decision '{decision_id}' does not exist in decision_ledger.")

        dec_dict = dict(dec_row)
        if dec_dict["product_id"] != product_id:
            conn.close()
            raise ValueError(
                f"Decision mismatch: Decision '{decision_id}' belongs to product "
                f"'{dec_dict['product_id']}', not '{product_id}'."
            )

        dec_date_str = str(dec_dict["decision_timestamp"]).split("T")[0].split(" ")[0]
        dec_date = datetime.date.fromisoformat(dec_date_str)
        if dec_date > d_start:
            conn.close()
            raise ValueError(
                f"Temporal Integrity Error: Decision timestamp ({dec_dict['decision_timestamp']}) "
                f"occurs after outcome period_start ({period_start})."
            )

        conn.close()
        return decision_id

    # decision_id is None -> search prior candidate decisions
    cur.execute('''
        SELECT decision_id, decision_timestamp FROM decision_ledger
        WHERE product_id = ? AND date(decision_timestamp) <= ?
        ORDER BY decision_timestamp DESC, decision_id DESC
    ''', (product_id, d_start.isoformat()))
    candidate_rows = cur.fetchall()
    conn.close()

    if not candidate_rows:
        return None

    if len(candidate_rows) == 1:
        return candidate_rows[0][0]

    # Multiple historical decisions exist -> reject ambiguous matching
    raise ValueError(
        f"Ambiguous historical matching: {len(candidate_rows)} decisions exist for product '{product_id}' "
        f"on or prior to '{period_start}'. Explicit 'decision_id' must be specified."
    )


# -------------------------------------------------------------
# 4. OUTCOME INGESTION SERVICE CLASS
# -------------------------------------------------------------

class OutcomeIngestionService:
    """
    Main service coordinating post-launch outcome ingestion, validation,
    auditable corrections, observation status, and calibration triggers.
    """

    @staticmethod
    def ingest_outcome(
        outcome_payload: Dict[str, Any],
        auto_calibrate: bool = True,
        calculation_version: str = V8_CALIBRATION_VERSION
    ) -> Dict[str, Any]:
        """
        Ingests a post-launch outcome observation deterministically.

        Pipeline:
          1. Validates base payload (bounds, period order, stockouts, proxies).
          2. Resolves and validates decision linkage with strict temporal integrity.
          3. Derives missing metrics transparently without overwriting supplied values.
          4. Persists to product_outcomes with duplicate detection.
          5. Triggers calibration deterministically if linked to a frozen decision.
        """
        # Step 1: Base validation
        validated = validate_outcome_payload(outcome_payload)
        product_id = validated["product_id"]
        period_start = validated["period_start"]

        # Step 2: Temporal & decision resolution
        raw_decision_id = validated.get("decision_id")
        resolved_decision_id = resolve_decision_link(
            product_id=product_id,
            period_start=period_start,
            decision_id=raw_decision_id
        )
        validated["decision_id"] = resolved_decision_id

        # Step 3: Transparent metric derivation
        enriched, derived_fields = derive_outcome_metrics(validated)

        # Step 4: Database persistence (idempotent, with temporal check)
        record_res = record_product_outcome(
            outcome_data=enriched,
            update_if_exists=False,
            enforce_temporal=True
        )

        outcome_id = record_res["outcome_id"]
        status = record_res["status"]

        # Step 5: Deterministic calibration trigger
        calibration_res = None
        if auto_calibrate and status != "IDEMPOTENT_DUPLICATE" and resolved_decision_id is not None:
            calibration_res = calibrate_outcome(
                outcome_id=outcome_id,
                calculation_version=calculation_version
            )

        return {
            "outcome_id": outcome_id,
            "status": status,
            "product_id": product_id,
            "decision_id": resolved_decision_id,
            "period_type": enriched["period_type"],
            "period_start": enriched["period_start"],
            "period_end": enriched["period_end"],
            "derived_fields": derived_fields,
            "calibration": calibration_res,
            "ingested_at": datetime.datetime.now().isoformat()
        }

    @staticmethod
    def correct_outcome(
        outcome_id: int,
        correction_data: Dict[str, Any],
        reason: str,
        operator: str = "SYSTEM_OPERATOR",
        auto_calibrate: bool = True,
        calculation_version: str = V8_CALIBRATION_VERSION
    ) -> Dict[str, Any]:
        """
        Explicitly corrects an existing outcome record with full change audit logging.
        Never deletes previous values silently. Automatically recalibrates if triggered.
        """
        if not reason or not str(reason).strip():
            raise ValueError("A non-empty correction reason is mandatory for auditable outcome corrections.")

        # Ensure outcome exists
        existing = get_outcome_by_id(outcome_id)
        if not existing:
            raise ValueError(f"Outcome record {outcome_id} not found.")

        # Check temporal integrity if decision_id or period_start are modified
        product_id = existing["product_id"]
        target_dec_id = correction_data.get("decision_id", existing.get("decision_id"))
        target_start = correction_data.get("period_start", existing["period_start"])

        if target_dec_id is not None:
            # Validate decision linkage and temporal bounds
            resolve_decision_link(
                product_id=product_id,
                period_start=target_start,
                decision_id=target_dec_id
            )

        # Record correction and log diffs
        res = record_outcome_correction(
            outcome_id=outcome_id,
            updates=correction_data,
            correction_reason=reason.strip(),
            corrected_by=operator
        )

        # Trigger recalibration deterministically
        calibration_res = None
        if auto_calibrate:
            calibration_res = calibrate_outcome(
                outcome_id=outcome_id,
                calculation_version=calculation_version
            )

        return {
            "outcome_id": outcome_id,
            "status": "CORRECTED",
            "corrections_logged": res["corrections_logged"],
            "calibration": calibration_res
        }

    @staticmethod
    def get_observation_status(product_id: str) -> Dict[str, Any]:
        """
        Cleanly derives observation status from existing lifecycle data:
          - NOT_LAUNCHED: Product has not been launched.
          - LAUNCHED_NOT_OBSERVED: Product is launched, but zero outcome observations exist.
          - OBSERVATION_AVAILABLE: At least one complete observation exists.
          - PARTIAL_OBSERVATION: Observations exist, but some core metrics remain NULL.
        """
        conn = get_connection()
        cur = conn.cursor()

        # Check master_products
        cur.execute("SELECT product_id, status FROM master_products WHERE product_id = ?", (product_id,))
        prod_row = cur.fetchone()
        if not prod_row:
            conn.close()
            raise ValueError(f"Product '{product_id}' does not exist in master_products.")

        prod_status = prod_row[1] or ""

        # Check launchpad_items
        cur.execute('''
            SELECT item_id, launch_status, target_launch_date, purchase_order_generated
            FROM launchpad_items WHERE product_id = ?
            ORDER BY item_id DESC LIMIT 1
        ''', (product_id,))
        launch_row = cur.fetchone()
        conn.close()

        is_launched = False
        if prod_status.upper() in ("LAUNCHED", "LIVE", "ACTIVE", "POST_LAUNCH"):
            is_launched = True
        elif launch_row:
            l_status = (launch_row[1] or "").upper()
            po_gen = launch_row[3] or 0
            if l_status in ("LAUNCHED", "LIVE", "ACTIVE", "POST_LAUNCH") or po_gen == 1:
                is_launched = True

        outcomes = get_product_outcomes(product_id)
        if not outcomes:
            status = STATUS_LAUNCHED_NOT_OBSERVED if is_launched else STATUS_NOT_LAUNCHED
            return {
                "product_id": product_id,
                "observation_status": status,
                "is_launched": is_launched,
                "outcomes_count": 0,
                "periods_recorded": [],
                "latest_outcome": None
            }

        # Outcomes exist -> assess completeness
        periods_recorded = [o["period_type"] for o in outcomes]
        latest_outcome = outcomes[-1]

        # Determine if any observation has complete core metrics
        has_full_observation = False
        for o in outcomes:
            missing_core = [f for f in CORE_METRIC_FIELDS if o.get(f) is None]
            if not missing_core:
                has_full_observation = True
                break

        obs_status = STATUS_OBSERVATION_AVAILABLE if has_full_observation else STATUS_PARTIAL_OBSERVATION

        return {
            "product_id": product_id,
            "observation_status": obs_status,
            "is_launched": True,
            "outcomes_count": len(outcomes),
            "periods_recorded": periods_recorded,
            "latest_outcome": latest_outcome
        }

    @staticmethod
    def get_outcome_history(outcome_id: int) -> Dict[str, Any]:
        """
        Retrieves the complete lifecycle record of an outcome, including its
        current state, auditable correction history, and latest calibration.
        """
        outcome = get_outcome_by_id(outcome_id)
        if not outcome:
            raise ValueError(f"Outcome record {outcome_id} not found.")

        corrections = get_outcome_corrections(outcome_id=outcome_id)

        # Fetch latest calibration
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM prediction_calibrations WHERE outcome_id = ?", (outcome_id,))
        calib_row = cur.fetchone()
        conn.close()
        calib_dict = dict(calib_row) if calib_row else None

        return {
            "outcome": outcome,
            "corrections_count": len(corrections),
            "corrections_history": corrections,
            "calibration": calib_dict
        }
