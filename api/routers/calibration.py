"""
api/routers/calibration.py — Calibration and Model Performance endpoints.
"""
from fastapi import APIRouter, Query
from api.schemas.prediction_calibration import (
    PortfolioCalibrationSummary,
    PvRCatalogResponse
)
from api.services.prediction_calibration_service import PredictionCalibrationService

router = APIRouter(prefix="/calibration", tags=["calibration"])


@router.get("/summary", response_model=PortfolioCalibrationSummary)
@router.get("/portfolio-summary", response_model=PortfolioCalibrationSummary)
def get_calibration_summary():
    """Returns closed-loop portfolio calibration summary, error metrics, and bias statistics."""
    return PredictionCalibrationService.get_portfolio_summary()


@router.get("/products", response_model=PvRCatalogResponse)
def get_calibrated_products(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Returns catalog products with prediction vs reality coverage status."""
    return PredictionCalibrationService.get_catalog(limit=limit, offset=offset)
