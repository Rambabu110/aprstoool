"""
api/routers/telemetry.py — Telemetry and Keepa status endpoints.
"""
from fastapi import APIRouter
from api.schemas.integrations import KeepaTelemetryStatus
from api.services.integrations_service import IntegrationsService

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


@router.get("/keepa/status", response_model=KeepaTelemetryStatus)
@router.get("/keepa", response_model=KeepaTelemetryStatus)
def get_keepa_status():
    """Returns real Keepa integration configuration status and price stability telemetry metrics."""
    return IntegrationsService.get_keepa_status()
