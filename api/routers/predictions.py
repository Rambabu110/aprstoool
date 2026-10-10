"""
api/routers/predictions.py — Predictions and Decision Dossier endpoints.
"""
from fastapi import APIRouter, HTTPException, Query
from api.schemas.prediction_calibration import (
    PvRCatalogResponse,
    PvRDossierResponse
)
from api.services.prediction_calibration_service import PredictionCalibrationService

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.get("/catalog", response_model=PvRCatalogResponse)
def get_predictions_catalog(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Returns products with historical predictions and decision maturity status."""
    return PredictionCalibrationService.get_catalog(limit=limit, offset=offset)


@router.get("/dossier/{product_id}", response_model=PvRDossierResponse)
def get_prediction_dossier(product_id: str):
    """
    Returns deep prediction vs reality dossier for a product,
    including frozen decision snapshot, comparisons, and observation schedules.
    """
    dossier = PredictionCalibrationService.get_dossier(product_id)
    if not dossier:
        raise HTTPException(status_code=404, detail=f"No prediction dossier found for product '{product_id}'.")
    return dossier
