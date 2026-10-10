"""
api/schemas/prediction_calibration.py — Schemas for Prediction vs Reality & Calibration Reporting.
"""
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field


class DirectionalAccuracyCounts(BaseModel):
    UNDERPREDICTED: int = 0
    OVERPREDICTED: int = 0
    EXACT: int = 0
    UNKNOWN: int = 0


class PortfolioCalibrationSummary(BaseModel):
    total_master_products: int
    products_with_decisions: int
    products_with_outcomes: int
    products_awaiting_observation: int
    products_with_partial_observations: int
    products_with_calibrations: int
    total_decisions: int
    total_outcomes: int
    total_calibrations: int
    total_corrections: int
    total_observed_units: Optional[int] = None
    total_observed_revenue: Optional[float] = None
    demand_bias_mbe: Optional[float] = None
    demand_mae: Optional[float] = None
    demand_mape: Optional[float] = None
    price_bias_mbe: Optional[float] = None
    directional_accuracy_counts: Dict[str, int]
    calibration_reliability: str
    sample_size: int
    structural_readiness: Union[Dict[str, Any], str]
    maturity_summary: Dict[str, Any]


class PvRCatalogItem(BaseModel):
    product_id: str
    name: str
    category: Optional[str] = None
    status: Optional[str] = None
    decision_count: int = 0
    latest_decision_timestamp: Optional[str] = None
    outcome_count: int = 0
    latest_period_end: Optional[str] = None
    calibration_count: int = 0
    latest_directional_accuracy: str
    launch_status: Optional[str] = None
    target_launch_date: Optional[str] = None
    coverage_status: str


class PvRCatalogResponse(BaseModel):
    total: int
    items: List[PvRCatalogItem]


class PvRDossierResponse(BaseModel):
    product_id: str
    exists: bool
    coverage_status: str
    master: Optional[Dict[str, Any]] = None
    current_intelligence: Optional[Dict[str, Any]] = None
    decisions: List[Dict[str, Any]] = Field(default_factory=list)
    outcomes: List[Dict[str, Any]] = Field(default_factory=list)
    calibrations: List[Dict[str, Any]] = Field(default_factory=list)
    comparisons: List[Dict[str, Any]] = Field(default_factory=list)
    observation_schedule: Optional[Dict[str, Any]] = None
