"""
api/routers/opportunities.py — Opportunity pipeline preserving tri-state logic.
"""
from typing import Optional
from fastapi import APIRouter, Query
from api.schemas.opportunity import OpportunityListResponse
from api.services.opportunity_service import OpportunityService

router = APIRouter(prefix="/opportunities", tags=["Opportunities"])


@router.get(
    "",
    response_model=OpportunityListResponse,
    summary="List Opportunities",
    description="Returns candidate opportunities classified into strict tri-state categories: SURVIVES | KILLED | INSUFFICIENT_EVIDENCE."
)
def list_opportunities(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=25, ge=1, le=100, description="Items per page"),
    tri_state: Optional[str] = Query(default=None, pattern="^(SURVIVES|KILLED|INSUFFICIENT_EVIDENCE)$", description="Filter by tri-state status"),
    region: Optional[str] = Query(default=None, description="Filter by region"),
    category: Optional[str] = Query(default=None, description="Filter by category")
) -> OpportunityListResponse:
    return OpportunityService.get_opportunities(
        page=page,
        page_size=page_size,
        tri_state=tri_state,
        region=region,
        category=category
    )
