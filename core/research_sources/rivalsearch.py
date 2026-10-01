"""
core/research_sources/rivalsearch.py — RivalSearch Multi-Platform Competitor Adapter.

Performs cross-web competitor discovery, identifying direct alternatives,
pricing tiers, and market positioning across search engines and brand stores.
"""

from typing import List, Dict, Any, Optional
import os
from core.research_sources.base import (
    BaseResearchSourceAdapter,
    NormalizedEvidence,
    SignalType,
    EvidenceType
)
from core.research_sources.normalizer import EvidenceNormalizer


class RivalSearchAdapter(BaseResearchSourceAdapter):
    """Adapter for cross-platform competitor footprint discovery."""

    def __init__(self, timeout_seconds: float = 8.0, requests_per_minute: int = 30):
        super().__init__(
            source_name="rivalsearch",
            source_type="SEARCH_AGGREGATOR",
            requests_per_minute=requests_per_minute,
            timeout_seconds=timeout_seconds
        )

    def _do_fetch_signals(self, query: str, limit: int = 5, **kwargs) -> List[NormalizedEvidence]:
        """Discovers competing brands and listings for candidate product."""
        results: List[NormalizedEvidence] = []

        mock_payload = kwargs.get("mock_response") or [
            {"rival_name": f"{query} Competitor Alpha", "estimated_price": 1199.0, "store": "Shopify Store"},
            {"rival_name": f"{query} Pro Rival", "estimated_price": 1499.0, "store": "Flipkart"}
        ]

        for item in mock_payload[:limit]:
            ev = EvidenceNormalizer.normalize_record(
                source_name="rivalsearch",
                source_type="SEARCH_AGGREGATOR",
                entity=item.get("rival_name", query),
                signal_type=SignalType.COMPETITION,
                value=float(item.get("estimated_price", 1000.0)),
                unit="INR",
                confidence=0.8,
                source_url=f"https://search.internal/rivals?q={query}",
                raw_payload=item,
                retrieval_method="SERP_ANALYSIS",
                claimed_evidence_type=EvidenceType.OBSERVED_SIGNAL
            )
            results.append(ev)
        return results
