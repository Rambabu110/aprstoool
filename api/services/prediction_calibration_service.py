"""
api/services/prediction_calibration_service.py — Direct reuse of PredictionRealityReportService.
"""
from typing import Optional, List, Dict, Any
from core.prediction_reality_report import PredictionRealityReportService
from api.schemas.prediction_calibration import (
    PortfolioCalibrationSummary,
    PvRCatalogItem,
    PvRCatalogResponse,
    PvRDossierResponse
)


class PredictionCalibrationService:
    @staticmethod
    def get_portfolio_summary() -> PortfolioCalibrationSummary:
        raw = PredictionRealityReportService.get_portfolio_summary()
        return PortfolioCalibrationSummary(**raw)

    @staticmethod
    def get_catalog(limit: int = 50, offset: int = 0) -> PvRCatalogResponse:
        raw_list = PredictionRealityReportService.get_products_pvr_catalog(limit=limit + offset)
        sliced = raw_list[offset:offset + limit] if raw_list else []
        items = [
            PvRCatalogItem(
                product_id=r["product_id"],
                name=r.get("name") or "Product",
                category=r.get("category"),
                status=r.get("status"),
                decision_count=r.get("decision_count", 0),
                latest_decision_timestamp=r.get("latest_decision_timestamp"),
                outcome_count=r.get("outcome_count", 0),
                latest_period_end=r.get("latest_period_end"),
                calibration_count=r.get("calibration_count", 0),
                latest_directional_accuracy=r.get("latest_directional_accuracy", "UNKNOWN"),
                launch_status=r.get("launch_status"),
                target_launch_date=r.get("target_launch_date"),
                coverage_status=r.get("coverage_status", "UNKNOWN")
            )
            for r in sliced
        ]
        return PvRCatalogResponse(total=len(items), items=items)

    @staticmethod
    def get_dossier(product_id: str) -> Optional[PvRDossierResponse]:
        raw = PredictionRealityReportService.get_product_pvr_dossier(product_id)
        if not raw or not raw.get("exists"):
            return None
        return PvRDossierResponse(**raw)
