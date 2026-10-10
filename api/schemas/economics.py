"""
api/schemas/economics.py — 15-factor 3-scenario unit economics response models.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ScenarioDetail(BaseModel):
    scenario_name: str  # "Conservative", "Expected", "Upside"
    planned_msrp: float
    fob_price: float
    landed_cogs: float
    gross_margin_pct: float
    net_profit_pct: float
    worst_case_stress_margin_pct: float
    break_even_units: int
    is_viable: bool
    status: str


class EconomicsResponse(BaseModel):
    product_id: str
    region: str
    currency: str
    composite_score: float
    recommendation: str  # PASS / FAIL
    is_financially_viable: bool
    lead_time_days: int
    trend_half_life_days: int
    lead_time_risk_factor: float
    scenarios: List[ScenarioDetail]
    factor_breakdown: Optional[Dict[str, Any]] = None
