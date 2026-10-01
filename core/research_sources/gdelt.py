"""
core/research_sources/gdelt.py — GDELT Project Global News & Event Adapter.

Queries the GDELT Project DOC 2.0 API to measure global media volume intensity,
news coverage momentum, and regulatory/market events for categories and products.
Free and public — requires no API key.
Enforces GDELT's strict 5-second interval pacing and handles rate limits honestly.
"""

from typing import List, Dict, Any, Optional
import os
import time
import json
import logging
import threading
import requests
from core.research_sources.base import (
    BaseResearchSourceAdapter,
    NormalizedEvidence,
    SignalType,
    EvidenceType
)
from core.research_sources.normalizer import EvidenceNormalizer

logger = logging.getLogger("aprs.research_sources.gdelt")

# Module-level gate enforcing >= 6.0 seconds between GDELT calls across all threads
_GDELT_LOCK = threading.Lock()
_LAST_GDELT_CALL_TS = 0.0
_MIN_GDELT_INTERVAL = 6.0


class GDELTResearchAdapter(BaseResearchSourceAdapter):
    """Adapter for GDELT global news intelligence."""

    def __init__(self, timeout_seconds: float = 15.0, requests_per_minute: int = 10):
        super().__init__(
            source_name="gdelt",
            source_type="PUBLIC_API",
            requests_per_minute=requests_per_minute,
            timeout_seconds=timeout_seconds
        )

    def _pace_gdelt_request(self):
        """Enforces minimum 6.0s spacing between GDELT requests to avoid 429 shedding."""
        global _LAST_GDELT_CALL_TS
        with _GDELT_LOCK:
            elapsed = time.time() - _LAST_GDELT_CALL_TS
            if elapsed < _MIN_GDELT_INTERVAL:
                time.sleep(_MIN_GDELT_INTERVAL - elapsed)
            _LAST_GDELT_CALL_TS = time.time()

    def _do_fetch_signals(self, query: str, limit: int = 5, **kwargs) -> List[NormalizedEvidence]:
        """
        Queries GDELT DOC API v2 for news volume intensity and articles.
        Returns ONLY observed real data. Never returns synthetic or fallback records.
        """
        if not query or not query.strip():
            logger.warning("GDELT query is empty or whitespace.")
            raise ValueError("INVALID_QUERY: query string is empty")

        clean_query = query.strip()
        results: List[NormalizedEvidence] = []

        # Mock / Test mode (explicitly enabled for unit testing)
        if os.getenv("APRS_RESEARCH_MOCK") == "1" or kwargs.get("mock_response"):
            mock_data = kwargs.get("mock_response") or [
                {
                    "title": f"Surging Consumer Demand for {clean_query} Across Tier-2 Indian Cities",
                    "url": "https://example-news.com/article1",
                    "seendate": "20261001T120000Z",
                    "domain": "financialexpress.com"
                }
            ]
            for art in mock_data[:limit]:
                ev = EvidenceNormalizer.normalize_record(
                    source_name="gdelt",
                    source_type="PUBLIC_API",
                    entity=clean_query,
                    signal_type=SignalType.NEWS,
                    value=art.get("title", ""),
                    unit="news_article",
                    confidence=0.8,
                    source_url=art.get("url"),
                    raw_payload=art,
                    retrieval_method="GDELT_DOC_API_V2",
                    claimed_evidence_type=EvidenceType.OBSERVED_SIGNAL
                )
                results.append(ev)
            return results

        # Live GDELT call
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json"
        }

        # Step 1: Pacing gate
        self._pace_gdelt_request()

        # Step 2: Query TimelineVol for macro media volume intensity
        encoded_query = requests.utils.quote(clean_query)
        vol_url = f"https://api.gdeltproject.org/api/v2/doc/doc?query={encoded_query}&mode=TimelineVol&format=json"

        try:
            resp = requests.get(vol_url, headers=headers, timeout=self.timeout_seconds)

            if resp.status_code == 429 or "please limit requests" in resp.text.lower():
                logger.warning(f"GDELT rate limit reached for '{clean_query}'. Status=429.")
                raise RuntimeError("RATE_LIMITED: GDELT public query limit (one request every 5s) active")

            if resp.status_code in [500, 502, 503, 504]:
                logger.warning(f"GDELT server error {resp.status_code} for '{clean_query}'.")
                raise RuntimeError(f"HTTP_ERROR: GDELT server returned status {resp.status_code}")

            if resp.status_code != 200:
                raise RuntimeError(f"HTTP_ERROR: GDELT query failed with status {resp.status_code}")

            # Parse JSON
            try:
                data = resp.json()
            except Exception as je:
                raise RuntimeError(f"INVALID_RESPONSE: Malformed JSON from GDELT: {je}")

            timeline = data.get("timeline", [])
            if timeline and isinstance(timeline, list) and len(timeline) > 0:
                series_data = timeline[0].get("data", [])
                if series_data:
                    # Extract latest intensity data point
                    latest_dp = series_data[-1]
                    latest_val = float(latest_dp.get("value", 0.0))
                    obs_date = str(latest_dp.get("date", ""))

                    # Calculate 7-day average if available
                    recent_vals = [float(p.get("value", 0.0)) for p in series_data[-7:]]
                    avg_7d = sum(recent_vals) / max(len(recent_vals), 1)

                    raw_meta = {
                        "latest_intensity": latest_val,
                        "avg_7d": round(avg_7d, 4),
                        "total_data_points": len(series_data),
                        "series_name": timeline[0].get("series", "Volume Intensity"),
                        "query": clean_query
                    }

                    ev_vol = EvidenceNormalizer.normalize_record(
                        source_name="gdelt",
                        source_type="PUBLIC_API",
                        entity=clean_query,
                        signal_type=SignalType.NEWS,
                        value=latest_val,
                        unit="volume_intensity_pct",
                        confidence=0.85,
                        source_url=vol_url,
                        raw_payload=raw_meta,
                        observed_at=obs_date,
                        retrieval_method="GDELT_DOC_API_V2_TIMELINE",
                        claimed_evidence_type=EvidenceType.OBSERVED_SIGNAL
                    )
                    results.append(ev_vol)
                else:
                    logger.info(f"NO_DATA: GDELT timeline data points empty for '{clean_query}'.")
            else:
                logger.info(f"NO_DATA: GDELT timeline empty for '{clean_query}'.")

        except requests.exceptions.Timeout as te:
            raise RuntimeError(f"TIMEOUT: GDELT API timed out after {self.timeout_seconds}s: {te}")
        except requests.exceptions.ConnectionError as ce:
            raise RuntimeError(f"NETWORK_ERROR: Failed to connect to GDELT: {ce}")
        except Exception as e:
            # Let the specific error bubble up to fetch_signals
            raise e

        return results

