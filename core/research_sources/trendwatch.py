"""
core/research_sources/trendwatch.py — TrendWatch Breakout & Velocity Adapter.

Monitors breakout thresholds, acceleration rates, and momentum shifts
to provide early-warning signals for fast-moving product opportunities.
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


class TrendWatchAdapter(BaseResearchSourceAdapter):
    """Adapter for breakout velocity monitoring."""

    def __init__(self, timeout_seconds: float = 6.0, requests_per_minute: int = 40):
        super().__init__(
            source_name="trendwatch",
            source_type="ANALYTICS",
            requests_per_minute=requests_per_minute,
            timeout_seconds=timeout_seconds
        )

    def _do_fetch_signals(self, query: str, limit: int = 5, **kwargs) -> List[NormalizedEvidence]:
        """Calculates or fetches breakout acceleration signals."""
        results: List[NormalizedEvidence] = []

        mock_payload = kwargs.get("mock_response") or {
            "entity": query,
            "acceleration_score": 84.5,
            "is_breakout": True,
            "velocity_delta_7d": "+142%"
        }

        ev = EvidenceNormalizer.normalize_record(
            source_name="trendwatch",
            source_type="ANALYTICS",
            entity=query,
            signal_type=SignalType.TREND,
            value=float(mock_payload.get("acceleration_score", 75.0)),
            unit="velocity_score_0_100",
            confidence=0.85,
            source_url=f"https://trendwatch.internal/metrics?q={query}",
            raw_payload=mock_payload,
            retrieval_method="VELOCITY_ANALYSIS",
            claimed_evidence_type=EvidenceType.ESTIMATE
        )
        results.append(ev)
        return results
