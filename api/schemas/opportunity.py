"""
api/schemas/opportunity.py — Opportunities pipeline schemas preserving tri-state logic.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class OpportunityItem(BaseModel):
    product_id: str
    name: str
    category: Optional[str] = None
    region: Optional[str] = None
    planned_msrp: Optional[float] = None
    tri_state_status: str = Field(description="Strict tri-state: SURVIVES | KILLED | INSUFFICIENT_EVIDENCE")
    current_gate: int
    overall_score: Optional[float] = None
    action_plan: Optional[str] = None
    arbiter_verdict: Optional[str] = None
    rejection_reason: Optional[str] = None
    gates_summary: Dict[str, str] = Field(default_factory=dict)
    created_at: Optional[str] = None


class OpportunityListResponse(BaseModel):
    items: List[OpportunityItem]
    total: int
    survives_count: int
    killed_count: int
    insufficient_evidence_count: int
    page: int
    page_size: int
    has_next: bool
