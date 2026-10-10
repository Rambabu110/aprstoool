"""
core/research_sources/reddit.py — Reddit Customer Pain & Discussion Adapter.

Extracts customer grievances, recurring product complaints, and unmet needs
from targeted subreddits (e.g., r/ecommerce, product categories, defect discussions).
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


class RedditResearchAdapter(BaseResearchSourceAdapter):
    """Adapter for Reddit customer pain and discussion signals."""

    def __init__(self, timeout_seconds: float = 8.0, requests_per_minute: int = 30):
        super().__init__(
            source_name="reddit",
            source_type="PUBLIC_FEED",
            requests_per_minute=requests_per_minute,
            timeout_seconds=timeout_seconds
        )

    def _do_fetch_signals(self, query: str, limit: int = 5, **kwargs) -> List[NormalizedEvidence]:
        """Queries public Reddit JSON endpoints for complaints regarding product/niche."""
        results: List[NormalizedEvidence] = []
        target_sub = kwargs.get("subreddit", "all")
        url = f"https://www.reddit.com/r/{target_sub}/search.json?q={requests.utils.quote(query)}+defect+OR+problem+OR+broke&restrict_sr=1&limit={limit}&sort=relevance"

        # Mock / Test Mode
        if os.getenv("APRS_RESEARCH_MOCK") == "1" or kwargs.get("mock_response"):
            items = kwargs.get("mock_response") or [
                {
                    "title": f"Frustrated with my {query} - stopped working after 2 weeks",
                    "subreddit": "BuyItForLife",
                    "score": 142,
                    "url": f"https://reddit.com/r/BuyItForLife/comments/test1",
                    "permalink": "/r/BuyItForLife/comments/test1"
                },
                {
                    "title": f"Why does every {query} have cheap plastic hinges?",
                    "subreddit": "mildlyinfuriating",
                    "score": 89,
                    "url": f"https://reddit.com/r/mildlyinfuriating/comments/test2",
                    "permalink": "/r/mildlyinfuriating/comments/test2"
                }
            ]
            for post in items[:limit]:
                ev = EvidenceNormalizer.normalize_record(
                    source_name="reddit",
                    source_type="PUBLIC_FEED",
                    entity=query,
                    signal_type=SignalType.CUSTOMER_PAIN,
                    value=post.get("title", ""),
                    unit="complaint_post",
                    confidence=0.85,
                    source_url=post.get("url"),
                    raw_payload=post,
                    retrieval_method="PUBLIC_FEED_JSON",
                    claimed_evidence_type=EvidenceType.OBSERVED_SIGNAL
                )
                results.append(ev)
            return results

        # Live Public Reddit JSON request
        headers = {"User-Agent": "APRS-V8-ResearchBot/1.0 (Market Research)"}
        try:
            resp = requests.get(url, headers=headers, timeout=self.timeout_seconds)
            if resp.status_code == 429:
                raise RuntimeError("RATE_LIMITED: Reddit public API rate limit reached (HTTP 429)")
            elif resp.status_code != 200:
                raise RuntimeError(f"HTTP_ERROR: Reddit query failed with status {resp.status_code}")

            data = resp.json()
            children = data.get("data", {}).get("children", [])
            for child in children[:limit]:
                pdata = child.get("data", {})
                title = pdata.get("title", "")
                permalink = pdata.get("permalink", "")
                post_url = f"https://www.reddit.com{permalink}" if permalink else url

                ev = EvidenceNormalizer.normalize_record(
                    source_name="reddit",
                    source_type="PUBLIC_FEED",
                    entity=query,
                    signal_type=SignalType.CUSTOMER_PAIN,
                    value=title,
                    unit="complaint_post",
                    confidence=0.8,
                    source_url=post_url,
                    retrieval_method="PUBLIC_FEED_JSON",
                    claimed_evidence_type=EvidenceType.OBSERVED_SIGNAL
                )
                results.append(ev)
        except Exception as e:
            raise e

        return results
