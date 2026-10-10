"""
api/schemas/health.py — Health and system readiness schemas.
"""
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(default="ok", description="Overall API service health")
    service: str = Field(default="aprs-api", description="Service identifier")
    database: str = Field(description="Database connectivity status: 'ok' or error detail")
    version: str = Field(default="6.0.0", description="APRS software version")
    timestamp: str = Field(description="ISO 8601 UTC timestamp of the health check")
