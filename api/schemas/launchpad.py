"""
api/schemas/launchpad.py — Schemas for Launchpad items and pipeline stages.
"""
from typing import List, Optional, Dict
from pydantic import BaseModel


class LaunchpadItem(BaseModel):
    item_id: int
    product_id: str
    product_name: str
    launch_status: str
    target_launch_date: Optional[str] = None
    target_moq: int = 0
    target_fob: float = 0.0
    confirmed_factory_name: Optional[str] = None
    sample_ordered: bool = False
    sample_approved: bool = False
    qc_aql_standard: Optional[str] = None
    compliance_checklist_passed: bool = False
    purchase_order_generated: bool = False
    updated_at: str
    # Enriched from master_products
    category: Optional[str] = None
    region: Optional[str] = None
    planned_msrp: Optional[float] = None
    landed_cogs: Optional[float] = None
    gross_margin_pct: Optional[float] = None


class LaunchpadSummaryResponse(BaseModel):
    total_items: int
    status_counts: Dict[str, int]
    items: List[LaunchpadItem]
