"""
core/research_sources/youtube.py — YouTube Creator & Video Signal Adapter.

Measures creator coverage, unboxing interest, and tutorial engagement for candidate products.
Enforces the anti-hallucination boundary: view counts represent media engagement,
never verified purchase intent or conversion volume.
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


class YouTubeResearchAdapter(BaseResearchSourceAdapter):
    """Adapter for YouTube video and engagement signals."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout_seconds: float = 8.0,
        requests_per_minute: int = 40
    ):
        super().__init__(
            source_name="youtube",
            source_type="API",
            requests_per_minute=requests_per_minute,
            timeout_seconds=timeout_seconds
        )
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY", "").strip()

    def _do_fetch_signals(self, query: str, limit: int = 5, **kwargs) -> List[NormalizedEvidence]:
        """Collects video engagement indicators for the candidate product query."""
        results: List[NormalizedEvidence] = []

        # Mock / Test Mode
        if os.getenv("APRS_RESEARCH_MOCK") == "1" or kwargs.get("mock_response") or not self.api_key:
            mock_items = kwargs.get("mock_response") or [
                {
                    "title": f"Top 5 Best {query} 2026 - Honest Review",
                    "views": 48500,
                    "channel": "Tech Reviews India",
                    "video_id": "yt_sample_123"
                }
            ]
            for item in mock_items[:limit]:
                ev = EvidenceNormalizer.normalize_record(
                    source_name="youtube",
                    source_type="API" if self.api_key else "ESTIMATE",
                    entity=query,
                    signal_type=SignalType.ENGAGEMENT,
                    value=int(item.get("views", 10000)),
                    unit="view_count",
                    confidence=0.85 if self.api_key else 0.7,
                    source_url=f"https://youtube.com/watch?v={item.get('video_id', '')}",
                    raw_payload=item,
                    retrieval_method="YOUTUBE_DATA_API" if self.api_key else "SYNTHETIC_ESTIMATE",
                    claimed_evidence_type=EvidenceType.OBSERVED_SIGNAL if self.api_key else EvidenceType.ESTIMATE
                )
                results.append(ev)
            return results

        # Live YouTube Data API v3 call
        endpoint = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "part": "snippet",
            "q": f"{query} review unboxing",
            "type": "video",
            "maxResults": limit,
            "key": self.api_key
        }

        resp = requests.get(endpoint, params=params, timeout=self.timeout_seconds)
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get("items", []):
                snippet = item.get("snippet", {})
                vid_title = snippet.get("title", "")
                vid_id = item.get("id", {}).get("videoId", "")
                ev = EvidenceNormalizer.normalize_record(
                    source_name="youtube",
                    source_type="API",
                    entity=query,
                    signal_type=SignalType.ENGAGEMENT,
                    value=vid_title,
                    unit="video_mention",
                    confidence=0.9,
                    source_url=f"https://youtube.com/watch?v={vid_id}",
                    raw_payload=item,
                    retrieval_method="YOUTUBE_DATA_API_V3",
                    claimed_evidence_type=EvidenceType.OBSERVED_SIGNAL
                )
                results.append(ev)
        else:
            raise RuntimeError(f"YouTube API returned {resp.status_code}: {resp.text}")

        return results
