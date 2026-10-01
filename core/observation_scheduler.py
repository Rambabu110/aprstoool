"""
APRS V8 PHASE 4A: OBSERVATION SCHEDULER & MATURITY ENGINE
=========================================================
Architectural Layer: Observation Scheduling & Maturity Tracking
Purpose:
  Deterministically determines:
    1. WHEN APRS should expect an observation for a launched product.
    2. WHAT observation period is currently due or overdue.
    3. WHETHER that observation has already been received and calibrated.

Core Invariants (Rule 0):
  1. Strict Separation: Scheduling and maturity tracking are strictly separated
     from outcome ingestion. This engine NEVER invents sales numbers, margins,
     revenues, returns, or units.
  2. Pure Analytical Evaluation: Dynamic evaluation directly from authoritative
     `launchpad_items`, `master_products`, and `product_outcomes`.
  3. Zero State Duplication: Reuses existing launch status, timestamps, and
     outcomes without creating duplicate state machines.
  4. Deterministic Time-Travel: All scheduling and maturity functions accept
     an explicit `as_of_date` parameter for deterministic testing, replay,
     and simulation.
  5. Zero Production Mutation: Operates as a read-only analytical scheduler;
     inserts zero rows into `product_outcomes` or `prediction_calibrations`.
"""

import datetime
from typing import Dict, Any, List, Optional, Tuple, Union

from core.database import (
    get_connection,
    get_product_outcomes,
    get_launched_products
)

# -------------------------------------------------------------
# 1. WINDOW MATURITY STATUS CONSTANTS
# -------------------------------------------------------------

WINDOW_STATUS_NOT_DUE = "NOT_DUE"
WINDOW_STATUS_DUE = "DUE"
WINDOW_STATUS_OVERDUE = "OVERDUE"
WINDOW_STATUS_OBSERVED = "OBSERVED"
WINDOW_STATUS_PARTIALLY_OBSERVED = "PARTIALLY_OBSERVED"
WINDOW_STATUS_NOT_LAUNCHED = "NOT_LAUNCHED"

STANDARD_WINDOWS: Tuple[str, ...] = ("DAY_30", "DAY_60", "DAY_90")

WINDOW_DURATIONS: Dict[str, int] = {
    "DAY_30": 30,
    "DAY_60": 60,
    "DAY_90": 90,
}

CORE_METRIC_FIELDS: Tuple[str, ...] = (
    "actual_units_sold",
    "actual_revenue",
    "actual_avg_selling_price",
    "actual_landed_cogs",
    "actual_contribution_margin",
    "actual_cm_pct",
    "actual_ad_spend",
    "actual_cac"
)

DEFAULT_GRACE_PERIOD_DAYS: int = 7


# -------------------------------------------------------------
# 2. PRODUCT LAUNCH DETECTION & RESOLUTION
# -------------------------------------------------------------

