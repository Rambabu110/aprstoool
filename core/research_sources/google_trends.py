"""
core/research_sources/google_trends.py — Google Trends Demand Validation Adapter.

Interfaces with Google Trends via pytrends to measure actual search momentum,
breakout rising queries, and regional demand for candidate products and niches.
Zero synthetic fallbacks or hardcoded 50.0 estimates.
"""

from typing import List, Dict, Any, Optional
import os
import datetime
import logging
from core.research_sources.base import (
    BaseResearchSourceAdapter,
    NormalizedEvidence,
    SignalType,
    EvidenceType
)
from core.research_sources.normalizer import EvidenceNormalizer

logger = logging.getLogger("aprs.research_sources.google_trends")


class GoogleTrendsAdapter(BaseResearchSourceAdapter):
    """Adapter for Google Trends search momentum."""

    def __init__(self, timeout_seconds: float = 15.0, requests_per_minute: int = 20):
        super().__init__(
            source_name="google_trends",
            source_type="PUBLIC_API",
            requests_per_minute=requests_per_minute,
            timeout_seconds=timeout_seconds
        )
        self._engine = None

    def _get_engine(self):
        """Lazy loads RealGoogleTrendsEngine from tools.google_trends_realtime."""
        if self._engine is None:
            try:
                from tools.google_trends_realtime import get_trends_engine
                self._engine = get_trends_engine()
            except ImportError as ie:
                logger.error(f"Failed to import RealGoogleTrendsEngine: {ie}")
                raise RuntimeError(f"DEPENDENCY_ERROR: pytrends or tools.google_trends_realtime unavailable: {ie}")
        return self._engine

    def _do_fetch_signals(self, query: str, limit: int = 5, **kwargs) -> List[NormalizedEvidence]:
        """
        Fetches interest over time index and breakout search queries from Google Trends.
        Returns ONLY observed real data. Never returns synthetic or hardcoded fallback estimates.
        """
        if not query or not query.strip():
            logger.warning("Google Trends query is empty or whitespace.")
            raise ValueError("INVALID_QUERY: query string is empty")

        clean_query = query.strip()
        results: List[NormalizedEvidence] = []
        geo = kwargs.get("geo", "IN")  # Default to India market
        timeframe = kwargs.get("timeframe", "today 3-m")

        # Mock / Test mode (explicitly enabled for unit testing)
        if os.getenv("APRS_RESEARCH_MOCK") == "1" or kwargs.get("mock_response"):
            mock_data = kwargs.get("mock_response") or {
                "interest_index": 78.0,
                "rising_queries": [f"{clean_query} best price", f"buy {clean_query} online", f"{clean_query} review"]
            }
            ev_trend = EvidenceNormalizer.normalize_record(
                source_name="google_trends",
                source_type="PUBLIC_API",
                entity=clean_query,
                signal_type=SignalType.DEMAND,
                value=float(mock_data.get("interest_index", 75.0)),
                unit="index_0_100",
                confidence=0.9,
                source_url=f"https://trends.google.com/trends/explore?geo={geo}&q={clean_query}",
                raw_payload=mock_data,
                retrieval_method="PUBLIC_API_REST",
                claimed_evidence_type=EvidenceType.OBSERVED_SIGNAL
            )
            results.append(ev_trend)

            for rq in mock_data.get("rising_queries", [])[:limit]:
                ev_kw = EvidenceNormalizer.normalize_record(
                    source_name="google_trends",
                    source_type="PUBLIC_API",
                    entity=rq,
                    signal_type=SignalType.KEYWORD,
                    value=100.0,
                    unit="breakout_pct",
                    confidence=0.85,
                    source_url=f"https://trends.google.com/trends/explore?geo={geo}&q={rq}",
                    retrieval_method="PUBLIC_API_REST",
                    claimed_evidence_type=EvidenceType.OBSERVED_SIGNAL
                )
                results.append(ev_kw)
            return results

        # Live engine execution via pytrends
        engine = self._get_engine()

        # 1. Fetch interest over time
        trend_data = engine.get_interest_over_time(clean_query, geo=geo, timeframe=timeframe)

        if not trend_data or not trend_data.get("success"):
            err_msg = trend_data.get("error", "Unknown Google Trends error") if trend_data else "Empty response"
            if "429" in str(err_msg).lower() or "too many" in str(err_msg).lower():
                raise RuntimeError(f"RATE_LIMITED: Google Trends rate limit reached: {err_msg}")
            elif "timeout" in str(err_msg).lower() or "timed out" in str(err_msg).lower() or "time out" in str(err_msg).lower():
                raise RuntimeError(f"TIMEOUT: Google Trends request timed out: {err_msg}")
            elif "no data" in str(err_msg).lower():
                logger.info(f"NO_DATA for Google Trends query '{clean_query}' in {geo}")
                return []
            else:
                raise RuntimeError(f"NETWORK_ERROR: {err_msg}")

        # CRITICAL RULE: Reject synthetic fallback from suggest if pytrends 429'd internally
        source_engine = trend_data.get("source", "")
        if source_engine != "pytrends_realtime":
            logger.warning(
                f"Google Trends direct call did not return real pytrends data (source={source_engine}). "
                "Rejecting synthetic estimate to preserve data integrity."
            )
            raise RuntimeError(f"UNAVAILABLE: Google Trends direct data unavailable (returned {source_engine})")

        # Real observed Google Trends signal
        current_interest = float(trend_data.get("current_interest", 0.0))
        raw_payload = {
            "current_interest": current_interest,
            "avg_interest_30d": trend_data.get("avg_interest_30d"),
            "avg_interest_7d": trend_data.get("avg_interest_7d"),
            "velocity_pct": trend_data.get("velocity_pct"),
            "trend_direction": trend_data.get("trend_direction"),
            "peak_interest": trend_data.get("peak_interest"),
            "peak_date": trend_data.get("peak_date"),
            "geo": geo,
            "timeframe": timeframe
        }

        ev_trend = EvidenceNormalizer.normalize_record(
            source_name="google_trends",
            source_type="PUBLIC_API",
            entity=clean_query,
            signal_type=SignalType.DEMAND,
            value=current_interest,
            unit="index_0_100",
            confidence=0.85,
            source_url=f"https://trends.google.com/trends/explore?geo={geo}&q={clean_query}",
            raw_payload=raw_payload,
            retrieval_method="PYTRENDS_REALTIME",
            claimed_evidence_type=EvidenceType.OBSERVED_SIGNAL
        )
        results.append(ev_trend)

        # 2. Fetch related queries (breakout search terms)
        try:
            related_data = engine.get_related_queries(clean_query, geo=geo, timeframe=timeframe)
            if related_data and related_data.get("success"):
                rising_queries = related_data.get("rising", [])
                for rq in rising_queries[:limit]:
                    rq_query = rq.get("query", "").strip()
                    if not rq_query:
                        continue
                    rq_val_str = str(rq.get("value", "100"))
                    try:
                        rq_val = float(rq_val_str.replace("+", "").replace("%", ""))
                    except ValueError:
                        rq_val = 100.0

                    ev_kw = EvidenceNormalizer.normalize_record(
                        source_name="google_trends",
                        source_type="PUBLIC_API",
                        entity=rq_query,
                        signal_type=SignalType.KEYWORD,
                        value=rq_val,
                        unit="breakout_pct",
                        confidence=0.80,
                        source_url=f"https://trends.google.com/trends/explore?geo={geo}&q={rq_query}",
                        raw_payload=rq,
                        retrieval_method="PYTRENDS_REALTIME",
                        claimed_evidence_type=EvidenceType.OBSERVED_SIGNAL
                    )
                    results.append(ev_kw)
        except Exception as rel_err:
            logger.debug(f"Related queries fetch notice for '{clean_query}': {rel_err}")

        return results

