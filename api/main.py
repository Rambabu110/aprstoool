"""
api/main.py — APRS V6 Pro FastAPI Application Entrypoint.

Architectural Guarantees:
1. Direct, completely free product access. Zero auth requirements, zero login redirects.
2. Thin API boundary wrapping authoritative Python logic and SQLite SSOT.
3. Clean local CORS configured for the Next.js frontend (http://localhost:3000).
4. Standardized, safe JSON error formats without secret or stack trace leakage.
5. Does not automatically launch the 24/7 scraping daemon on startup.
"""
import os
import sys
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Ensure project root is in sys.path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from api.routers import (
    health_router,
    dashboard_router,
    products_router,
    trends_router,
    opportunities_router,
    economics_router,
    operations_router,
    db_explorer_router,
    launchpad_router,
    calibration_router,
    predictions_router,
    integrations_router,
    telemetry_router,
    scheduler_router,
    outcomes_router,
    archive_router,
    price_compare_router,
)
from api.schemas.common import ErrorDetail, ErrorResponse

logger = logging.getLogger("aprs.api")
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(name)s %(levelname)s — %(message)s"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager.
    Initializes non-destructive resources at startup and cleans up on shutdown.
    Avoids launching background scraping loops or AI tasks at API startup.
    """
    logger.info("⚡ APRS V6 Pro FastAPI Gateway initializing...")
    logger.info("   - SQLite SSOT: data/research_engine.db")
    logger.info("   - Access Model: Free direct access (No authentication required)")
    logger.info("   - OpenAPI Documentation: /docs")
    yield
    logger.info("⚡ APRS V6 Pro FastAPI Gateway shutdown complete.")


def create_app() -> FastAPI:
    """Factory creating and configuring the FastAPI instance."""
    app = FastAPI(
        title="APRS V6 Pro API",
        description=(
            "Autonomous Product Research System (APRS V6 Pro) REST API Gateway. "
            "Exposes high-performance endpoints for Product Intelligence, Trends, "
            "Unit Economics, and Discovery Pipeline to the Next.js frontend."
        ),
        version="6.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan
    )

    # ── CORS Middleware ──────────────────────────────────────────────────────────
    # Default to Next.js development server; can be extended via APRS_CORS_ORIGINS env
    custom_origins = os.getenv("APRS_CORS_ORIGINS", "")
    allowed_origins = [
        origin.strip() for origin in custom_origins.split(",") if origin.strip()
    ] if custom_origins else [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,  # Unauthenticated direct access
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Accept", "X-Requested-With"],
    )

    # ── Standardized Exception Handlers ──────────────────────────────────────────
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail:
            err_code = detail.get("code", "HTTP_ERROR")
            err_msg = detail.get("message", "An HTTP error occurred.")
            err_details = detail.get("details")
        else:
            err_code = f"HTTP_{exc.status_code}"
            err_msg = str(detail)
            err_details = None

        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": err_code, "message": err_msg, "details": err_details}}
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        safe_errors = []
        for err in exc.errors():
            loc = " -> ".join(str(l) for l in err.get("loc", []))
            safe_errors.append({"field": loc, "issue": err.get("msg")})

        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "The request contained invalid or unparseable parameters.",
                    "details": safe_errors
                }
            }
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled server error on {request.method} {request.url.path}: {exc}", exc_info=True)
        # Redact raw internal traces from API consumer
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An internal server error occurred while processing the request.",
                    "details": None
                }
            }
        )

    # ── Router Registration ──────────────────────────────────────────────────────
    app.include_router(health_router)
    app.include_router(dashboard_router)
    app.include_router(products_router)
    app.include_router(trends_router)
    app.include_router(opportunities_router)
    app.include_router(economics_router)
    app.include_router(operations_router)
    app.include_router(db_explorer_router)
    app.include_router(launchpad_router)
    app.include_router(calibration_router)
    app.include_router(predictions_router)
    app.include_router(integrations_router)
    app.include_router(telemetry_router)
    app.include_router(scheduler_router)
    app.include_router(outcomes_router)
    app.include_router(archive_router)
    app.include_router(price_compare_router)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=True)
