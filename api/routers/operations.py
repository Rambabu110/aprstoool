from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse
from api.schemas.operations import (
    ResearchJobsResponse,
    SupervisorLogsResponse,
    WarRoomDebateResponse,
    WarRoomChatRequest,
    WarRoomChatResponse,
    WarRoomHistoryResponse,
    AlertsListResponse,
    AlertDismissResponse,
    ConflictsListResponse,
    ConflictResolveRequest,
    ConflictResolveResponse,
)
from api.services.operations_service import OperationsService

router = APIRouter(prefix="/operations", tags=["operations"])


@router.get("/jobs", response_model=ResearchJobsResponse)
def get_research_jobs(limit: int = Query(50, ge=1, le=200)):
    """Returns recent and active research runs with metrics and status."""
    return OperationsService.get_research_jobs(limit=limit)


@router.get("/supervisor-logs", response_model=SupervisorLogsResponse)
def get_supervisor_logs(limit: int = Query(50, ge=1, le=200)):
    """Returns real autonomous supervisor events and validations."""
    return OperationsService.get_supervisor_logs(limit=limit)


@router.get("/war-room-debate/{product_id}", response_model=WarRoomDebateResponse)
def get_war_room_debate(product_id: str):
    """
    Executes real War Room 2.0 multi-agent debate (Trend Scout, Defect Analyst,
    Economics Auditor, Marketplace Harvester, Chief Arbiter) and disagreement detection.
    """
    res = OperationsService.get_war_room_debate(product_id)
    if not res:
        raise HTTPException(status_code=404, detail=f"Product '{product_id}' not found in catalog.")
    return res


# ── War Room Interactive Chat & Word Doc Export ────────────────────────────
@router.post("/war-room/chat", response_model=WarRoomChatResponse)
def war_room_chat(request: WarRoomChatRequest):
    """
    Routes user prompt to specialist agents (Sales, Quality, Supplier, Finance, Tech, Secretary)
    via AITeamMeetingRoom and records turns in meeting audit log.
    """
    if not request.user_query or not request.user_query.strip():
        raise HTTPException(status_code=400, detail="Query text cannot be empty.")
    try:
        return OperationsService.send_war_room_chat(
            user_query=request.user_query.strip(),
            target_speaker=request.target_speaker
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/war-room/history", response_model=WarRoomHistoryResponse)
def war_room_history(
    session_id: Optional[str] = Query(None, description="Optional session filter"),
    limit: int = Query(60, ge=1, le=200, description="Max messages to return")
):
    """Returns recorded specialist dialogue turns from meeting_audit_log table."""
    return OperationsService.get_war_room_history(session_id=session_id, limit=limit)


@router.get("/war-room/docx")
def war_room_docx(session_id: Optional[str] = Query(None, description="Optional session filter")):
    """
    Compiles meeting audit log into a formal .docx document (or .txt fallback)
    and returns a downloadable file attachment.
    """
    doc_path = OperationsService.generate_war_room_docx(session_id=session_id)
    if not doc_path or not Path(doc_path).exists():
        raise HTTPException(status_code=404, detail="No meeting log available to generate document.")
    
    path_obj = Path(doc_path)
    if path_obj.suffix.lower() == ".docx":
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        filename = "aprs_war_room_minutes.docx"
    else:
        media_type = "text/plain; charset=utf-8"
        filename = "aprs_war_room_minutes.txt"

    return FileResponse(
        path=str(path_obj),
        media_type=media_type,
        filename=filename,
    )


# ── Operational Alerts & Conflicts ────────────────────────────────────────
@router.get("/alerts", response_model=AlertsListResponse)
def list_active_alerts(limit: int = Query(50, ge=1, le=200)):
    """Returns unacknowledged opportunity alerts from the SSOT database."""
    return OperationsService.get_active_alerts(limit=limit)


@router.post("/alerts/{alert_id}/dismiss", response_model=AlertDismissResponse)
def dismiss_alert_endpoint(alert_id: int):
    """Acknowledges and dismisses an alert in the database."""
    res = OperationsService.dismiss_alert(alert_id=alert_id)
    if not res.success:
        raise HTTPException(status_code=404, detail=f"Alert with ID {alert_id} not found or could not be dismissed.")
    return res


@router.get("/conflicts", response_model=ConflictsListResponse)
def list_data_conflicts(unresolved_only: bool = Query(True)):
    """Surfaces cross-source data discrepancies without hiding them."""
    return OperationsService.get_data_conflicts(unresolved_only=unresolved_only)


@router.post("/conflicts/{conflict_id}/resolve", response_model=ConflictResolveResponse)
def resolve_data_conflict_endpoint(conflict_id: int, request: ConflictResolveRequest = ConflictResolveRequest()):
    """Marks a data conflict as reviewed and resolved with an audit explanation."""
    res = OperationsService.resolve_data_conflict(
        conflict_id=conflict_id,
        resolution_status=request.resolution_status,
        explanation=request.explanation
    )
    if not res.success:
        raise HTTPException(status_code=404, detail=f"Conflict with ID {conflict_id} not found or could not be updated.")
    return res

