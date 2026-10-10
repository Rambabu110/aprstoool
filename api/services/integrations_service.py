"""
api/services/integrations_service.py — Service for real source health, marketplace configs, and telemetry.
"""
import os
from typing import List, Dict, Any
from core.database import get_connection
import config.settings as app_settings
from tools.keepa_api_client import KeepaAPIClient
from api.schemas.integrations import (
    SourceHealthItem,
    MarketplaceConfigItem,
    LLMClusterInfo,
    IntegrationOverviewResponse,
    KeepaTelemetryStatus
)


class IntegrationsService:
    @staticmethod
    def get_overview() -> IntegrationOverviewResponse:
        conn = get_connection()
        cur = conn.cursor()

        # Check if details_json exists in source_health
        cur.execute("PRAGMA table_info(source_health)")
        cols = {row[1] for row in cur.fetchall()}
        has_details = "details_json" in cols

        if has_details:
            cur.execute("""
                SELECT source_id, source_name, data_type, last_successful_fetch,
                       failure_count, freshness_status, response_time_ms, details_json, updated_at
                FROM source_health
                ORDER BY source_id ASC
            """)
        else:
            cur.execute("""
                SELECT source_id, source_name, data_type, last_successful_fetch,
                       failure_count, freshness_status, response_time_ms, updated_at
                FROM source_health
                ORDER BY source_id ASC
            """)
        source_rows = cur.fetchall()

        # Query marketplace_config
        cur.execute("""
            SELECT config_id, marketplace_name, region, base_url, is_active,
                   priority, success_rate, last_scraped_at, anti_bot_level, extraction_prompt
            FROM marketplace_config
            ORDER BY priority DESC
        """)
        market_rows = cur.fetchall()
        conn.close()

        import json
        MOCK_SOURCES = {"tiktok", "rivalsearch", "trendscope", "trendwatch"}
        CREDENTIAL_REQUIRED_SOURCES = {
            "amazon_india": "DECODO_AUTH",
            "amazon_scraper": "DECODO_AUTH",
            "trends_mcp": "TRENDSMCP_API_KEY",
            "scavio_mcp": "SCAVIO_API_KEY",
            "youtube": "YOUTUBE_API_KEY"
        }

        sources = []
        for r in source_rows:
            name = (r["source_name"] or "").lower()
            details = {}
            if has_details and r["details_json"]:
                try:
                    details = json.loads(r["details_json"])
                except Exception:
                    pass

            status_msg = details.get("status_message") or ""
            is_mock = name in MOCK_SOURCES
            fail_count = r["failure_count"] or 0
            last_fetch = r["last_successful_fetch"]
            freshness = r["freshness_status"] or "UNKNOWN"

            if is_mock:
                prov_status = "MOCK/TEST"
            elif name in CREDENTIAL_REQUIRED_SOURCES and not os.getenv(CREDENTIAL_REQUIRED_SOURCES[name]):
                prov_status = "NOT_CONFIGURED"
            elif freshness == "OFFLINE" or fail_count > 5:
                prov_status = "FAILED"
            elif last_fetch and freshness == "HEALTHY":
                prov_status = "LIVE_VERIFIED"
            elif last_fetch:
                prov_status = "CACHED"
            else:
                prov_status = "UNVERIFIED"

            sources.append(
                SourceHealthItem(
                    source_id=r["source_id"],
                    source_name=r["source_name"],
                    data_type=r["data_type"] or "SCRAPER",
                    last_successful_fetch=last_fetch,
                    failure_count=fail_count,
                    freshness_status=freshness,
                    provenance_status=prov_status,
                    is_mock=is_mock,
                    status_message=status_msg or None,
                    response_time_ms=float(r["response_time_ms"] or 0.0),
                    updated_at=r["updated_at"] or "N/A"
                )
            )

        marketplaces = [
            MarketplaceConfigItem(
                config_id=r["config_id"],
                marketplace_name=r["marketplace_name"],
                region=r["region"],
                base_url=r["base_url"],
                is_active=bool(r["is_active"]),
                priority=r["priority"] or 0,
                success_rate=round(float(r["success_rate"] or 0.0), 2),
                last_scraped_at=r["last_scraped_at"],
                anti_bot_level=r["anti_bot_level"] or "standard",
                extraction_prompt=r["extraction_prompt"]
            )
            for r in market_rows
        ]

        llm_cluster = LLMClusterInfo(
            nim_keys_configured=len(getattr(app_settings, "NIM_API_KEYS", [])),
            nim_base_url=getattr(app_settings, "NIM_BASE_URL", ""),
            models_configured=getattr(app_settings, "NIM_MODELS", {}),
            roles_configured=list(getattr(app_settings, "SWARM_ROLES", {}).keys()),
            gemini_fallback_configured=bool(getattr(app_settings, "GEMINI_API_KEY", "")),
            google_trends_enabled=bool(getattr(app_settings, "GOOGLE_TRENDS_ENABLED", True)),
            local_ollama_present=False
        )

        return IntegrationOverviewResponse(
            sources=sources,
            marketplaces=marketplaces,
            llm_cluster=llm_cluster
        )

    @staticmethod
    def get_keepa_status() -> KeepaTelemetryStatus:
        keepa_key = os.getenv("KEEPA_API_KEY", "")
        api_configured = bool(keepa_key and len(keepa_key.strip()) >= 20)

        conn = get_connection()
        cur = conn.cursor()

        # Query real telemetry stored in master_products
        cur.execute("SELECT COUNT(*) FROM master_products WHERE keepa_price_stability IS NOT NULL")
        monitored_products_count = cur.fetchone()[0]

        cur.execute("SELECT AVG(keepa_price_stability) FROM master_products WHERE keepa_price_stability IS NOT NULL")
        avg_row = cur.fetchone()
        avg_stability = round(avg_row[0], 1) if avg_row and avg_row[0] is not None else None

        cur.execute("SELECT COUNT(*) FROM master_products WHERE bsr_rank IS NOT NULL AND bsr_rank > 0")
        products_with_bsr_count = cur.fetchone()[0]

        conn.close()

        status_msg = (
            "Keepa live API authenticated and active."
            if api_configured
            else "Keepa live API key not configured in environment. Displaying historical Keepa price stability telemetry from SQLite SSOT."
        )

        return KeepaTelemetryStatus(
            api_configured=api_configured,
            status_message=status_msg,
            supported_domains=KeepaAPIClient.DOMAINS,
            monitored_products_count=monitored_products_count,
            avg_price_stability_pct=avg_stability,
            products_with_bsr_count=products_with_bsr_count
        )
