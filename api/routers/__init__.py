"""
api/routers — FastAPI endpoints organized by business domain.
"""
from api.routers.health import router as health_router
from api.routers.dashboard import router as dashboard_router
from api.routers.products import router as products_router
from api.routers.trends import router as trends_router
from api.routers.opportunities import router as opportunities_router
from api.routers.economics import router as economics_router
from api.routers.operations import router as operations_router
from api.routers.db_explorer import router as db_explorer_router
from api.routers.launchpad import router as launchpad_router
from api.routers.calibration import router as calibration_router
from api.routers.predictions import router as predictions_router
from api.routers.integrations import router as integrations_router
from api.routers.telemetry import router as telemetry_router
from api.routers.scheduler import router as scheduler_router
from api.routers.outcomes import router as outcomes_router
from api.routers.archive import router as archive_router
from api.routers.price_compare import router as price_compare_router

__all__ = [
    "health_router",
    "dashboard_router",
    "products_router",
    "trends_router",
    "opportunities_router",
    "economics_router",
    "operations_router",
    "db_explorer_router",
    "launchpad_router",
    "calibration_router",
    "predictions_router",
    "integrations_router",
    "telemetry_router",
    "scheduler_router",
    "outcomes_router",
    "archive_router",
    "price_compare_router",
]
