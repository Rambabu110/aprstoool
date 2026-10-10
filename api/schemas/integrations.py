"""
api/schemas/integrations.py — Schemas for Integrations, Marketplaces, and Telemetry.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class SourceHealthItem(BaseModel):
    source_id: int
    source_name: str
    data_type: str
    last_successful_fetch: Optional[str] = None
    failure_count: int = 0
    freshness_status: str
    provenance_status: str = "UNVERIFIED"
    is_mock: bool = False
    status_message: Optional[str] = None
    response_time_ms: float = 0.0
    updated_at: str


class MarketplaceConfigItem(BaseModel):
    config_id: int
    marketplace_name: str
    region: str
    base_url: str
    is_active: bool
    priority: int
    success_rate: float
    last_scraped_at: Optional[str] = None
    anti_bot_level: str
    extraction_prompt: Optional[str] = None


class LLMClusterInfo(BaseModel):
    nim_keys_configured: int
    nim_base_url: str
    models_configured: Dict[str, str]
    roles_configured: List[str]
    gemini_fallback_configured: bool
    google_trends_enabled: bool
    local_ollama_present: bool = False  # Per instructions, Ollama is not installed/used


class IntegrationOverviewResponse(BaseModel):
    sources: List[SourceHealthItem]
    marketplaces: List[MarketplaceConfigItem]
    llm_cluster: LLMClusterInfo


class KeepaTelemetryStatus(BaseModel):
    api_configured: bool
    status_message: str
    supported_domains: Dict[str, int]
    monitored_products_count: int
    avg_price_stability_pct: Optional[float] = None
    products_with_bsr_count: int
