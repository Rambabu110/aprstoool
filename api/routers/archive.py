"""
api/routers/archive.py — Archive and Historical Records Router.
Exposes frozen decisions, team audit logs, defect clusters, and conflict archives from SQLite.
"""
import json
from typing import List, Dict, Any, Optional
from fastapi import APIRouter
from pydantic import BaseModel
from core.database import get_connection

router = APIRouter(prefix="/archive", tags=["archive"])


class DecisionLedgerItem(BaseModel):
    decision_id: int
    product_id: str
    product_name: str
    decision_timestamp: str
    metrics: Dict[str, Any]
    model_version: str
    kill_status: str
    opportunity_score: float
    confidence: float
    policy_version: Optional[str] = "V7.2"


class MeetingAuditLogItem(BaseModel):
    message_id: int
    session_id: str
    timestamp: str
    speaker_name: str
    speaker_role: str
    avatar: Optional[str] = None
    user_prompt: Optional[str] = None
    response_text: Optional[str] = None


class ArchivedProductItem(BaseModel):
    product_id: str
    name: str
    category: Optional[str] = None
    region: Optional[str] = None
    delete_reason: Optional[str] = None
    soft_deleted_at: Optional[str] = None
    planned_msrp: Optional[float] = None
    overall_score: Optional[float] = None


class ArchiveRestoreResponse(BaseModel):
    success: bool
    product_id: str
    restored: bool
    message: str


class ArchiveOverviewResponse(BaseModel):
    decision_ledger_records: List[DecisionLedgerItem]
    meeting_audit_logs: List[MeetingAuditLogItem]
    archived_products: List[ArchivedProductItem] = []
    total_archived_decisions: int
    total_meeting_logs: int
    total_defect_clusters: int
    total_data_conflicts: int
    total_soft_deleted: int = 0


@router.get("/overview", response_model=ArchiveOverviewResponse)
def get_archive_overview():
    """Returns historical archive records including frozen decision ledger, meeting logs, and soft-deleted products."""
    conn = get_connection()
    cur = conn.cursor()

    # Query decision_ledger
    cur.execute("SELECT * FROM decision_ledger ORDER BY decision_id DESC")
    dl_rows = cur.fetchall()

    decisions: List[DecisionLedgerItem] = []
    for r in dl_rows:
        raw_metrics = {
            "predicted_daily_units": r["predicted_daily_units"],
            "predicted_selling_price": r["predicted_selling_price"],
            "predicted_cogs": r["predicted_cogs"],
            "predicted_cm_pct": r["predicted_cm_pct"],
            "predicted_rto_pct": r["predicted_rto_pct"],
            "predicted_cac": r["predicted_cac"],
        }
        product_name = r["product_id"]
        if r["snapshot_payload_json"]:
            try:
                payload = json.loads(r["snapshot_payload_json"])
                product_name = payload.get("product_snapshot", {}).get("name") or payload.get("name") or r["product_id"]
            except Exception:
                pass

        decisions.append(
            DecisionLedgerItem(
                decision_id=r["decision_id"],
                product_id=r["product_id"],
                product_name=product_name,
                decision_timestamp=r["decision_timestamp"] or r["created_at"] or "N/A",
                metrics=raw_metrics,
                model_version=r["model_version"] or "V7.2",
                kill_status=r["frozen_kill_status"] or "SURVIVES",
                opportunity_score=float(r["frozen_score"] or 0.0),
                confidence=float(r["frozen_confidence"] or 80.0),
                policy_version=r["policy_version"] or "V7.2"
            )
        )

    # Query meeting_audit_log
    cur.execute("SELECT * FROM meeting_audit_log ORDER BY message_id DESC")
    meeting_rows = cur.fetchall()
    meetings: List[MeetingAuditLogItem] = []
    for m in meeting_rows:
        meetings.append(
            MeetingAuditLogItem(
                message_id=m["message_id"],
                session_id=m["session_id"] or "N/A",
                timestamp=m["timestamp"] or "N/A",
                speaker_name=m["speaker_name"] or "Agent",
                speaker_role=m["speaker_role"] or "analyst",
                avatar=m["avatar"],
                user_prompt=m["user_prompt"],
                response_text=m["response_text"]
            )
        )

    # Query soft-deleted products
    cur.execute("""
        SELECT product_id, name, category, region, deletion_reason, deleted_at, planned_msrp, overall_score
        FROM master_products
        WHERE is_deleted = 1
        ORDER BY deleted_at DESC
    """)
    archived_rows = cur.fetchall()
    archived_prods = [
        ArchivedProductItem(
            product_id=ap["product_id"],
            name=ap["name"] or ap["product_id"],
            category=ap["category"],
            region=ap["region"],
            delete_reason=ap["deletion_reason"],
            soft_deleted_at=ap["deleted_at"],
            planned_msrp=ap["planned_msrp"],
            overall_score=ap["overall_score"]
        )
        for ap in archived_rows
    ]

    # Counts
    cur.execute("SELECT COUNT(*) FROM defect_clusters")
    defect_cnt = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM data_conflicts")
    conflict_cnt = cur.fetchone()[0]

    conn.close()

    return ArchiveOverviewResponse(
        decision_ledger_records=decisions,
        meeting_audit_logs=meetings,
        archived_products=archived_prods,
        total_archived_decisions=len(decisions),
        total_meeting_logs=len(meetings),
        total_defect_clusters=defect_cnt,
        total_data_conflicts=conflict_cnt,
        total_soft_deleted=len(archived_prods)
    )


@router.post("/{product_id}/restore", response_model=ArchiveRestoreResponse)
def restore_archived_product(product_id: str):
    """Restores a soft-deleted product back into the active catalog."""
    from fastapi import HTTPException
    from core.database import restore_product
    ok = restore_product(product_id)
    if not ok:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to restore product '{product_id}'. Product may not exist or is not marked as soft-deleted."
        )
    return ArchiveRestoreResponse(
        success=True,
        product_id=product_id,
        restored=True,
        message=f"Product '{product_id}' successfully restored to active catalog."
    )


