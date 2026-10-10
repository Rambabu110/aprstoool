"""
api/services/trend_service.py — Queries real trend signals from SQLite SSOT.
Does not make blocking external network requests to Google Trends on page load.
"""
from typing import Optional, List, Any
from core.database import get_connection
from api.schemas.trend import TrendItem, TrendListResponse


class TrendService:
    @staticmethod
    def get_trends(
        page: int = 1,
        page_size: int = 25,
        region: Optional[str] = None,
        platform: Optional[str] = None,
        search: Optional[str] = None,
        status: str = "ACTIVE",
        sort_by: str = "velocity_score",
        sort_order: str = "desc"
    ) -> TrendListResponse:
        """
        Retrieves paginated, filtered trend signals from trend_signals table.
        """
        page = max(1, page)
        page_size = min(100, max(1, page_size))
        offset = (page - 1) * page_size

        conn = get_connection()
        cur = conn.cursor()

        where_clauses = ["1=1"]
        params: List[Any] = []

        if status:
            where_clauses.append("status = ?")
            params.append(status.upper())

        if region:
            where_clauses.append("region = ?")
            params.append(region)

        if platform:
            where_clauses.append("platform = ?")
            params.append(platform)

        if search:
            where_clauses.append("(keyword LIKE ? OR trend_category LIKE ?)")
            term = f"%{search.strip()}%"
            params.extend([term, term])

        where_sql = " AND ".join(where_clauses)

        # Count query
        cur.execute(f"SELECT COUNT(*) FROM trend_signals WHERE {where_sql}", params)
        total = cur.fetchone()[0]

        allowed_sorts = {
            "velocity_score": "velocity_score",
            "created_at": "created_at",
            "search_volume_est": "search_volume_est",
            "keyword": "keyword"
        }
        order_col = allowed_sorts.get(sort_by, "velocity_score")
        order_dir = "ASC" if sort_order.lower() == "asc" else "DESC"

        # Data query
        query_sql = f"""
            SELECT signal_id, platform, keyword, trend_category, region,
                   search_volume_est, velocity_score, longevity_days, status, created_at
            FROM trend_signals
            WHERE {where_sql}
            ORDER BY {order_col} {order_dir}
            LIMIT ? OFFSET ?
        """
        cur.execute(query_sql, params + [page_size, offset])
        rows = cur.fetchall()
        conn.close()

        items = [
            TrendItem(
                signal_id=r["signal_id"],
                keyword=r["keyword"],
                region=r["region"],
                source=r["platform"],
                velocity_score=r["velocity_score"],
                search_volume_indicator=str(r["search_volume_est"]) if r["search_volume_est"] else None,
                trend_type=r["trend_category"],
                first_detected_at=r["created_at"],
                last_updated_at=r["created_at"],
                is_active=(r["status"] == "ACTIVE")
            )
            for r in rows
        ]

        has_next = (offset + len(items)) < total

        return TrendListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_next=has_next
        )
