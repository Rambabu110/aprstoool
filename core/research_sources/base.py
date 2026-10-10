"""
core/research_sources/base.py — Universal Research Source Adapter Foundation.

Defines the core data contracts, anti-hallucination type boundaries,
health telemetry, rate limiting, and retry policies for all external
research providers in APRS.
"""

from enum import Enum
from typing import Dict, Any, List, Optional, Union, Callable
import datetime
import hashlib
import time
import random
import threading
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()


# ─────────────────────────────────────────────────────────────────────────────
# 1. ANTI-HALLUCINATION EVIDENCE TYPING
# ─────────────────────────────────────────────────────────────────────────────
class EvidenceType(str, Enum):
    """
    CRITICAL ANTI-HALLUCINATION BOUNDARY:
    Strictly distinguishes observed reality from speculative inferences.
    Never allow a trend signal to be labeled as sales or verified volume.
    """
    OBSERVED_SIGNAL = "OBSERVED_SIGNAL"  # Raw external signal (e.g. search index, post count)
    ESTIMATE = "ESTIMATE"                # Calculated approximation from a source model
    INFERENCE = "INFERENCE"              # Derived synthesis by AI or deterministic heuristic
    PREDICTION = "PREDICTION"            # Forward-looking forecast
    DECISION = "DECISION"                # Operational verdict (buy, kill, RFQ)


class SignalType(str, Enum):
    """Normalized categories of research signals across all providers."""
    DEMAND = "DEMAND"
    COMPETITION = "COMPETITION"
    CUSTOMER_PAIN = "CUSTOMER_PAIN"
    PRICE = "PRICE"
    TREND = "TREND"
    KEYWORD = "KEYWORD"
    NEWS = "NEWS"
    ENGAGEMENT = "ENGAGEMENT"


# ─────────────────────────────────────────────────────────────────────────────
# 2. DATA CONTRACTS: HEALTH, NORMALIZED EVIDENCE, AND CONFLICTS
# ─────────────────────────────────────────────────────────────────────────────
class SourceHealth(BaseModel):
    """Tracks provider operational status, degradation, and latency."""
    source_name: str
    is_healthy: bool = False
    status: str = "UNINITIALIZED"
    last_successful_run: Optional[str] = None
    records_collected_total: int = 0
    consecutive_errors: int = 0
    average_latency_ms: float = 0.0
    status_message: str = "UNINITIALIZED"
    rate_limit_remaining: Optional[int] = None
    last_error: Optional[str] = None


class NormalizedEvidence(BaseModel):
    """
    Immutable, standardized evidence record emitted by research adapters.
    Preserves complete provenance, timestamps, confidence, and anti-hallucination types.
    """
    source: str
    source_type: str = "API"            # e.g., "MCP", "API", "SCRAPER", "PUBLIC"
    source_record_id: str               # Deterministic identifier for deduplication
    entity: str                         # Keyword, topic, ASIN, or product title
    evidence_type: EvidenceType = EvidenceType.OBSERVED_SIGNAL
    signal_type: SignalType
    value: Union[float, int, str, Dict[str, Any]]
    unit: str = "index_0_100"           # e.g. "index_0_100", "count", "currency", "sentiment"
    observed_at: str                    # Original observation timestamp from source
    retrieved_at: str                   # Local ingestion timestamp
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    source_url: Optional[str] = None
    raw_reference: Optional[str] = None
    adapter_version: str = "1.0.0"
    schema_version: str = "1.0.0"

    def generate_dedup_hash(self) -> str:
        """Deterministic fingerprint of this evidence record."""
        payload = f"{self.source}|{self.entity}|{self.signal_type}|{self.observed_at}|{self.value}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class SourceConflict(BaseModel):
    """Structured record when two independent sources emit divergent signals."""
    conflict_id: str
    entity: str
    signal_type: SignalType
    source_a: str
    value_a: Any
    timestamp_a: str
    source_b: str
    value_b: Any
    timestamp_b: str
    conflict_type: str                   # e.g., "MAGNITUDE_DIVERGENCE", "TREND_CONTRADICTION"
    divergence_score: float = 0.0        # Normalized difference [0.0, 1.0]
    severity: str = "MEDIUM"             # "LOW", "MEDIUM", "HIGH"
    resolution_status: str = "UNRESOLVED"
    explanation: str = ""
    created_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())


