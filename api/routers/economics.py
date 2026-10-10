"""
api/routers/economics.py — 15-Factor 3-Scenario Unit Economics evaluation endpoint.
"""
from fastapi import APIRouter, HTTPException, status
from api.schemas.economics import EconomicsResponse
from api.services.economics_service import EconomicsService

router = APIRouter(prefix="/economics", tags=["Economics"])


@router.get(
    "/{product_id}",
    response_model=EconomicsResponse,
    summary="Get 15-Factor Economics Assessment",
    description="Evaluates Conservative, Expected, and Upside unit economics using the authoritative Comprehensive15FactorEconomics engine."
)
def get_economics(product_id: str) -> EconomicsResponse:
    assessment = EconomicsService.get_product_economics(product_id)
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "PRODUCT_NOT_FOUND",
                "message": f"Product with ID '{product_id}' was not found for economics evaluation."
            }
        )
    return assessment
