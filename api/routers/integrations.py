"""
api/routers/integrations.py — Integrations and marketplace configurations.
"""
from fastapi import APIRouter
from api.schemas.integrations import IntegrationOverviewResponse
from api.services.integrations_service import IntegrationsService

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/overview", response_model=IntegrationOverviewResponse)
def get_integrations_overview():
    """Returns real source health, active marketplace configurations, and LLM cluster status."""
    return IntegrationsService.get_overview()
