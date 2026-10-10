"""
api/services/price_compare_service.py — Business logic for 5-Platform Price Comparison.
Reuses existing core/utils.py implementation (get_top_5_marketplaces, get_wholesaler_info).
"""
from typing import Optional, Dict, Any
from fastapi import HTTPException

from core.database import get_connection
from core.utils import (
    get_top_5_marketplaces,
    get_wholesaler_info,
    normalize_region,
    get_region_currency,
)
from api.schemas.price_compare import (
    PriceCompareResponse,
    MarketplaceListingItem,
    WholesalerContactInfo,
)


class PriceCompareService:
    @staticmethod
    def compare_prices(
        product_id: Optional[str] = None,
        query: Optional[str] = None,
        region: Optional[str] = None,
        planned_msrp: Optional[float] = None,
    ) -> PriceCompareResponse:
        """
        Executes multi-platform price comparison using authoritative core logic.
        Supports both existing catalog products and custom keyword searches.
        """
        product_obj: Dict[str, Any] = {}

        if product_id:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT * FROM master_products WHERE product_id = ?", (product_id,))
            row = cur.fetchone()
            if not row:
                conn.close()
                raise HTTPException(
                    status_code=404,
                    detail={
                        "code": "PRODUCT_NOT_FOUND",
                        "message": f"Product with ID '{product_id}' was not found in the catalog.",
                    },
                )
            product_obj = dict(row)

            # Attach suppliers if available
            cur.execute("SELECT * FROM product_suppliers WHERE product_id = ?", (product_id,))
            product_obj["suppliers"] = [dict(s) for s in cur.fetchall()]
            conn.close()

            # Optional overrides
            if region:
                product_obj["region"] = region
            if planned_msrp is not None and planned_msrp > 0:
                product_obj["planned_msrp"] = planned_msrp

        elif query and query.strip():
            target_region = region.strip() if region and region.strip() else "India"
            benchmark = float(planned_msrp) if planned_msrp and planned_msrp > 0 else 999.0

            product_obj = {
                "name": query.strip(),
                "region": target_region,
                "planned_msrp": benchmark,
                "factory_cogs": round(benchmark * 0.30, 2),
                "sourcing_cluster": "Direct Wholesaler Network",
                "suppliers": [],
            }
        else:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "MISSING_PARAMETERS",
                    "message": "Either 'product_id' or a non-empty 'query' must be provided for price comparison.",
                },
            )

        # Execute existing core business logic
        platforms = get_top_5_marketplaces(product_obj)
        wholesaler_raw = get_wholesaler_info(product_obj)

        if not platforms:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "PLATFORMS_UNAVAILABLE",
                    "message": "Could not determine marketplace comparisons for this region.",
                },
            )

        # Parse prices & arbitrage metrics
        prices = [p["price"] for p in platforms]
        lowest_p = min(prices)
        highest_p = max(prices)
        savings = round(highest_p - lowest_p, 2)
        savings_pct = round((savings / highest_p) * 100, 1) if highest_p > 0 else 0.0

        sym, _ = get_region_currency(product_obj.get("region", "India"))

        # Convert to response models
        marketplaces_out = [
            MarketplaceListingItem(
                platform=p["platform"],
                badge=p["badge"],
                color=p["color"],
                url=p["url"],
                price=float(p["price"]),
                currency=p.get("currency", sym),
                delivery=p["delivery"],
                note=p["note"],
                is_lowest=bool(p.get("is_lowest", False)),
                savings_vs_highest=float(p.get("savings_vs_highest", 0.0)),
            )
            for p in platforms
        ]

        wholesaler_out = None
        if wholesaler_raw:
            wholesaler_out = WholesalerContactInfo(
                factory_name=wholesaler_raw.get("factory_name", "Primary Manufacturing Hub"),
                contact_person=wholesaler_raw.get("contact_person", "Sourcing Manager"),
                contact_details=wholesaler_raw.get("contact_details", ""),
                email=wholesaler_raw.get("email"),
                phone=wholesaler_raw.get("phone"),
                fob_unit_price=wholesaler_raw.get("fob_unit_price"),
                moq_units=wholesaler_raw.get("moq_units"),
                sourcing_cluster=wholesaler_raw.get("sourcing_cluster") or product_obj.get("sourcing_cluster"),
                directory_url=wholesaler_raw.get("directory_url"),
            )

        return PriceCompareResponse(
            product_id=product_obj.get("product_id"),
            product_name=product_obj.get("name", "Unknown Product"),
            region=normalize_region(product_obj.get("region", "India")),
            benchmark_msrp=float(product_obj.get("planned_msrp", 999.0)),
            currency=sym,
            marketplaces=marketplaces_out,
            lowest_price=lowest_p,
            highest_price=highest_p,
            arbitrage_savings=savings,
            arbitrage_pct=savings_pct,
            wholesaler=wholesaler_out,
        )
