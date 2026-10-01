"""
core/research_sources/amazon_india.py — Amazon India Seller & Listing Research Adapter.

Extracts observed market signals from Amazon.in listings (price, review velocity, rating).
Supports routing through Decodo proxy infrastructure while strictly maintaining
provenance and anti-hallucination boundaries.
"""

from typing import List, Dict, Any, Optional
import os
import requests
from bs4 import BeautifulSoup
from core.research_sources.base import (
    BaseResearchSourceAdapter,
    NormalizedEvidence,
    SignalType,
    EvidenceType
)
from core.research_sources.normalizer import EvidenceNormalizer
from core.research_sources.provenance import ProvenanceTracker


class AmazonIndiaAdapter(BaseResearchSourceAdapter):
    """
    Adapter for Amazon India marketplace research.
    Optionally routes via Decodo proxy infrastructure.
    """

    def __init__(
        self,
        use_proxy: bool = True,
        timeout_seconds: float = 12.0,
        requests_per_minute: int = 20
    ):
        super().__init__(
            source_name="amazon_india",
            source_type="SCRAPER",
            requests_per_minute=requests_per_minute,
            timeout_seconds=timeout_seconds
        )
        self.use_proxy = use_proxy
        self.proxy_auth = os.getenv("DECODO_AUTH", "").strip()
        self.proxy_host = os.getenv("DECODO_PROXY_HOST", "proxy.decodo.io").strip()
        self.proxy_port = os.getenv("DECODO_PROXY_PORT", "8080").strip()

    def _get_proxies(self) -> Optional[Dict[str, str]]:
        """Constructs proxy dictionary if Decodo credentials are present."""
        if self.use_proxy and self.proxy_auth:
            proxy_url = f"http://{self.proxy_auth}@{self.proxy_host}:{self.proxy_port}"
            return {"http": proxy_url, "https": proxy_url}
        return None

    def _do_fetch_signals(self, query: str, limit: int = 5, **kwargs) -> List[NormalizedEvidence]:
        """
        Gathers observed listings for query on Amazon.in.
        Emits price, rating, review counts as OBSERVED_SIGNAL.
        """
        results: List[NormalizedEvidence] = []
        target_url = f"https://www.amazon.in/s?k={requests.utils.quote(query)}"

        # Mock / Test mode
        if os.getenv("APRS_RESEARCH_MOCK") == "1" or kwargs.get("mock_response"):
            items = kwargs.get("mock_response") or [
                {"title": f"{query} Premium Edition", "price": 1299.0, "rating": 4.2, "reviews": 340, "asin": "B0IN123456"}
            ]
            for item in items[:limit]:
                # Price signal
                ev_price = EvidenceNormalizer.normalize_record(
                    source_name="amazon_india",
                    source_type="SCRAPER",
                    entity=item.get("title", query),
                    signal_type=SignalType.PRICE,
                    value=float(item.get("price", 999.0)),
                    unit="INR",
                    confidence=0.9,
                    source_url=target_url,
                    raw_payload=item,
                    retrieval_method="SCRAPER_PROXY" if self.proxy_auth else "SCRAPER_DIRECT",
                    claimed_evidence_type=EvidenceType.OBSERVED_SIGNAL
                )
                results.append(ev_price)

                # Demand/Competition signal (review count as proxy for competitor footprint)
                ev_comp = EvidenceNormalizer.normalize_record(
                    source_name="amazon_india",
                    source_type="SCRAPER",
                    entity=item.get("title", query),
                    signal_type=SignalType.COMPETITION,
                    value=int(item.get("reviews", 50)),
                    unit="review_count",
                    confidence=0.85,
                    source_url=target_url,
                    raw_payload=item,
                    retrieval_method="SCRAPER_PROXY" if self.proxy_auth else "SCRAPER_DIRECT",
                    claimed_evidence_type=EvidenceType.OBSERVED_SIGNAL
                )
                results.append(ev_comp)
            return results

        # Live scrape with headers
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-IN,en;q=0.9"
        }
        proxies = self._get_proxies()

        try:
            resp = requests.get(target_url, headers=headers, proxies=proxies, timeout=self.timeout_seconds)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                product_cards = soup.select('div[data-component-type="s-search-result"]')
                
                for card in product_cards[:limit]:
                    title_elem = card.select_one("h2 a span")
                    price_elem = card.select_one(".a-price-whole")
                    rating_elem = card.select_one(".a-icon-alt")
                    
                    if not title_elem:
                        continue
                        
                    title = title_elem.get_text(strip=True)
                    price_str = price_elem.get_text(strip=True).replace(",", "") if price_elem else "0"
                    try:
                        price_val = float(price_str)
                    except ValueError:
                        price_val = 0.0
                    
                    ev = EvidenceNormalizer.normalize_record(
                        source_name="amazon_india",
                        source_type="SCRAPER",
                        entity=title,
                        signal_type=SignalType.PRICE,
                        value=price_val,
                        unit="INR",
                        confidence=0.85,
                        source_url=target_url,
                        retrieval_method="SCRAPER_PROXY" if proxies else "SCRAPER_DIRECT",
                        claimed_evidence_type=EvidenceType.OBSERVED_SIGNAL
                    )
                    results.append(ev)
        except Exception as e:
            # Propagate to base retry/error tracker
            raise e

        return results
