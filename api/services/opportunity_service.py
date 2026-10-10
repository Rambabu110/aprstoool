"""
api/services/opportunity_service.py — Opportunity pipeline and tri-state gate evaluation.
Preserves strict tri-state logic: SURVIVES | KILLED | INSUFFICIENT_EVIDENCE.
Never collapses into a binary state.
"""
from typing import Optional, List, Dict, Any
from core.database import get_connection, get_gate_status
from api.schemas.opportunity import OpportunityItem, OpportunityListResponse


class OpportunityService:
    @staticmethod
    def get_opportunities(
        page: int = 1,
        page_size: int = 25,
        tri_state: Optional[str] = None,
        region: Optional[str] = None,
        category: Optional[str] = None
    ) -> OpportunityListResponse:
        """
        Retrieves products in the research pipeline classified by tri-state outcome:
        - SURVIVES: Passed all evaluated gates / consensus pass
        - KILLED: Explicitly rejected by arbiter, kill switch, or failed gate
        - INSUFFICIENT_EVIDENCE: Pending evaluation, gates in progress, or unverified
        """
        page = max(1, page)
        page_size = min(100, max(1, page_size))
        offset = (page - 1) * page_size

        conn = get_connection()
        cur = conn.cursor()

        # Query all active products with gate information
        where_clauses = ["is_deleted = 0"]
        params: List[Any] = []

        if region:
            where_clauses.append("region = ?")
            params.append(region)

        if category:
            where_clauses.append("category = ?")
            params.append(category)

        where_sql = " AND ".join(where_clauses)

        cur.execute(f"""
            SELECT product_id, name, category, region, planned_msrp,
                   status, consensus_status, human_override_status,
                   overall_score, action_plan, ai_rejection_reason, created_at
            FROM master_products
            WHERE {where_sql}
            ORDER BY overall_score DESC, created_at DESC
        """, params)
        all_rows = cur.fetchall()

        # Fetch all gate statuses in bulk
        cur.execute("""
            SELECT product_id, gate_number, status
            FROM product_gate_progress
            ORDER BY gate_number ASC
        """)
        gate_rows = cur.fetchall()
        conn.close()

        # Map gates per product
        gates_by_product: Dict[str, Dict[str, str]] = {}
        max_gate_by_product: Dict[str, int] = {}
        for gr in gate_rows:
            pid = gr["product_id"]
            if pid not in gates_by_product:
                gates_by_product[pid] = {}
                max_gate_by_product[pid] = 0
            g_num = gr["gate_number"]
            g_st = gr["status"]
            gates_by_product[pid][f"Gate {g_num}"] = g_st
            if g_st == "PASS" and g_num > max_gate_by_product[pid]:
                max_gate_by_product[pid] = g_num

        classified_items: List[OpportunityItem] = []
        survives_cnt = 0
        killed_cnt = 0
        insufficient_cnt = 0

        for r in all_rows:
            pid = r["product_id"]
            st = (r["human_override_status"] or r["status"] or "PENDING").upper()
            c_st = (r["consensus_status"] or "PENDING").upper()
            prod_gates = gates_by_product.get(pid, {})
            current_gate_num = max_gate_by_product.get(pid, 1)

            # Determine Tri-State
            if st == "PASS" or c_st == "CONSENSUS_PASS":
                item_tri_state = "SURVIVES"
                survives_cnt += 1
            elif st == "FAIL" or c_st == "CONSENSUS_FAIL" or any(s == "FAIL" for s in prod_gates.values()):
                item_tri_state = "KILLED"
                killed_cnt += 1
            else:
                item_tri_state = "INSUFFICIENT_EVIDENCE"
                insufficient_cnt += 1

            if tri_state and item_tri_state != tri_state.upper():
                continue

            classified_items.append(OpportunityItem(
                product_id=pid,
                name=r["name"] or "Unnamed Product",
                category=r["category"],
                region=r["region"],
                planned_msrp=r["planned_msrp"],
                tri_state_status=item_tri_state,
                current_gate=current_gate_num,
                overall_score=r["overall_score"],
                action_plan=r["action_plan"],
                arbiter_verdict=c_st if c_st != "PENDING" else None,
                rejection_reason=r["ai_rejection_reason"],
                gates_summary=prod_gates,
                created_at=r["created_at"]
            ))

        total_filtered = len(classified_items)
        paginated_items = classified_items[offset:offset + page_size]
        has_next = (offset + len(paginated_items)) < total_filtered

        return OpportunityListResponse(
            items=paginated_items,
            total=total_filtered,
            survives_count=survives_cnt,
            killed_count=killed_cnt,
            insufficient_evidence_count=insufficient_cnt,
            page=page,
            page_size=page_size,
            has_next=has_next
        )
