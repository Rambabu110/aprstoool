"""
api/services/launchpad_service.py — Service for retrieving real Launchpad items from SQLite.
"""
from typing import List, Dict, Optional
from core.database import get_connection
from api.schemas.launchpad import LaunchpadItem, LaunchpadSummaryResponse


class LaunchpadService:
    @staticmethod
    def get_launchpad_summary() -> LaunchpadSummaryResponse:
        conn = get_connection()
        cur = conn.cursor()

        # Query launchpad items joined with master_products
        cur.execute("""
            SELECT l.item_id, l.product_id, l.product_name, l.target_launch_date,
                   l.target_moq, l.target_fob, l.confirmed_factory_name,
                   l.sample_ordered, l.sample_approved, l.qc_aql_standard,
                   l.compliance_checklist_passed, l.purchase_order_generated,
                   l.launch_status, l.updated_at,
                   m.category, m.region, m.planned_msrp, m.landed_cogs, m.gross_margin_pct
            FROM launchpad_items l
            LEFT JOIN master_products m ON l.product_id = m.product_id
            ORDER BY l.item_id ASC
        """)
        rows = cur.fetchall()
        conn.close()

        items: List[LaunchpadItem] = []
        status_counts: Dict[str, int] = {}

        for r in rows:
            st = r["launch_status"] or "UNKNOWN"
            status_counts[st] = status_counts.get(st, 0) + 1

            items.append(
                LaunchpadItem(
                    item_id=r["item_id"],
                    product_id=r["product_id"],
                    product_name=r["product_name"] or "Product",
                    launch_status=st,
                    target_launch_date=r["target_launch_date"],
                    target_moq=r["target_moq"] or 0,
                    target_fob=float(r["target_fob"] or 0.0),
                    confirmed_factory_name=r["confirmed_factory_name"],
                    sample_ordered=bool(r["sample_ordered"]),
                    sample_approved=bool(r["sample_approved"]),
                    qc_aql_standard=r["qc_aql_standard"],
                    compliance_checklist_passed=bool(r["compliance_checklist_passed"]),
                    purchase_order_generated=bool(r["purchase_order_generated"]),
                    updated_at=r["updated_at"] or "N/A",
                    category=r["category"],
                    region=r["region"],
                    planned_msrp=r["planned_msrp"],
                    landed_cogs=r["landed_cogs"],
                    gross_margin_pct=r["gross_margin_pct"],
                )
            )

        return LaunchpadSummaryResponse(
            total_items=len(items),
            status_counts=status_counts,
            items=items
        )
