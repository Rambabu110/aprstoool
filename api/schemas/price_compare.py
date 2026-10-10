"""
api/schemas/price_compare.py — Pydantic schemas for 5-Platform Price Comparison.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class MarketplaceListingItem(BaseModel):
    platform: str = Field(..., description="Platform name, e.g. Amazon India, Flipkart")
    badge: str = Field(..., description="Display badge with emoji")
    color: str = Field(..., description="Brand accent color hex")
    url: str = Field(..., description="Search or product URL")
    price: float = Field(..., description="Platform price in local currency")
    currency: str = Field(..., description="Currency symbol")
    delivery: str = Field(..., description="Delivery promise / tier")
    note: str = Field(..., description="Marketplace context / review note")
    is_lowest: bool = Field(False, description="Flag indicating lowest price amongst platforms")
    savings_vs_highest: float = Field(0.0, description="Arbitrage savings compared to highest price")


class WholesalerContactInfo(BaseModel):
    factory_name: str = Field(..., description="Factory or manufacturer name")
    contact_person: str = Field(..., description="Contact representative")
    contact_details: str = Field("", description="Raw contact string")
    email: Optional[str] = Field(None, description="Direct email if available")
    phone: Optional[str] = Field(None, description="Direct phone/WhatsApp if available")
    fob_unit_price: Optional[str] = Field(None, description="Reported FOB price range")
    moq_units: Optional[int] = Field(None, description="Minimum order quantity")
    sourcing_cluster: Optional[str] = Field(None, description="Industrial hub / city")
    directory_url: Optional[str] = Field(None, description="B2B platform or direct link")


class PriceCompareResponse(BaseModel):
    product_id: Optional[str] = Field(None, description="Catalog product ID if tracked")
    product_name: str = Field(..., description="Product title or search query")
    region: str = Field(..., description="Geographic marketplace region")
    benchmark_msrp: float = Field(..., description="Benchmark retail price")
    currency: str = Field(..., description="Currency symbol")
    marketplaces: List[MarketplaceListingItem] = Field(..., description="Top 5 regional platforms")
    lowest_price: float = Field(..., description="Lowest price among the 5 platforms")
    highest_price: float = Field(..., description="Highest price among the 5 platforms")
    arbitrage_savings: float = Field(..., description="Absolute difference between highest and lowest")
    arbitrage_pct: float = Field(..., description="Arbitrage savings percentage")
    wholesaler: Optional[WholesalerContactInfo] = Field(None, description="Sourcing & factory partner details")