# ─────────────────────────────────────────────────────────────────────────────
# 3. RATE LIMITING & RETRY POLICY
# ─────────────────────────────────────────────────────────────────────────────
class RateLimiter:
    """Thread-safe token bucket rate limiter to protect free and public APIs."""
    def __init__(self, requests_per_minute: int = 60):
        self.rpm = max(1, requests_per_minute)
        self.interval = 60.0 / self.rpm
        self.last_request = 0.0
        self._lock = threading.Lock()

    def acquire(self):
        with self._lock:
            now = time.time()
            elapsed = now - self.last_request
            if elapsed < self.interval:
                time.sleep(self.interval - elapsed)
            self.last_request = time.time()


class RetryPolicy:
    """Configurable exponential backoff with jitter."""
    def __init__(self, max_retries: int = 3, backoff_factor: float = 1.5, max_backoff: float = 10.0):
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.max_backoff = max_backoff

    def execute_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                last_exception = exc
                if attempt == self.max_retries:
                    raise exc
                delay = min(self.max_backoff, self.backoff_factor ** attempt) + random.uniform(0.1, 0.5)
                time.sleep(delay)
        raise last_exception


# ─────────────────────────────────────────────────────────────────────────────
# 4. BASE RESEARCH SOURCE ADAPTER
# ─────────────────────────────────────────────────────────────────────────────
class BaseResearchSourceAdapter:
    """
    Abstract base adapter for all APRS research sources.
    Enforces timeout isolation, telemetry, and graceful degradation.
    """
    def __init__(
        self,
        source_name: str,
        source_type: str = "API",
        requests_per_minute: int = 30,
        max_retries: int = 2,
        timeout_seconds: float = 10.0
    ):
        self.source_name = source_name
        self.source_type = source_type
        self.timeout_seconds = timeout_seconds
        self.rate_limiter = RateLimiter(requests_per_minute)
        self.retry_policy = RetryPolicy(max_retries=max_retries)
        
        # Operational telemetry
        self.records_collected_total = 0
        self.consecutive_errors = 0
        self.total_latency_ms = 0.0
        self.total_calls = 0
        self.last_successful_run: Optional[str] = None
        self.last_error: Optional[str] = None
        self._lock = threading.Lock()

    def is_available(self) -> bool:
        """Determines if the adapter has valid credentials / network access."""
        return True

    @property
    def is_mock(self) -> bool:
        """Determines if the adapter produces mock/stub data."""
        return self.source_name.lower() in ("tiktok", "rivalsearch", "trendscope", "trendwatch")

    def record_success(self, count: int, latency_ms: float):
        with self._lock:
            self.records_collected_total += count
            self.consecutive_errors = 0
            self.total_latency_ms += latency_ms
            self.total_calls += 1
            self.last_successful_run = datetime.datetime.now(datetime.timezone.utc).isoformat()
            self.last_error = None

    def record_error(self, err_msg: str):
        with self._lock:
            self.consecutive_errors += 1
            self.total_calls += 1
            self.last_error = err_msg

    def health_check(self) -> SourceHealth:
        with self._lock:
            avg_lat = (self.total_latency_ms / max(1, self.total_calls))
            
            if not self.is_available():
                is_healthy = False
                source_status = "UNCONFIGURED"
                status_msg = "UNCONFIGURED (Missing Credential or Proxy)"
            elif self.last_successful_run is None:
                # Never had a verified successful live run
                is_healthy = False
                if self.consecutive_errors > 0:
                    source_status = "FAILED"
                    if self.last_error and "rate_limited" in self.last_error.lower():
                        status_msg = "RATE_LIMITED"
                    elif self.last_error and "timeout" in self.last_error.lower():
                        status_msg = "TIMEOUT"
                    else:
                        status_msg = f"FAILED ({self.consecutive_errors} errors before any success)"
                else:
                    source_status = "UNINITIALIZED"
                    status_msg = "INITIALIZED (UNPROBED)"
            elif self.consecutive_errors >= 5:
                is_healthy = False
                source_status = "FAILED"
                status_msg = f"OFFLINE ({self.consecutive_errors} consecutive errors)"
            elif self.consecutive_errors > 0:
                is_healthy = True
                source_status = "DEGRADED"
                if self.last_error and "rate_limited" in self.last_error.lower():
                    status_msg = "RATE_LIMITED"
                else:
                    status_msg = f"DEGRADED ({self.consecutive_errors} errors)"
            else:
                is_healthy = True
                source_status = "HEALTHY"
                status_msg = "ONLINE"

            return SourceHealth(
                source_name=self.source_name,
                is_healthy=is_healthy,
                status=source_status,
                last_successful_run=self.last_successful_run,
                records_collected_total=self.records_collected_total,
                consecutive_errors=self.consecutive_errors,
                average_latency_ms=round(avg_lat, 2),
                status_message=status_msg,
                last_error=self.last_error
            )

    def fetch_signals(self, query: str, limit: int = 10, **kwargs) -> List[NormalizedEvidence]:
        """
        Public execution wrapper with rate limiting, error catching, and metrics.
        Never throws unhandled exceptions to caller — gracefully isolates failures.
        """
        if not self.is_available():
            self.record_error("Provider unavailable or missing credentials")
            return []

        start_time = time.time()
        try:
            self.rate_limiter.acquire()
            results = self.retry_policy.execute_with_retry(self._do_fetch_signals, query, limit, **kwargs)
            latency_ms = (time.time() - start_time) * 1000.0
            self.record_success(len(results), latency_ms)
            return results
        except Exception as exc:
            self.record_error(str(exc))
            return []

    def fetch_canonical_observations(self, query: str, limit: int = 10, **kwargs) -> Any:
        """
        Executes fetch and returns a structured SourceExecutionResult containing
        canonical observations for the safe ingestion pipeline.
        """
        from core.research_sources.observation import (
            CanonicalObservation,
            SourceStatus,
            SourceExecutionResult
        )
        started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        start_ts = time.time()

        if not self.is_available():
            completed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            return SourceExecutionResult(
                source_id=self.source_name,
                status=SourceStatus.UNCONFIGURED,
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=0.0,
                records_received=0,
                error_type="UNCONFIGURED",
                error_message="Provider unconfigured or missing credentials/proxy"
            )

        evidence_list = self.fetch_signals(query, limit=limit, **kwargs)
        duration_ms = (time.time() - start_ts) * 1000.0
        completed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        observations = [
            CanonicalObservation.from_normalized_evidence(
                ev,
                product_id=kwargs.get("product_id"),
                marketplace=kwargs.get("marketplace"),
                currency=kwargs.get("currency")
            )
            for ev in evidence_list
        ]

        h = self.health_check()
        try:
            exec_status = SourceStatus(h.status)
        except (ValueError, KeyError):
            exec_status = SourceStatus.HEALTHY if h.is_healthy else SourceStatus.DEGRADED

        return SourceExecutionResult(
            source_id=self.source_name,
            status=exec_status,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=round(duration_ms, 2),
            records_received=len(observations),
            observations=observations,
            error_type="SOURCE_ERROR" if self.last_error else None,
            error_message=self.last_error
        )

    def _do_fetch_signals(self, query: str, limit: int, **kwargs) -> List[NormalizedEvidence]:
        """Subclasses implement specific provider logic here."""
        raise NotImplementedError
