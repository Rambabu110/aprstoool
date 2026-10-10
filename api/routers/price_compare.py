"""
api/routers/price_compare.py — Multi-marketplace price compare and arbitrage routes.
"""
from typing import Optional
from fastapi import APIRouter, Query

from api.schemas.price_compare import PriceCompareResponse
from api.services.price_compare_service import PriceCompareService

router = APIRouter(prefix="/price-compare", tags=["Price Comparison"])


@router.get(
    "",
    response_model=PriceCompareResponse,
    summary="5-Platform Price Comparison",
    description=(
        "Compares live market pricing across the top 5 regional e-commerce platforms, "
        "identifies the lowest price, calculates arbitrage savings, and returns verified "
        "wholesaler sourcing details. Supports tracked product IDs or custom queries."
    ),
)
def compare_prices(
    product_id: Optional[str] = Query(None, description="Catalog product ID"),
    query: Optional[str] = Query(None, description="Custom product name or keyword search"),
    region: Optional[str] = Query(None, description="Regional market (India, USA, GCC_MiddleEast, UK, Europe)"),
    planned_msrp: Optional[float] = Query(None, description="Benchmark MSRP in local currency"),
) -> PriceCompareResponse:
    return PriceCompareService.compare_prices(
        product_id=product_id,
        query=query,
        region=region,
        planned_msrp=planned_msrp,
    )
