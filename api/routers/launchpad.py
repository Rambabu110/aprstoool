"""
api/routers/launchpad.py — Launchpad endpoints for physical launch tracking.
"""
from fastapi import APIRouter
from api.schemas.launchpad import LaunchpadSummaryResponse
from api.services.launchpad_service import LaunchpadService

router = APIRouter(prefix="/launchpad", tags=["launchpad"])


@router.get("/summary", response_model=LaunchpadSummaryResponse)
def get_launchpad_summary():
    """Returns all real launchpad items and status breakdown from SQLite."""
    return LaunchpadService.get_launchpad_summary()
