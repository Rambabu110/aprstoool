"""
api/schemas/trend.py — Real trending signals schema.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class TrendItem(BaseModel):
    signal_id: Optional[int] = None
    keyword: str
    region: Optional[str] = None
    source: Optional[str] = None
    velocity_score: Optional[float] = None
    search_volume_indicator: Optional[str] = None
    trend_type: Optional[str] = None
    first_detected_at: Optional[str] = None
    last_updated_at: Optional[str] = None
    is_active: bool = True


class TrendListResponse(BaseModel):
    items: List[TrendItem]
    total: int
    page: int
    page_size: int
    has_next: bool
