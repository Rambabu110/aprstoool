"""
core/research_sources/scavio.py — Scavio MCP Client & Adapter.

Integrates with Scavio-AI MCP API using SCAVIO_API_KEY to perform web intelligence,
competitor monitoring, and feature gap extraction.
"""

from typing import List, Dict, Any, Optional
import os
import requests
from core.research_sources.base import (
    BaseResearchSourceAdapter,
    NormalizedEvidence,
    SignalType,
    EvidenceType
)
from core.research_sources.normalizer import EvidenceNormalizer


class ScavioMCPAdapter(BaseResearchSourceAdapter):
    """Adapter for Scavio MCP (scavio-ai/scavio-mcp)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.scavio.ai/v1",
        timeout_seconds: float = 10.0,
        requests_per_minute: int = 30
    ):
        super().__init__(
            source_name="scavio_mcp",
            source_type="MCP",
            requests_per_minute=requests_per_minute,
            timeout_seconds=timeout_seconds
        )
        self.api_key = api_key if api_key is not None else os.getenv("SCAVIO_API_KEY", "").strip()
        self.base_url = os.getenv("SCAVIO_BASE_URL", base_url).rstrip("/")

    def is_available(self) -> bool:
        """Available when SCAVIO_API_KEY is configured."""
        return bool(self.api_key and not self.api_key.startswith("xxx"))

    def _do_fetch_signals(self, query: str, limit: int = 5, **kwargs) -> List[NormalizedEvidence]:
        """Queries Scavio for competitor products, price points, and review sentiment."""
        if not self.is_available():
            return []

        results: List[NormalizedEvidence] = []
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "APRS-V8-ResearchEngine/1.0"
        }

        # Test/mock support
        if os.getenv("APRS_RESEARCH_MOCK") == "1" or kwargs.get("mock_response"):
            raw_items = kwargs.get("mock_response") or [
                {
                    "competitor": f"{query} Top Rival",
                    "price": 1499.0,
                    "rating": 4.1,
                    "weakness": "Battery degrades after 3 months",
                    "url": "https://example.com/competitor1"
                }
            ]
            for item in raw_items[:limit]:
                ev_pain = EvidenceNormalizer.normalize_record(
                    source_name="scavio_mcp",
                    source_type="MCP",
                    entity=query,
                    signal_type=SignalType.CUSTOMER_PAIN,
                    value=item.get("weakness", "Reported flaw"),
                    unit="text_finding",
                    confidence=0.8,
                    source_url=item.get("url"),
                    raw_payload=item,
                    retrieval_method="MCP_JSONRPC",
                    claimed_evidence_type=EvidenceType.OBSERVED_SIGNAL
                )
                results.append(ev_pain)
            return results

        # Live call
        endpoint = f"{self.base_url}/research"
        payload = {"query": query, "depth": "standard", "limit": limit}

        resp = requests.post(endpoint, headers=headers, json=payload, timeout=self.timeout_seconds)
        if resp.status_code == 429:
            raise RuntimeError(f"Scavio Rate limit: {resp.text}")
        if resp.status_code != 200:
            raise RuntimeError(f"Scavio returned HTTP {resp.status_code}: {resp.text}")

        data = resp.json()
        findings = data.get("findings", []) if isinstance(data, dict) else []

        for item in findings[:limit]:
            ev = EvidenceNormalizer.normalize_record(
                source_name="scavio_mcp",
                source_type="MCP",
                entity=query,
                signal_type=SignalType.COMPETITION,
                value=item.get("summary", str(item)),
                unit="text_analysis",
                confidence=float(item.get("confidence", 0.75)),
                source_url=item.get("source_url"),
                raw_payload=item,
                retrieval_method="MCP_JSONRPC",
                claimed_evidence_type=EvidenceType.OBSERVED_SIGNAL
            )
            results.append(ev)

        return results
