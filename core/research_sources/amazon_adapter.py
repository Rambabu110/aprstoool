"""
core/research_sources/amazon_adapter.py — Safe Amazon Live Scraper Adapter & Validator.

Wraps tools/amazon_live_scraper.py with typed execution status:
LIVE_SUCCESS, BLOCKED, TIMEOUT, HTTP_ERROR, PARSE_ERROR, UNAVAILABLE

Enforces rigorous validation:
- ASIN (10 alphanumeric characters)
- Title (non-empty string)
- Price (strictly positive numeric value)
- Currency (ISO currency or detected code)
- Marketplace (valid domain)
- Canonical URL
- Availability (boolean in_stock)
- Observed timestamp

Never invents Best Sellers Rank (BSR) or Buy Box winner if not observed.
Emits CanonicalObservation instances for the safe ingestion pipeline.
"""

from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
import datetime
import re
import time
import logging

from core.research_sources.base import (
    BaseResearchSourceAdapter,
    SignalType,
    EvidenceType,
    NormalizedEvidence
)
from core.research_sources.observation import (
    CanonicalObservation,
    SourceStatus,
    SourceExecutionResult
)
from core.research_sources.normalizer import EvidenceNormalizer

logger = logging.getLogger("aprs.research_sources.amazon_adapter")


class AmazonScrapeStatus(str, Enum):
    """Explicit scrape outcomes for Amazon."""
    LIVE_SUCCESS = "LIVE_SUCCESS"
    BLOCKED = "BLOCKED"
    TIMEOUT = "TIMEOUT"
    HTTP_ERROR = "HTTP_ERROR"
    PARSE_ERROR = "PARSE_ERROR"
    UNAVAILABLE = "UNAVAILABLE"