def get_product_launch_info(product_id: str) -> Dict[str, Any]:
    """
    Inspects master_products and launchpad_items to determine:
      - is_launched: bool
      - launch_status: str
      - effective_launch_date: datetime.date or None
      - product_name: str
      - launchpad_item_id: int or None
      - purchase_order_generated: bool
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT product_id, name, status, created_at FROM master_products WHERE product_id = ?", (product_id,))
    mp_row = cur.fetchone()
    if not mp_row:
        conn.close()
        raise ValueError(f"Product '{product_id}' does not exist in master_products.")

    mp_dict = dict(mp_row)

    cur.execute('''
        SELECT item_id, launch_status, target_launch_date, purchase_order_generated, updated_at
        FROM launchpad_items
        WHERE product_id = ?
        ORDER BY item_id DESC LIMIT 1
    ''', (product_id,))
    lp_row = cur.fetchone()
    conn.close()

    lp_dict = dict(lp_row) if lp_row else {}

    is_launched = False
    launch_status = "NOT_LAUNCHED"
    effective_launch_date: Optional[datetime.date] = None

    mp_status = (mp_dict.get("status") or "").upper()
    lp_status = (lp_dict.get("launch_status") or "").upper()
    po_gen = bool(lp_dict.get("purchase_order_generated", 0))

    if mp_status in ("LAUNCHED", "LIVE", "ACTIVE", "POST_LAUNCH"):
        is_launched = True
        launch_status = mp_status
    elif lp_status in ("LAUNCHED", "LIVE", "ACTIVE", "SHIPPED", "POST_LAUNCH") or po_gen:
        is_launched = True
        launch_status = lp_status if lp_status else ("PO_ISSUED" if po_gen else "LAUNCHED")

    # Determine effective launch date
    raw_date = lp_dict.get("target_launch_date")
    if raw_date:
        try:
            effective_launch_date = datetime.date.fromisoformat(str(raw_date)[:10])
        except Exception:
            effective_launch_date = None

    if not effective_launch_date and is_launched:
        # Fallback to launchpad updated_at or master_products created_at
        date_str = lp_dict.get("updated_at") or mp_dict.get("created_at")
        if date_str:
            try:
                effective_launch_date = datetime.date.fromisoformat(str(date_str)[:10])
            except Exception:
                effective_launch_date = None

    return {
        "product_id": product_id,
        "product_name": mp_dict.get("name", ""),
        "is_launched": is_launched,
        "launch_status": launch_status,
        "effective_launch_date": effective_launch_date,
        "launchpad_item_id": lp_dict.get("item_id"),
        "purchase_order_generated": po_gen
    }


# -------------------------------------------------------------
# 3. OBSERVATION WINDOW DATE COMPUTATION
# -------------------------------------------------------------

def compute_observation_windows(
    launch_date: Union[str, datetime.date],
    window_types: Tuple[str, ...] = STANDARD_WINDOWS
) -> List[Dict[str, Any]]:
    """
    Computes deterministic period boundaries and due dates for observation windows:
      - DAY_30: [launch, launch + 29 days], due on launch + 30 days
      - DAY_60: [launch, launch + 59 days], due on launch + 60 days
      - DAY_90: [launch, launch + 89 days], due on launch + 90 days

    Returns list of dicts with:
      period_type, period_start, period_end, due_date, duration_days
    """
    if isinstance(launch_date, str):
        l_date = datetime.date.fromisoformat(str(launch_date)[:10])
    elif isinstance(launch_date, datetime.date):
        l_date = launch_date
    else:
        raise ValueError(f"Invalid launch_date type: {type(launch_date)}")

    windows = []
    for w_type in window_types:
        if w_type not in WINDOW_DURATIONS:
            continue
        duration = WINDOW_DURATIONS[w_type]
        p_start = l_date
        p_end = l_date + datetime.timedelta(days=duration - 1)
        due = l_date + datetime.timedelta(days=duration)

        windows.append({
            "period_type": w_type,
            "period_start": p_start.isoformat(),
            "period_end": p_end.isoformat(),
            "due_date": due.isoformat(),
            "duration_days": duration
        })
    return windows


# -------------------------------------------------------------
# 4. WINDOW MATURITY EVALUATION
# -------------------------------------------------------------

def evaluate_window_maturity(
    product_id: str,
    window: Dict[str, Any],
    as_of_date: Optional[Union[str, datetime.date]] = None,
    grace_period_days: int = DEFAULT_GRACE_PERIOD_DAYS
) -> Dict[str, Any]:
    """
    Cross-references a scheduled observation window against real `product_outcomes`
    and the current evaluation date (`as_of_date`) to determine:
      - OBSERVED: Valid full outcome ingested.
      - PARTIALLY_OBSERVED: Valid outcome ingested, but some core metrics are NULL.
      - NOT_DUE: as_of_date < due_date.
      - DUE: as_of_date >= due_date and (as_of_date - due_date) <= grace_period_days.
      - OVERDUE: (as_of_date - due_date) > grace_period_days with no outcome received.
    """
    if as_of_date is None:
        eval_date = datetime.date.today()
    elif isinstance(as_of_date, str):
        eval_date = datetime.date.fromisoformat(str(as_of_date)[:10])
    else:
        eval_date = as_of_date

    p_type = window["period_type"]
    w_start = window["period_start"]
    w_end = window["period_end"]
    w_due = datetime.date.fromisoformat(window["due_date"])

    # Query existing outcomes for product & period
    outcomes = get_product_outcomes(product_id=product_id, period_type=p_type)

    # Match outcome by exact period or period_type
    matched_outcome = None
    for o in outcomes:
        if o.get("period_start") == w_start and o.get("period_end") == w_end:
            matched_outcome = o
            break
    if not matched_outcome and outcomes:
        # Fallback to any outcome matching the period_type
        matched_outcome = outcomes[0]

    if matched_outcome:
        # Check completeness of core commercial metrics
        missing_core = [f for f in CORE_METRIC_FIELDS if matched_outcome.get(f) is None]
        status = WINDOW_STATUS_OBSERVED if not missing_core else WINDOW_STATUS_PARTIALLY_OBSERVED

        return {
            "period_type": p_type,
            "period_start": w_start,
            "period_end": w_end,
            "due_date": window["due_date"],
            "status": status,
            "outcome_id": matched_outcome["outcome_id"],
            "days_until_due": 0,
            "days_overdue": 0,
            "missing_core_metrics": missing_core,
            "data_source": matched_outcome.get("data_source"),
            "ingested_at": matched_outcome.get("ingested_at")
        }

    # No outcome received yet -> evaluate temporal maturity
    if eval_date < w_due:
        days_until = (w_due - eval_date).days
        return {
            "period_type": p_type,
            "period_start": w_start,
            "period_end": w_end,
            "due_date": window["due_date"],
            "status": WINDOW_STATUS_NOT_DUE,
            "outcome_id": None,
            "days_until_due": days_until,
            "days_overdue": 0,
            "missing_core_metrics": None,
            "data_source": None,
            "ingested_at": None
        }

    # Past due date
    overdue_days = (eval_date - w_due).days
    status = WINDOW_STATUS_DUE if overdue_days <= grace_period_days else WINDOW_STATUS_OVERDUE

    return {
        "period_type": p_type,
        "period_start": w_start,
        "period_end": w_end,
        "due_date": window["due_date"],
        "status": status,
        "outcome_id": None,
        "days_until_due": 0,
        "days_overdue": overdue_days,
        "missing_core_metrics": None,
        "data_source": None,
        "ingested_at": None
    }


# -------------------------------------------------------------
# 5. OBSERVATION SCHEDULER SERVICE CLASS
# -------------------------------------------------------------

class ObservationScheduler:
    """
    Core service coordinating observation window calculation, maturity evaluation,
    due observation queues, and catalog-wide scheduling summaries.
    """

    @staticmethod
    def get_product_schedule(
        product_id: str,
        as_of_date: Optional[Union[str, datetime.date]] = None,
        grace_period_days: int = DEFAULT_GRACE_PERIOD_DAYS
    ) -> Dict[str, Any]:
        """
        Retrieves the complete observation schedule for a specific product.
        Identifies all scheduled windows, their maturity status, and the next
        expected observation.
        """
        launch_info = get_product_launch_info(product_id)

        if not launch_info["is_launched"] or not launch_info["effective_launch_date"]:
            return {
                "product_id": product_id,
                "product_name": launch_info["product_name"],
                "is_launched": False,
                "launch_status": launch_info["launch_status"],
                "effective_launch_date": None,
                "schedule_status": WINDOW_STATUS_NOT_LAUNCHED,
                "windows": [],
                "next_expected_observation": None,
                "due_windows_count": 0,
                "overdue_windows_count": 0,
                "observed_windows_count": 0
            }

        launch_date = launch_info["effective_launch_date"]
        raw_windows = compute_observation_windows(launch_date)

        evaluated_windows = []
        due_count = 0
        overdue_count = 0
        observed_count = 0

        next_expected = None

        for rw in raw_windows:
            ew = evaluate_window_maturity(
                product_id=product_id,
                window=rw,
                as_of_date=as_of_date,
                grace_period_days=grace_period_days
            )
            evaluated_windows.append(ew)

            if ew["status"] == WINDOW_STATUS_DUE:
                due_count += 1
            elif ew["status"] == WINDOW_STATUS_OVERDUE:
                overdue_count += 1
            elif ew["status"] in (WINDOW_STATUS_OBSERVED, WINDOW_STATUS_PARTIALLY_OBSERVED):
                observed_count += 1

        # Identify next expected observation
        # Priority 1: First overdue window
        for ew in evaluated_windows:
            if ew["status"] == WINDOW_STATUS_OVERDUE:
                next_expected = ew
                break
        # Priority 2: First due window
        if not next_expected:
            for ew in evaluated_windows:
                if ew["status"] == WINDOW_STATUS_DUE:
                    next_expected = ew
                    break
        # Priority 3: First upcoming (NOT_DUE) window
        if not next_expected:
            for ew in evaluated_windows:
                if ew["status"] == WINDOW_STATUS_NOT_DUE:
                    next_expected = ew
                    break

        schedule_status = "UP_TO_DATE"
        if overdue_count > 0:
            schedule_status = "HAS_OVERDUE_OBSERVATIONS"
        elif due_count > 0:
            schedule_status = "HAS_DUE_OBSERVATIONS"
        elif observed_count == len(evaluated_windows):
            schedule_status = "ALL_OBSERVATIONS_RECEIVED"

        return {
            "product_id": product_id,
            "product_name": launch_info["product_name"],
            "is_launched": True,
            "launch_status": launch_info["launch_status"],
            "effective_launch_date": launch_date.isoformat(),
            "schedule_status": schedule_status,
            "windows": evaluated_windows,
            "next_expected_observation": next_expected,
            "due_windows_count": due_count,
            "overdue_windows_count": overdue_count,
            "observed_windows_count": observed_count
        }

    @staticmethod
    def get_catalog_schedules(
        as_of_date: Optional[Union[str, datetime.date]] = None,
        status_filter: Optional[str] = None,
        grace_period_days: int = DEFAULT_GRACE_PERIOD_DAYS
    ) -> List[Dict[str, Any]]:
        """
        Retrieves observation schedules for all launched products in the catalog.
        Optionally filters by schedule_status (e.g. 'HAS_DUE_OBSERVATIONS', 'HAS_OVERDUE_OBSERVATIONS').
        """
        launched = get_launched_products()
        schedules = []
        for p in launched:
            pid = p["product_id"]
            try:
                sched = ObservationScheduler.get_product_schedule(
                    product_id=pid,
                    as_of_date=as_of_date,
                    grace_period_days=grace_period_days
                )
                if status_filter and sched["schedule_status"] != status_filter:
                    continue
                schedules.append(sched)
            except Exception:
                continue
        return schedules

    @staticmethod
    def get_due_observations(
        as_of_date: Optional[Union[str, datetime.date]] = None,
        include_overdue: bool = True,
        grace_period_days: int = DEFAULT_GRACE_PERIOD_DAYS
    ) -> List[Dict[str, Any]]:
        """
        Returns a prioritized, actionable queue of all observation windows across
        the entire catalog that are currently DUE or OVERDUE for data ingestion.
        Sorted by due_date ASC (most overdue first).
        """
        all_scheds = ObservationScheduler.get_catalog_schedules(
            as_of_date=as_of_date,
            grace_period_days=grace_period_days
        )
        due_list = []
        target_statuses = {WINDOW_STATUS_DUE}
        if include_overdue:
            target_statuses.add(WINDOW_STATUS_OVERDUE)

        for s in all_scheds:
            pid = s["product_id"]
            pname = s["product_name"]
            l_date = s["effective_launch_date"]
            for w in s["windows"]:
                if w["status"] in target_statuses:
                    due_list.append({
                        "product_id": pid,
                        "product_name": pname,
                        "launch_date": l_date,
                        "period_type": w["period_type"],
                        "period_start": w["period_start"],
                        "period_end": w["period_end"],
                        "due_date": w["due_date"],
                        "status": w["status"],
                        "days_overdue": w["days_overdue"]
                    })

        # Sort by due_date ascending (oldest due first)
        due_list.sort(key=lambda x: x["due_date"])
        return due_list

    @staticmethod
    def get_maturity_summary(
        as_of_date: Optional[Union[str, datetime.date]] = None,
        grace_period_days: int = DEFAULT_GRACE_PERIOD_DAYS
    ) -> Dict[str, Any]:
        """
        High-level aggregate portfolio maturity metrics:
          - Total launched products
          - Total scheduled windows
          - Observed count, Partially observed count
          - Due count, Overdue count, Not due count
        """
        schedules = ObservationScheduler.get_catalog_schedules(
            as_of_date=as_of_date,
            grace_period_days=grace_period_days
        )

        total_prods = len(schedules)
        total_windows = 0
        observed_cnt = 0
        partial_cnt = 0
        due_cnt = 0
        overdue_cnt = 0
        not_due_cnt = 0

        for s in schedules:
            for w in s["windows"]:
                total_windows += 1
                st = w["status"]
                if st == WINDOW_STATUS_OBSERVED:
                    observed_cnt += 1
                elif st == WINDOW_STATUS_PARTIALLY_OBSERVED:
                    partial_cnt += 1
                elif st == WINDOW_STATUS_DUE:
                    due_cnt += 1
                elif st == WINDOW_STATUS_OVERDUE:
                    overdue_cnt += 1
                elif st == WINDOW_STATUS_NOT_DUE:
                    not_due_cnt += 1

        return {
            "total_launched_products": total_prods,
            "total_scheduled_windows": total_windows,
            "observed_count": observed_cnt,
            "partially_observed_count": partial_cnt,
            "due_count": due_cnt,
            "overdue_count": overdue_cnt,
            "not_due_count": not_due_cnt,
            "as_of_date": (as_of_date.isoformat() if isinstance(as_of_date, datetime.date) else str(as_of_date)) if as_of_date else datetime.date.today().isoformat()
        }
