"""
api/schemas/product.py — Product listing and dossier schemas.
"""
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field


class GateProgressItem(BaseModel):
    gate_number: int
    status: str
    completed_at: Optional[str] = None
    completed_by: Optional[str] = None
    blocked_reason: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class MultiPlatformListingItem(BaseModel):
    platform: str
    title: Optional[str] = None
    url: Optional[str] = None
    price: Optional[float] = None
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    in_stock: Optional[bool] = None


class ProductSummary(BaseModel):
    product_id: str
    name: str
    category: Optional[str] = None
    region: Optional[str] = "India"
    planned_msrp: Optional[float] = None
    landed_cogs: Optional[float] = None
    gross_margin_pct: Optional[float] = None
    net_profit_pct: Optional[float] = None
    status: Optional[str] = None
    overall_score: Optional[float] = None
    is_shortlisted: bool = False
    ai_confidence: Optional[float] = None
    gates_passed: int = 0
    total_gates: int = 6
    created_at: Optional[str] = None
    trend_source: Optional[str] = None


class ProductListResponse(BaseModel):
    items: List[ProductSummary]
    total: int
    page: int
    page_size: int
    has_next: bool


class ProductDetailResponse(BaseModel):
    product_id: str
    name: str
    category: Optional[str] = None
    region: Optional[str] = None
    planned_msrp: Optional[float] = None
    landed_cogs: Optional[float] = None
    gross_margin_pct: Optional[float] = None
    estimated_cac: Optional[float] = None
    net_profit_pct: Optional[float] = None
    worst_case_stress_margin_pct: Optional[float] = None
    status: Optional[str] = None
    overall_score: Optional[float] = None
    consensus_status: Optional[str] = None
    action_plan: Optional[str] = None
    sourcing_cluster: Optional[str] = None
    marketplace_url: Optional[str] = None
    competitor_3star_flaws: Optional[str] = None
    upgrade_v2_engineering: Optional[str] = None
    bsr_rank: Optional[int] = None
    estimated_daily_units: Optional[int] = None
    human_override_status: Optional[str] = None
    first_discovered_date: Optional[str] = None
    last_evaluated_date: Optional[str] = None
    keepa_price_stability: Optional[float] = None
    helium_monthly_revenue: Optional[float] = None
    factory_cogs: Optional[float] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    ai_rejection_reason: Optional[str] = None
    ai_reasoning: Optional[str] = None
    ai_confidence: Optional[float] = None
    is_shortlisted: bool = False
    gates: List[GateProgressItem] = []
    listings: List[MultiPlatformListingItem] = []
    defects: Optional[List[Dict[str, Any]]] = None
    economics_summary: Optional[Dict[str, Any]] = None


class ProductRefreshResponse(BaseModel):
    success: bool
    product_id: str
    refreshed_at: str
    overall_score: Optional[float] = None
    kill_status: Optional[str] = None
    evidence_count: int = 0
    recommendation: Optional[str] = None
    error: Optional[str] = None


# ── Supplier Directory Schemas ─────────────────────────────────────────────
class SupplierDirectoryItem(BaseModel):
    supplier_id: int
    product_id: str
    product_name: str
    region: str
    factory_name: str
    supplier_type: Optional[str] = None
    industrial_address: Optional[str] = None
    contact_person: Optional[str] = None
    contact_details: Optional[str] = None
    platform_profile_url: Optional[str] = None
    fob_unit_price: Optional[str] = None
    moq_units: Optional[int] = None
    sample_cost_leadtime: Optional[str] = None
    certifications: Optional[str] = None


class SupplierDirectoryResponse(BaseModel):
    total: int
    suppliers: List[SupplierDirectoryItem]


# ── Watchlist & Shortlist Mutation Schemas ────────────────────────────────
class WatchlistAddRequest(BaseModel):
    priority_status: str = "WATCH"
    notes: str = ""


class WatchlistMutationResponse(BaseModel):
    product_id: str
    in_watchlist: bool
    status: str
    message: str


class ShortlistToggleRequest(BaseModel):
    is_shortlisted: bool = True


class ShortlistToggleResponse(BaseModel):
    product_id: str
    is_shortlisted: bool
    message: str


