"""
api/routers/outcomes.py — Outcome Ingestion and Observation Foundation Router.
Reuses core.outcome_ingestion and core.outcome_adapters.manual_csv_adapter.
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from core.database import get_connection
from core.outcome_ingestion import (
    VALID_PERIOD_TYPES,
    CORE_METRIC_FIELDS,
    derive_outcome_metrics,
    OutcomeIngestionService
)
from core.observation_scheduler import ObservationScheduler

router = APIRouter(prefix="/outcomes", tags=["outcomes"])


class OutcomeRecord(BaseModel):
    outcome_id: int
    product_id: str
    decision_id: Optional[str] = None
    period_start: str
    period_end: str
    period_type: str
    actual_units_sold: Optional[int] = None
    actual_revenue: Optional[float] = None
    actual_avg_selling_price: Optional[float] = None
    actual_landed_cogs: Optional[float] = None
    actual_contribution_margin: Optional[float] = None
    actual_cm_pct: Optional[float] = None
    actual_returns_count: Optional[int] = None
    actual_rto_count: Optional[int] = None
    actual_ad_spend: Optional[float] = None
    actual_cac: Optional[float] = None
    actual_inventory: Optional[int] = None
    actual_stockout_days: Optional[int] = None
    actual_conversion_rate_pct: Optional[float] = None
    provenance: Optional[str] = None
    data_source: str
    notes: Optional[str] = None
    ingested_at: str


class OutcomesListResponse(BaseModel):
    total: int
    items: List[OutcomeRecord]
    corrections_count: int


class OutcomeSchemaDocumentation(BaseModel):
    period_types: List[str]
    core_metrics: List[str]
    sample_csv_header: str
    invariants: List[str]


class OutcomeValidationRequest(BaseModel):
    product_id: str
    period_start: str
    period_end: str
    period_type: str
    actual_units_sold: Optional[int] = None
    actual_revenue: Optional[float] = None
    actual_landed_cogs: Optional[float] = None
    actual_ad_spend: Optional[float] = None
    actual_returns_count: Optional[int] = None
    actual_rto_count: Optional[int] = None


class OutcomeValidationResponse(BaseModel):
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    derived_metrics: Dict[str, Any]
    derivation_reasons: Dict[str, str]


@router.get("", response_model=OutcomesListResponse)
@router.get("/list", response_model=OutcomesListResponse)
def get_outcomes(limit: int = Query(50, ge=1, le=100)):
    """Returns real observed outcomes from product_outcomes and corrections count."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM outcome_corrections_log")
    corrections_cnt = cur.fetchone()[0]

    cur.execute("""
        SELECT outcome_id, product_id, decision_id, period_start, period_end,
               period_type, actual_units_sold, actual_revenue, actual_avg_selling_price,
               actual_landed_cogs, actual_contribution_margin, actual_cm_pct,
               actual_returns_count, actual_rto_count, actual_ad_spend, actual_cac,
               actual_inventory, actual_stockout_days,
               data_source, notes, ingested_at
        FROM product_outcomes
        ORDER BY outcome_id DESC
        LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()

    items = [
        OutcomeRecord(
            outcome_id=r["outcome_id"],
            product_id=r["product_id"],
            decision_id=r["decision_id"],
            period_start=r["period_start"] or "N/A",
            period_end=r["period_end"] or "N/A",
            period_type=r["period_type"] or "CUSTOM",
            actual_units_sold=r["actual_units_sold"],
            actual_revenue=r["actual_revenue"],
            actual_avg_selling_price=r["actual_avg_selling_price"],
            actual_landed_cogs=r["actual_landed_cogs"],
            actual_contribution_margin=r["actual_contribution_margin"],
            actual_cm_pct=r["actual_cm_pct"],
            actual_returns_count=r["actual_returns_count"],
            actual_rto_count=r["actual_rto_count"],
            actual_ad_spend=r["actual_ad_spend"],
            actual_cac=r["actual_cac"],
            actual_inventory=r["actual_inventory"],
            actual_stockout_days=r["actual_stockout_days"],
            data_source=r["data_source"] or "MANUAL_CSV",
            notes=r["notes"],
            ingested_at=r["ingested_at"] or "N/A"
        )
        for r in rows
    ]

    return OutcomesListResponse(
        total=len(items),
        items=items,
        corrections_count=corrections_cnt
    )


@router.get("/schema", response_model=OutcomeSchemaDocumentation)
def get_outcome_schema():
    """Returns V8 outcome ingestion schema specifications and CSV guidelines."""
    return OutcomeSchemaDocumentation(
        period_types=list(VALID_PERIOD_TYPES),
        core_metrics=list(CORE_METRIC_FIELDS),
        sample_csv_header="product_id,source_product_id,period_start,period_end,period_type,source_record_id,units_sold,revenue,landed_cogs,returns_count,rto_count,ad_spend,inventory,stockout_days,notes",
        invariants=[
            "Frozen Decision Ledger: Historical predictions in decision_ledger are NEVER altered upon outcome ingestion.",
            "Temporal Integrity: period_start must be >= decision_timestamp.",
            "Strict NULL Semantics: Blank numeric cells remain NULL; zero remains 0.",
            "Transparent Derivation: Derived metrics (ASP, CM, CAC) are computed only when raw inputs exist."
        ]
    )


@router.post("/validate", response_model=OutcomeValidationResponse)
def validate_outcome_dry_run(req: OutcomeValidationRequest):
    """
    Validates an outcome record and executes metric derivations in dry-run mode
    WITHOUT mutating SQLite database tables.
    """
    errors: List[str] = []
    warnings: List[str] = []

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT product_id, name FROM master_products WHERE product_id = ?", (req.product_id,))
    prod = cur.fetchone()
    conn.close()

    if not prod:
        errors.append(f"Product '{req.product_id}' not found in master_products.")

    if req.period_type not in VALID_PERIOD_TYPES:
        errors.append(f"Invalid period_type '{req.period_type}'. Must be one of: {', '.join(VALID_PERIOD_TYPES)}")

    # Derive metrics
    payload_dict = req.model_dump()
    derived, reasons = derive_outcome_metrics(payload_dict)

    if req.actual_units_sold is not None and req.actual_units_sold < 0:
        errors.append("actual_units_sold cannot be negative.")

    if req.actual_revenue is not None and req.actual_revenue < 0:
        errors.append("actual_revenue cannot be negative.")

    return OutcomeValidationResponse(
        is_valid=(len(errors) == 0),
        errors=errors,
        warnings=warnings,
        derived_metrics=derived,
        derivation_reasons=reasons
    )


@router.get("/status/{product_id}")
def get_product_observation_status(product_id: str):
    """Returns observation schedule status for a specific product."""
    sched = ObservationScheduler.get_product_schedule(product_id)
    if not sched:
        raise HTTPException(status_code=404, detail=f"No launch schedule found for product '{product_id}'.")
    return sched


class OutcomeIngestRequest(BaseModel):
    product_id: str
    decision_id: Optional[str] = None
    period_start: str
    period_end: str
    period_type: str = "DAY_30"
    source_record_id: Optional[str] = None
    actual_units_sold: Optional[int] = None
    actual_revenue: Optional[float] = None
    actual_avg_selling_price: Optional[float] = None
    actual_landed_cogs: Optional[float] = None
    actual_contribution_margin: Optional[float] = None
    actual_cm_pct: Optional[float] = None
    actual_returns_count: Optional[int] = None
    actual_rto_count: Optional[int] = None
    actual_ad_spend: Optional[float] = None
    actual_cac: Optional[float] = None
    actual_inventory: Optional[int] = None
    actual_stockout_days: Optional[int] = None
    actual_conversion_rate_pct: Optional[float] = None
    provenance: Optional[str] = None
    data_source: str = "MANUAL_CSV"
    notes: Optional[str] = None
    auto_calibrate: bool = True


class OutcomeIngestResponse(BaseModel):
    success: bool
    outcome_id: int
    product_id: str
    decision_id: Optional[str] = None
    calibrated: bool
    calibration_id: Optional[int] = None
    ingested_at: str
    derived_metrics: Dict[str, Any] = {}
    message: str = "Outcome ingested successfully."


@router.post("/ingest", response_model=OutcomeIngestResponse)
def ingest_outcome(req: OutcomeIngestRequest):
    """
    Explicit action endpoint: Ingests a real observed business outcome into product_outcomes.
    Idempotent: Rejects duplicates based on source_record_id or exact period window.
    Deterministically triggers Prediction Calibration if linked to a frozen decision.
    """
    payload = req.model_dump(exclude_unset=True)
    auto_calibrate = payload.pop("auto_calibrate", True)

    # Document provenance / conversion rate in notes if provided
    extra_notes = []
    if req.provenance:
        extra_notes.append(f"provenance={req.provenance}")
    if req.actual_conversion_rate_pct is not None:
        extra_notes.append(f"conversion_rate={req.actual_conversion_rate_pct}%")
    if extra_notes:
        existing_notes = payload.get("notes") or ""
        joined_extra = "; ".join(extra_notes)
        payload["notes"] = f"{existing_notes} [{joined_extra}]".strip() if existing_notes else joined_extra

    # Remove non-schema helper fields from DB payload
    payload.pop("provenance", None)
    payload.pop("actual_conversion_rate_pct", None)

    try:
        res = OutcomeIngestionService.ingest_outcome(payload, auto_calibrate=auto_calibrate)
        return OutcomeIngestResponse(
            success=True,
            outcome_id=res["outcome_id"],
            product_id=res["product_id"],
            decision_id=res.get("decision_id"),
            calibrated=res.get("calibrated", False),
            calibration_id=res.get("calibration_id"),
            ingested_at=res.get("ingested_at", ""),
            derived_metrics=res.get("derived_fields", res.get("derived_metrics", {})),
            message="Outcome observation ingested and calibrated." if res.get("calibrated") else "Outcome observation ingested."
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_OUTCOME_PAYLOAD", "message": str(ve)}
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "INGESTION_ERROR", "message": f"Failed to ingest outcome: {str(exc)}"}
        )

