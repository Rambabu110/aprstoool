"""
core/research_sources/trends_mcp.py — Trends-MCP Client & Adapter.

Integrates with Trends-MCP API using TRENDSMCP_API_KEY to retrieve
cross-platform trend intelligence (Google, Amazon, YouTube, TikTok, Reddit).
"""

from typing import List, Dict, Any, Optional
import os
import requests
import datetime
from core.research_sources.base import (
    BaseResearchSourceAdapter,
    NormalizedEvidence,
    SignalType,
    EvidenceType
)
from core.research_sources.normalizer import EvidenceNormalizer


class TrendsMCPAdapter(BaseResearchSourceAdapter):
    """Adapter for Trends-MCP (trends-mcp server & REST API)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.trendsmcp.com/v1",
        timeout_seconds: float = 8.0,
        requests_per_minute: int = 60
    ):
        super().__init__(
            source_name="trends_mcp",
            source_type="MCP",
            requests_per_minute=requests_per_minute,
            timeout_seconds=timeout_seconds
        )
        self.api_key = api_key if api_key is not None else os.getenv("TRENDSMCP_API_KEY", "").strip()
        self.base_url = os.getenv("TRENDSMCP_BASE_URL", base_url).rstrip("/")

    def is_available(self) -> bool:
        """Available only when a valid TrendsMCP API key is configured."""
        return bool(self.api_key and not self.api_key.startswith("xxx"))

    def _do_fetch_signals(self, query: str, limit: int = 10, **kwargs) -> List[NormalizedEvidence]:
        """
        Queries TrendsMCP for cross-platform trend signals.
        Supports channels: google, amazon, tiktok, youtube, reddit.
        """
        if not self.is_available():
            return []

        channels = kwargs.get("channels", ["google", "amazon", "youtube", "reddit"])
        results: List[NormalizedEvidence] = []

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "APRS-V8-ResearchEngine/1.0"
        }

        # Check for test/mock override
        if os.getenv("APRS_RESEARCH_MOCK") == "1" or kwargs.get("mock_response"):
            raw_items = kwargs.get("mock_response") or [
                {"channel": "google", "query": query, "trend_score": 88, "growth_pct": 34.5},
                {"channel": "amazon", "query": query, "trend_score": 72, "growth_pct": 18.2},
                {"channel": "youtube", "query": query, "trend_score": 65, "growth_pct": 12.0}
            ]
            for item in raw_items[:limit]:
                ch = item.get("channel", "general")
                score = float(item.get("trend_score", 50))
                ev = EvidenceNormalizer.normalize_record(
                    source_name=f"trends_mcp_{ch}",
                    source_type="MCP",
                    entity=query,
                    signal_type=SignalType.TREND,
                    value=score,
                    unit="index_0_100",
                    confidence=0.85,
                    source_url=f"https://trendsmcp.com/trends?q={query}&ch={ch}",
                    raw_payload=item,
                    retrieval_method="MCP_JSONRPC",
                    claimed_evidence_type=EvidenceType.OBSERVED_SIGNAL
                )
                results.append(ev)
            return results

        # Live API call
        endpoint = f"{self.base_url}/signals"
        params = {"query": query, "channels": ",".join(channels), "limit": limit}

        resp = requests.get(endpoint, headers=headers, params=params, timeout=self.timeout_seconds)
        if resp.status_code == 429:
            raise RuntimeError(f"TrendsMCP Rate limit exceeded: {resp.text}")
        if resp.status_code != 200:
            raise RuntimeError(f"TrendsMCP returned HTTP {resp.status_code}: {resp.text}")

        data = resp.json()
        items = data.get("signals", []) if isinstance(data, dict) else []

        for item in items[:limit]:
            ch = item.get("channel", "general")
            score = float(item.get("trend_score", item.get("score", 50)))
            ev = EvidenceNormalizer.normalize_record(
                source_name=f"trends_mcp_{ch}",
                source_type="MCP",
                entity=query,
                signal_type=SignalType.TREND,
                value=score,
                unit="index_0_100",
                confidence=0.85,
                source_url=item.get("source_url") or f"https://trendsmcp.com/trends?q={query}",
                raw_payload=item,
                retrieval_method="MCP_JSONRPC",
                claimed_evidence_type=EvidenceType.OBSERVED_SIGNAL
            )
            results.append(ev)

        return results
