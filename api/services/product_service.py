"""
api/services/product_service.py — Product catalog queries, pagination, and dossier assembly.
Uses SQLite SSOT directly; avoids mutating data or calling external APIs on page reads.
"""
import os
import json
import datetime
from typing import Optional, List, Dict, Any, Tuple
from core.database import (
    get_connection,
    get_gate_status,
    get_defect_clusters,
    get_economics_assessments
)
from api.schemas.product import (
    ProductSummary,
    ProductListResponse,
    ProductDetailResponse,
    ProductRefreshResponse,
    GateProgressItem,
    MultiPlatformListingItem,
    SupplierDirectoryItem,
    SupplierDirectoryResponse,
    WatchlistMutationResponse,
    ShortlistToggleResponse,
)



class ProductService:
    @staticmethod
    def get_products(
        page: int = 1,
        page_size: int = 25,
        search: Optional[str] = None,
        category: Optional[str] = None,
        region: Optional[str] = None,
        is_shortlisted: Optional[bool] = None,
        status: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> ProductListResponse:
        """
        Retrieves paginated, filtered products from master_products table.
        """
        page = max(1, page)
        page_size = min(100, max(1, page_size))
        offset = (page - 1) * page_size

        conn = get_connection()
        cur = conn.cursor()

        # Build query dynamically with parameter binding
        where_clauses = ["is_deleted = 0"]
        params: List[Any] = []

        if search:
            search_param = f"%{search.strip()}%"
            where_clauses.append("(name LIKE ? OR category LIKE ? OR product_id LIKE ?)")
            params.extend([search_param, search_param, search_param])

        if category:
            where_clauses.append("category = ?")
            params.append(category)

        if region:
            where_clauses.append("region = ?")
            params.append(region)

        if is_shortlisted is not None:
            where_clauses.append("is_shortlisted = ?")
            params.append(1 if is_shortlisted else 0)

        if status:
            where_clauses.append("status = ?")
            params.append(status.upper())

        where_sql = " AND ".join(where_clauses)

        # Get total count
        count_sql = f"SELECT COUNT(*) FROM master_products WHERE {where_sql}"
        cur.execute(count_sql, params)
        total = cur.fetchone()[0]

        # Valid sort columns
        allowed_sorts = {
            "created_at": "created_at",
            "overall_score": "overall_score",
            "planned_msrp": "planned_msrp",
            "name": "name",
            "category": "category",
            "bsr_rank": "bsr_rank"
        }
        order_col = allowed_sorts.get(sort_by, "created_at")
        order_dir = "ASC" if sort_order.lower() == "asc" else "DESC"

        # Query items
        query_sql = f"""
            SELECT product_id, name, category, region, planned_msrp, landed_cogs,
                   gross_margin_pct, net_profit_pct, status, overall_score,
                   is_shortlisted, ai_confidence, created_at, trend_source
            FROM master_products
            WHERE {where_sql}
            ORDER BY {order_col} {order_dir}
            LIMIT ? OFFSET ?
        """
        cur.execute(query_sql, params + [page_size, offset])
        rows = cur.fetchall()

        # For gate counts, fetch summary
        product_ids = [r["product_id"] for r in rows]
        gates_map: Dict[str, int] = {}
        if product_ids:
            placeholders = ",".join("?" for _ in product_ids)
            gate_sql = f"""
                SELECT product_id, COUNT(*) as passed_cnt
                FROM product_gate_progress
                WHERE product_id IN ({placeholders}) AND status = 'PASS'
                GROUP BY product_id
            """
            cur.execute(gate_sql, product_ids)
            for gr in cur.fetchall():
                gates_map[gr["product_id"]] = gr["passed_cnt"]

        conn.close()

        items = [
            ProductSummary(
                product_id=r["product_id"],
                name=r["name"] or "Unnamed Product",
                category=r["category"],
                region=r["region"] or "India",
                planned_msrp=r["planned_msrp"],
                landed_cogs=r["landed_cogs"],
                gross_margin_pct=r["gross_margin_pct"],
                net_profit_pct=r["net_profit_pct"],
                status=r["status"],
                overall_score=r["overall_score"],
                is_shortlisted=bool(r["is_shortlisted"]),
                ai_confidence=r["ai_confidence"],
                gates_passed=gates_map.get(r["product_id"], 0),
                total_gates=6,
                created_at=r["created_at"],
                trend_source=r["trend_source"]
            )
            for r in rows
        ]

        has_next = (offset + len(items)) < total

        return ProductListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_next=has_next
        )

    @staticmethod
    def get_product_detail(product_id: str) -> Optional[ProductDetailResponse]:
        """
        Retrieves comprehensive product dossier by product_id.
        Returns None if product does not exist.
        """
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM master_products WHERE product_id = ?", (product_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return None

        p = dict(row)

        # 1. Fetch gate progress
        cur.execute("""
            SELECT gate_number, status, started_at, completed_at, completed_by, blocked_reason, metadata_json
            FROM product_gate_progress
            WHERE product_id = ?
            ORDER BY gate_number ASC
        """, (product_id,))
        gate_rows = cur.fetchall()
        gates = []
        for gr in gate_rows:
            meta = None
            if gr["metadata_json"]:
                try:
                    meta = json.loads(gr["metadata_json"])
                except Exception:
                    meta = {"raw": gr["metadata_json"]}
            gates.append(GateProgressItem(
                gate_number=gr["gate_number"],
                status=gr["status"],
                completed_at=gr["completed_at"] or gr["started_at"],
                completed_by=gr["completed_by"],
                blocked_reason=gr["blocked_reason"],
                metadata=meta
            ))

        # 2. Fetch multi-platform listings
        cur.execute("""
            SELECT platform, title, listing_url as url, price, rating, review_count as reviews_count, in_stock
            FROM multi_platform_listings
            WHERE product_id = ?
            ORDER BY platform ASC
        """, (product_id,))
        listing_rows = cur.fetchall()
        listings = [
            MultiPlatformListingItem(
                platform=lr["platform"],
                title=lr["title"],
                url=lr["url"],
                price=lr["price"],
                rating=lr["rating"],
                reviews_count=lr["reviews_count"],
                in_stock=bool(lr["in_stock"]) if lr["in_stock"] is not None else None
            )
            for lr in listing_rows
        ]

        # 3. Fetch defect clusters
        cur.execute("""
            SELECT cluster_id, defect_category, defect_description, severity, is_fixable, v2_fix_description, v2_bom_delta_usd
            FROM defect_clusters
            WHERE product_id = ?
        """, (product_id,))
        defects = [dict(d) for d in cur.fetchall()]

        # 4. Fetch economics assessments
        cur.execute("""
            SELECT scenario, msrp, fob_cost, contribution_margin, contribution_margin_pct, overall_pass, composite_score
            FROM economics_assessments
            WHERE product_id = ?
            ORDER BY assessment_id DESC LIMIT 3
        """, (product_id,))
        econ_rows = [dict(e) for e in cur.fetchall()]
        conn.close()

        econ_summary = {"scenarios": econ_rows} if econ_rows else None

        return ProductDetailResponse(
            product_id=p["product_id"],
            name=p.get("name") or "Unnamed Product",
            category=p.get("category"),
            region=p.get("region"),
            planned_msrp=p.get("planned_msrp"),
            landed_cogs=p.get("landed_cogs"),
            gross_margin_pct=p.get("gross_margin_pct"),
            estimated_cac=p.get("estimated_cac"),
            net_profit_pct=p.get("net_profit_pct"),
            worst_case_stress_margin_pct=p.get("worst_case_stress_margin_pct"),
            status=p.get("status"),
            overall_score=p.get("overall_score"),
            consensus_status=p.get("consensus_status"),
            action_plan=p.get("action_plan"),
            sourcing_cluster=p.get("sourcing_cluster"),
            marketplace_url=p.get("marketplace_url"),
            competitor_3star_flaws=p.get("competitor_3star_flaws"),
            upgrade_v2_engineering=p.get("upgrade_v2_engineering"),
            bsr_rank=p.get("bsr_rank"),
            estimated_daily_units=p.get("estimated_daily_units"),
            human_override_status=p.get("human_override_status"),
            first_discovered_date=p.get("first_discovered_date"),
            last_evaluated_date=p.get("last_evaluated_date"),
            keepa_price_stability=p.get("keepa_price_stability"),
            helium_monthly_revenue=p.get("helium_monthly_revenue"),
            factory_cogs=p.get("factory_cogs"),
            created_at=p.get("created_at"),
            updated_at=p.get("updated_at"),
            ai_rejection_reason=p.get("ai_rejection_reason"),
            ai_reasoning=p.get("ai_reasoning"),
            ai_confidence=p.get("ai_confidence"),
            is_shortlisted=bool(p.get("is_shortlisted")),
            gates=gates,
            listings=listings,
            defects=defects if defects else None,
            economics_summary=econ_summary
        )

    @staticmethod
    def refresh_product_intelligence(product_id: str, db_path: Optional[str] = None) -> ProductRefreshResponse:
        """
        Explicit action endpoint helper: Re-runs the forensic intelligence pipeline
        for an existing product, updating product_intelligence, scorecards, and timeline.
        This must ONLY be called from explicit mutation endpoints (POST), NEVER from GET.
        """
        conn = get_connection(db_path)
        cur = conn.cursor()
        cur.execute("SELECT product_id, name FROM master_products WHERE product_id = ?", (product_id,))
        prod = cur.fetchone()
        conn.close()

        if not prod:
            return ProductRefreshResponse(
                success=False,
                product_id=product_id,
                refreshed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                error=f"Product '{product_id}' not found in master_products."
            )

        from core.intelligence_engine import AutonomousIntelligenceEngine
        result = AutonomousIntelligenceEngine.run_full_product_intelligence(product_id)
        if "error" in result:
            return ProductRefreshResponse(
                success=False,
                product_id=product_id,
                refreshed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                error=result["error"]
            )

        scorecard = result.get("scorecard", {})
        kill_switch = result.get("kill_switch", {})

        return ProductRefreshResponse(
            success=True,
            product_id=product_id,
            refreshed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            overall_score=scorecard.get("overall_score"),
            kill_status=kill_switch.get("status"),
            evidence_count=len(result.get("signals", {})),
            recommendation=scorecard.get("recommendation", "HOLD")
        )

    @staticmethod
    def observe_product_pipeline(product_id: str, db_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Phase 6 Explicit Action: Executes the live observation pipeline for a specific product.
        1. Queries master_products for name/query.
        2. Invokes verified live sources (Google Trends, GDELT).
        3. Runs through ObservationIngestionService (Validate -> Normalize -> Provenance -> Deduplicate -> Store).
        4. Calculates differentials via ObservationDiffEngine.
        5. Conditionally re-evaluates intelligence ONLY IF material changes were detected.
        """
        target_db = db_path or os.getenv("APRS_DB_PATH")
        conn = get_connection(target_db)
        cur = conn.cursor()
        cur.execute("SELECT product_id, name, target_region FROM master_products WHERE product_id = ?", (product_id,))
        prod = cur.fetchone()
        conn.close()

        if not prod:
            return {
                "success": False,
                "product_id": product_id,
                "error": f"Product '{product_id}' not found in master_products."
            }

        product_name = prod["name"]
        region = prod["target_region"] or "IN"

        from core.research_sources.registry import ResearchSourceRegistry
        registry = ResearchSourceRegistry.get_instance()
        
        # Execute observation pipeline across verified live sources
        res = registry.execute_observation_pipeline(
            query=product_name,
            product_id=product_id,
            sources=["google_trends", "gdelt"],
            marketplace="amazon.in" if "in" in str(region).lower() else "amazon.com",
            db_path=target_db
        )

        refreshed = False
        refresh_data = None
        if res.get("requires_intelligence_refresh"):
            refresh_res = ProductService.refresh_product_intelligence(product_id)
            refreshed = refresh_res.success
            refresh_data = refresh_res.model_dump()

        return {
            "success": True,
            "product_id": product_id,
            "product_name": product_name,
            "pipeline_summary": res.get("ingestion_summary"),
            "observations_count": res.get("observations_count"),
            "material_changes_detected": res.get("requires_intelligence_refresh"),
            "intelligence_refreshed": refreshed,
            "intelligence_refresh_details": refresh_data,
            "diff_reports": res.get("diff_reports"),
            "executed_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }

    @staticmethod
    def get_supplier_directory(
        limit: int = 50,
        offset: int = 0,
        region: Optional[str] = None,
        product_id: Optional[str] = None
    ) -> SupplierDirectoryResponse:
        """Returns registered factory partners and sourcing clusters from product_suppliers."""
        conn = get_connection()
        cur = conn.cursor()

        query = """
            SELECT ps.*, mp.name as product_name, mp.region as product_region
            FROM product_suppliers ps
            LEFT JOIN master_products mp ON ps.product_id = mp.product_id
            WHERE 1=1
        """
        params = []
        if product_id:
            query += " AND ps.product_id = ?"
            params.append(product_id)
        if region:
            query += " AND (mp.region = ? OR ps.industrial_address LIKE ?)"
            params.extend([region, f"%{region}%"])

        # Count total
        count_query = f"SELECT COUNT(*) FROM ({query})"
        cur.execute(count_query, params)
        total = cur.fetchone()[0]

        # Fetch page
        query += " ORDER BY ps.supplier_id ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        cur.execute(query, params)
        rows = cur.fetchall()
        conn.close()

        suppliers = [
            SupplierDirectoryItem(
                supplier_id=r["supplier_id"],
                product_id=r["product_id"],
                product_name=r["product_name"] or r["product_id"],
                region=r["product_region"] or "Global",
                factory_name=r["factory_name"] or "Verified Supplier",
                supplier_type=r["supplier_type"],
                industrial_address=r["industrial_address"],
                contact_person=r["contact_person"],
                contact_details=r["contact_details"],
                platform_profile_url=r["platform_profile_url"],
                fob_unit_price=r["fob_unit_price"],
                moq_units=r["moq_units"],
                sample_cost_leadtime=r["sample_cost_leadtime"],
                certifications=r["certifications"],
            )
            for r in rows
        ]
        return SupplierDirectoryResponse(total=total, suppliers=suppliers)

    @staticmethod
    def add_to_watchlist(product_id: str, priority_status: str = "WATCH", notes: str = "") -> WatchlistMutationResponse:
        from core.database import add_to_watchlist
        ok = add_to_watchlist(product_id, priority_status=priority_status, notes=notes)
        return WatchlistMutationResponse(
            product_id=product_id,
            in_watchlist=ok,
            status="SUCCESS" if ok else "FAILED",
            message=f"Product '{product_id}' added to watchlist." if ok else f"Failed to add '{product_id}' to watchlist."
        )

    @staticmethod
    def remove_from_watchlist(product_id: str) -> WatchlistMutationResponse:
        from core.database import remove_from_watchlist
        ok = remove_from_watchlist(product_id)
        return WatchlistMutationResponse(
            product_id=product_id,
            in_watchlist=False,
            status="SUCCESS" if ok else "FAILED",
            message=f"Product '{product_id}' removed from watchlist." if ok else f"Failed to remove '{product_id}' from watchlist."
        )

    @staticmethod
    def toggle_shortlist(product_id: str, is_shortlisted: bool = True) -> ShortlistToggleResponse:
        from core.database import toggle_shortlist
        ok = toggle_shortlist(product_id, is_shortlisted=is_shortlisted)
        return ShortlistToggleResponse(
            product_id=product_id,
            is_shortlisted=is_shortlisted if ok else False,
            message=f"Product '{product_id}' shortlist status set to {is_shortlisted}." if ok else f"Failed to update shortlist status for '{product_id}'."
        )

