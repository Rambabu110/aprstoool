"""
api/schemas — Pydantic v2 typed request/response models.
"""
from api.schemas.common import ErrorDetail, ErrorResponse
from api.schemas.health import HealthResponse
from api.schemas.dashboard import DashboardResponse, DashboardStats, ScannerPipelineStatus
from api.schemas.product import ProductSummary, ProductListResponse, ProductDetailResponse
from api.schemas.trend import TrendItem, TrendListResponse
from api.schemas.opportunity import OpportunityItem, OpportunityListResponse
from api.schemas.economics import EconomicsResponse, ScenarioDetail

__all__ = [
    "ErrorDetail",
    "ErrorResponse",
    "HealthResponse",
    "DashboardResponse",
    "DashboardStats",
    "ScannerPipelineStatus",
    "ProductSummary",
    "ProductListResponse",
    "ProductDetailResponse",
    "TrendItem",
    "TrendListResponse",
    "OpportunityItem",
    "OpportunityListResponse",
    "EconomicsResponse",
    "ScenarioDetail",
]