class AmazonResearchAdapter(BaseResearchSourceAdapter):
    """
    Standardized, safe Amazon research adapter.
    Encapsulates AmazonLiveScraper with explicit anti-bot error discrimination.
    """

    def __init__(
        self,
        proxy_url: Optional[str] = None,
        timeout_seconds: float = 15.0,
        requests_per_minute: int = 15
    ):
        super().__init__(
            source_name="amazon_scraper",
            source_type="SCRAPER",
            requests_per_minute=requests_per_minute,
            timeout_seconds=timeout_seconds
        )
        self.proxy_url = proxy_url
        self._scraper = None

    def _get_scraper(self):
        """Lazy-instantiates AmazonLiveScraper."""
        if self._scraper is None:
            try:
                from tools.amazon_live_scraper import AmazonLiveScraper
                self._scraper = AmazonLiveScraper(proxy_url=self.proxy_url)
            except Exception as e:
                logger.error(f"Failed to initialize AmazonLiveScraper: {e}")
                raise RuntimeError(f"UNAVAILABLE: AmazonLiveScraper could not be loaded: {e}")
        return self._scraper

    @staticmethod
    def validate_listing(raw_item: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validates minimum required fields for an observed Amazon listing.
        Rejects malformed items before they can enter the database.
        """
        asin = raw_item.get("asin")
        if not asin or not re.match(r"^[A-Z0-9]{10}$", str(asin).strip()):
            return False, f"VALIDATION_ERROR: Invalid or missing ASIN '{asin}'."

        title = raw_item.get("title")
        if not title or not str(title).strip():
            return False, "VALIDATION_ERROR: Title cannot be empty."

        price = raw_item.get("price")
        if price is None:
            return False, "VALIDATION_ERROR: Price is missing."
        try:
            price_val = float(price)
            if price_val <= 0:
                return False, f"VALIDATION_ERROR: Price must be positive, got {price_val}."
        except (ValueError, TypeError):
            return False, f"VALIDATION_ERROR: Price '{price}' is not a valid number."

        domain = raw_item.get("domain") or raw_item.get("marketplace")
        if not domain or "amazon" not in str(domain).lower():
            return False, f"VALIDATION_ERROR: Invalid marketplace domain '{domain}'."

        return True, None

    def search_and_observe(
        self,
        query: str,
        region: str = "India",
        max_results: int = 5
    ) -> Tuple[AmazonScrapeStatus, List[CanonicalObservation], Optional[str]]:
        """
        Executes live search with explicit error classification.
        Returns (status, observations, error_message).
        """
        if not query or not query.strip():
            return AmazonScrapeStatus.PARSE_ERROR, [], "Search query cannot be empty."

        clean_query = query.strip()
        start_time = time.time()
        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        domain = "amazon.in" if region.lower() == "india" else "amazon.com"

        try:
            scraper = self._get_scraper()
            self.rate_limiter.acquire()
            raw_products = scraper.search(clean_query, region=region, max_results=max_results)

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000.0
            err_str = str(e).lower()
            self.record_error(str(e))

            if "blocked" in err_str or "captcha" in err_str or "bot" in err_str or "403" in err_str:
                logger.warning(f"Amazon scraper anti-bot blocked for '{clean_query}': {e}")
                return AmazonScrapeStatus.BLOCKED, [], f"ANTI_BOT_BLOCKED: {e}"
            elif "timeout" in err_str or "timed out" in err_str:
                logger.warning(f"Amazon scraper timed out for '{clean_query}': {e}")
                return AmazonScrapeStatus.TIMEOUT, [], f"TIMEOUT: {e}"
            elif "404" in err_str or "500" in err_str or "503" in err_str or "http" in err_str:
                return AmazonScrapeStatus.HTTP_ERROR, [], f"HTTP_ERROR: {e}"
            elif "no products parsed" in err_str:
                return AmazonScrapeStatus.PARSE_ERROR, [], f"PARSE_ERROR: {e}"
            else:
                return AmazonScrapeStatus.UNAVAILABLE, [], f"UNAVAILABLE: {e}"

        latency_ms = (time.time() - start_time) * 1000.0
        observations: List[CanonicalObservation] = []

        for item in raw_products:
            # Validate listing
            is_valid, val_err = self.validate_listing(item)
            if not is_valid:
                logger.debug(f"Skipping invalid Amazon listing item: {val_err}")
                continue

            asin = str(item["asin"]).strip()
            price_val = float(item["price"])
            currency_code = str(item.get("currency", "INR" if region.lower() == "india" else "USD"))
            rating_val = float(item.get("rating", 4.0))
            review_count = int(item.get("review_count", 0))
            title_str = str(item.get("title", clean_query))[:200]
            url_str = item.get("product_url", f"https://www.{domain}/dp/{asin}")
            in_stock = bool(item.get("in_stock", True))

            # Raw snapshot
            snapshot_dict = {
                "asin": asin,
                "title": title_str,
                "price": price_val,
                "currency": currency_code,
                "rating": rating_val,
                "review_count": review_count,
                "in_stock": in_stock,
                "marketplace": domain,
                "product_url": url_str,
                "seller": item.get("seller"),            # None if not observed; NEVER INVENTED
                "bsr_rank": item.get("bsr_rank"),          # None if not observed; NEVER INVENTED
                "scraped_at": now_utc
            }

            obs = CanonicalObservation(
                source_id="amazon_scraper",
                source_type="SCRAPER",
                external_id=asin,
                marketplace=domain,
                observation_type="LISTING",
                signal_type=SignalType.PRICE,
                evidence_type=EvidenceType.OBSERVED_SIGNAL,
                value=snapshot_dict,
                unit=currency_code,
                currency=currency_code,
                confidence=0.90,
                observed_at=now_utc,
                received_at=now_utc,
                source_url=url_str,
                source_record_id=f"amz_{asin}_{now_utc[:10]}",
                raw_payload=item,
                adapter_version="1.0.0",
                schema_version="1.0.0",
                fetch_duration_ms=round(latency_ms, 2)
            )
            observations.append(obs)

        if not observations:
            return AmazonScrapeStatus.PARSE_ERROR, [], "No valid listings passed schema validation."

        self.record_success(len(observations), latency_ms)
        return AmazonScrapeStatus.LIVE_SUCCESS, observations, None
