"""
api/routers/trends.py — Real trending signals query endpoint.
"""
from typing import Optional
from fastapi import APIRouter, Query
from api.schemas.trend import TrendListResponse
from api.services.trend_service import TrendService

router = APIRouter(prefix="/trends", tags=["Trending"])


@router.get(
    "",
    response_model=TrendListResponse,
    summary="List Trending Signals",
    description="Returns real detected trend signals from the SSOT database without triggering expensive external requests."
)
def list_trends(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=25, ge=1, le=100, description="Items per page"),
    region: Optional[str] = Query(default=None, description="Filter by region (e.g. India, USA, Europe)"),
    platform: Optional[str] = Query(default=None, description="Filter by platform/source (e.g. google_trends, amazon, tiktok)"),
    search: Optional[str] = Query(default=None, description="Keyword search filter"),
    status: str = Query(default="ACTIVE", description="Signal status: ACTIVE or ARCHIVED"),
    sort_by: str = Query(default="velocity_score", description="Sort field: velocity_score, search_volume_est, created_at"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$", description="Sort order: asc or desc")
) -> TrendListResponse:
    return TrendService.get_trends(
        page=page,
        page_size=page_size,
        region=region,
        platform=platform,
        search=search,
        status=status,
        sort_by=sort_by,
        sort_order=sort_order
    )
