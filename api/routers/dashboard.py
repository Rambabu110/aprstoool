"""
api/routers/dashboard.py — Dashboard metrics and real-time status summary.
"""
from fastapi import APIRouter
from api.schemas.dashboard import DashboardResponse
from api.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get(
    "",
    response_model=DashboardResponse,
    summary="Dashboard Overview",
    description="Returns verified aggregate counts, AI model readiness, source health, and recent discoveries."
)
def get_dashboard() -> DashboardResponse:
    return DashboardService.get_dashboard_data()
