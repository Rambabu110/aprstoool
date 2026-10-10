"""
api/schemas/dashboard.py — Dashboard data structures backed by real database metrics.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class DashboardStats(BaseModel):
    total_products: int = Field(description="Total products tracked in SSOT")
    trending_today: int = Field(description="Products identified as trending today")
    my_shortlist: int = Field(description="Total products shortlisted by user")
    ai_recommended: int = Field(description="Products verified and recommended by AI swarm")
    total_niches: int = Field(description="Total active dynamic discovery niches")
    active_sources: int = Field(description="Total active trend & catalog sources")
    passed_products: int = Field(description="Products passing investment criteria")


class SourceHealthItem(BaseModel):
    source_name: str
    status: str  # "OK", "Delayed", "Offline"
    last_checked: Optional[str] = None
    success_rate_pct: Optional[float] = None


class AIModelStatusItem(BaseModel):
    name: str
    role: str
    provider: str
    status: str  # "Running", "Token limit reached", "API key expired", "Not configured"
    affects: Optional[str] = None


class DailyDiscoveryItem(BaseModel):
    date: str
    count: int


class TopTrendingItem(BaseModel):
    rank: int
    product_id: str
    name: str
    score: float
    source: Optional[str] = None
    price: Optional[float] = None


class ScannerPipelineStatus(BaseModel):
    status: str  # "Running", "Paused", "Idle"
    current_niche: Optional[str] = None
    progress_pct: Optional[int] = 0
    scanned_count: int = 0
    new_found: int = 0
    gates_run: int = 0
    errors: int = 0
    next_run_in_min: Optional[int] = None


class DashboardResponse(BaseModel):
    stats: DashboardStats
    scanner_status: ScannerPipelineStatus
    ai_models_status: List[AIModelStatusItem]
    source_health: List[SourceHealthItem]
    products_discovered_7d: List[DailyDiscoveryItem]
    top_trending: List[TopTrendingItem]
    timestamp: str
