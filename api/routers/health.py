"""
api/routers/health.py — System health and readiness endpoint.
Strictly read-only; never exposes API keys, paths, or secrets.
"""
import datetime
from fastapi import APIRouter
from core.database import get_connection
from api.schemas.health import HealthResponse

router = APIRouter(tags=["System Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="API Health Check",
    description="Returns service status and tests SQLite database connectivity with a safe read-only probe."
)
def get_health() -> HealthResponse:
    db_status = "ok"
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        conn.close()
    except Exception as e:
        db_status = f"unhealthy: {type(e).__name__}"

    return HealthResponse(
        status="ok" if db_status == "ok" else "degraded",
        service="aprs-api",
        database=db_status,
        version="6.0.0",
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
