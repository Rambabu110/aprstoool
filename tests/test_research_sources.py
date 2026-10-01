"""
tests/test_research_sources.py — Comprehensive Unit & Integration Tests for Research Source Adapters.

Strictly verifies all 14 required dimensions across the research source adapter layer:
1. Configuration
2. Authentication handling
3. Successful response
4. Empty response
5. Malformed response
6. Timeout handling
7. Rate limit handling
8. Provider error isolation
9. Normalization correctness
10. Provenance chain of custody
11. Duplicate detection / idempotency
12. Source health telemetry
13. Conflict handling & non-averaging
14. Anti-hallucination type boundary enforcement
"""

import pytest
import os
import time
from unittest.mock import patch, MagicMock
import requests

from core.research_sources.base import (
    BaseResearchSourceAdapter,
    NormalizedEvidence,
    SourceConflict,
    SourceHealth,
    EvidenceType,
    SignalType,
    RateLimiter,
    RetryPolicy
)
from core.research_sources.provenance import ProvenanceTracker
from core.research_sources.normalizer import EvidenceNormalizer
from core.research_sources.registry import ResearchSourceRegistry

from core.research_sources.trends_mcp import TrendsMCPAdapter
from core.research_sources.scavio import ScavioMCPAdapter
from core.research_sources.amazon_india import AmazonIndiaAdapter
from core.research_sources.google_trends import GoogleTrendsAdapter
from core.research_sources.reddit import RedditResearchAdapter
from core.research_sources.youtube import YouTubeResearchAdapter
from core.research_sources.gdelt import GDELTResearchAdapter
from core.research_sources.trendwatch import TrendWatchAdapter
from core.research_sources.tiktok import TikTokResearchAdapter
from core.research_sources.rivalsearch import RivalSearchAdapter
from core.research_sources.trendscope import TrendScopeAdapter


# ─────────────────────────────────────────────────────────────────────────────
# 1. CONFIGURATION & AUTHENTICATION TESTS
# ─────────────────────────────────────────────────────────────────────────────
class TestSourceConfigurationAndAuth:
    """Verify initialization, credential loading, and availability flags."""

    def test_trends_mcp_auth_detection(self):
        """TrendsMCP is available when key is set, unavailable when empty or placeholder."""
        adapter_with_key = TrendsMCPAdapter(api_key="tmcp_live_testkey123")
        assert adapter_with_key.is_available() is True

        adapter_no_key = TrendsMCPAdapter(api_key="")
        assert adapter_no_key.is_available() is False

        adapter_placeholder = TrendsMCPAdapter(api_key="xxx")
        assert adapter_placeholder.is_available() is False

    def test_scavio_mcp_auth_detection(self):
        """Scavio is available when key is set, unavailable when empty or placeholder."""
        adapter_with_key = ScavioMCPAdapter(api_key="sk_testkey456")
        assert adapter_with_key.is_available() is True

        adapter_no_key = ScavioMCPAdapter(api_key="")
        assert adapter_no_key.is_available() is False

    def test_amazon_india_decodo_proxy_config(self):
        """Amazon India correctly sets up Decodo proxy dictionary when auth is configured."""
        adapter = AmazonIndiaAdapter(use_proxy=True)
        adapter.proxy_auth = "user:pass"
        adapter.proxy_host = "test.proxy.decodo"
        adapter.proxy_port = "8080"
        proxies = adapter._get_proxies()
        assert proxies is not None
        assert proxies["http"] == "http://user:pass@test.proxy.decodo:8080"
        assert proxies["https"] == "http://user:pass@test.proxy.decodo:8080"

    def test_public_sources_always_available(self):
        """Google Trends, GDELT, and Reddit do not require commercial keys."""
        assert GoogleTrendsAdapter().is_available() is True
        assert GDELTResearchAdapter().is_available() is True
        assert RedditResearchAdapter().is_available() is True


# ─────────────────────────────────────────────────────────────────────────────
# 2. SUCCESSFUL, EMPTY, AND MALFORMED RESPONSE TESTS
# ─────────────────────────────────────────────────────────────────────────────
class TestResponseHandling:
    """Verify parsing of valid, empty, and malformed provider responses."""

    def test_trends_mcp_successful_mock_response(self):
        adapter = TrendsMCPAdapter(api_key="mock_key")
        mock_data = [
            {"channel": "google", "query": "air purifier", "trend_score": 92.5, "growth_pct": 25.0},
            {"channel": "amazon", "query": "air purifier", "trend_score": 81.0, "growth_pct": 14.2}
        ]
        results = adapter.fetch_signals("air purifier", mock_response=mock_data)
        assert len(results) == 2
        assert results[0].source == "trends_mcp_google"
        assert results[0].value == 92.5
        assert results[0].signal_type == SignalType.TREND
        assert results[0].unit == "index_0_100"

    def test_scavio_mcp_successful_mock_response(self):
        adapter = ScavioMCPAdapter(api_key="mock_key")
        mock_data = [
            {"competitor": "Competitor X", "price": 1999.0, "weakness": "Loud fan noise", "url": "https://rival.com"}
        ]
        results = adapter.fetch_signals("air purifier", mock_response=mock_data)
        assert len(results) == 1
        assert results[0].signal_type == SignalType.CUSTOMER_PAIN
        assert results[0].value == "Loud fan noise"

    def test_empty_response_handling(self):
        """All adapters return empty list gracefully without throwing exception."""
        adapter = TrendsMCPAdapter(api_key="mock_key")
        results = adapter.fetch_signals("nonexistent_rare_query_xyz", mock_response=[])
        assert results == []

    def test_malformed_response_handling(self):
        """Malformed payloads with missing fields are handled safely."""
        adapter = TrendsMCPAdapter(api_key="mock_key")
        malformed = [{"invalid_key": 123}, {"channel": None}]
        results = adapter.fetch_signals("test", mock_response=malformed)
        assert isinstance(results, list)
        for r in results:
            assert isinstance(r, NormalizedEvidence)


# ─────────────────────────────────────────────────────────────────────────────
# 3. TIMEOUT, RATE LIMIT, AND PROVIDER ERROR ISOLATION TESTS
# ─────────────────────────────────────────────────────────────────────────────
class TestErrorHandlingAndIsolation:
    """Verify timeout, rate limit (429), and HTTP 500 error handling."""

    @patch("requests.get")
    def test_timeout_isolated_without_crashing(self, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout("Connection timed out")
        adapter = TrendsMCPAdapter(api_key="test_key")
        
        # Must return empty list, record error, and not crash
        results = adapter.fetch_signals("test query")
        assert results == []
        health = adapter.health_check()
        assert health.consecutive_errors >= 1
        assert "timed out" in (health.last_error or "").lower()

    @patch("requests.get")
    def test_rate_limit_429_handling(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Too Many Requests"
        mock_get.return_value = mock_response

        adapter = TrendsMCPAdapter(api_key="test_key")
        results = adapter.fetch_signals("test query")
        assert results == []
        assert adapter.consecutive_errors >= 1

    @patch("requests.get")
    def test_provider_server_error_500_handling(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_get.return_value = mock_response

        adapter = TrendsMCPAdapter(api_key="test_key")
        results = adapter.fetch_signals("test query")
        assert results == []
        assert adapter.consecutive_errors >= 1


# ─────────────────────────────────────────────────────────────────────────────
# 4. NORMALIZATION, PROVENANCE, AND IDEMPOTENCY TESTS
# ─────────────────────────────────────────────────────────────────────────────
class TestNormalizationAndProvenance:
    """Verify evidence integrity, tampering signatures, and deduplication."""

    def test_evidence_normalizer_generates_valid_record(self):
        ev = EvidenceNormalizer.normalize_record(
            source_name="google_trends",
            source_type="PUBLIC_API",
            entity="portable blender",
            signal_type=SignalType.DEMAND,
            value=84.0,
            unit="index_0_100",
            confidence=0.88,
            source_url="https://trends.google.com",
            raw_payload={"query": "portable blender", "interest": 84}
        )
        assert ev.entity == "portable blender"
        assert ev.value == 84.0
        assert ev.confidence == 0.88
        assert ev.evidence_type == EvidenceType.OBSERVED_SIGNAL
        assert ProvenanceTracker.verify_provenance(ev) is True

    def test_provenance_tamper_detection(self):
        ev = EvidenceNormalizer.normalize_record(
            source_name="google_trends",
            source_type="PUBLIC_API",
            entity="water bottle",
            signal_type=SignalType.DEMAND,
            value=50.0,
            unit="index_0_100"
        )
        # Valid initially
        assert ProvenanceTracker.verify_provenance(ev) is True

        # Tampering with source name breaks verification
        ev.source = "forged_source_name"
        assert ProvenanceTracker.verify_provenance(ev) is False

    def test_idempotency_and_deduplication(self):
        ev1 = EvidenceNormalizer.normalize_record(
            source_name="reddit",
            source_type="PUBLIC_FEED",
            entity="desk mat",
            signal_type=SignalType.CUSTOMER_PAIN,
            value="Edges fraying",
            unit="complaint_post",
            observed_at="2026-10-01T12:00:00Z"
        )
        ev2 = EvidenceNormalizer.normalize_record(
            source_name="reddit",
            source_type="PUBLIC_FEED",
            entity="desk mat",
            signal_type=SignalType.CUSTOMER_PAIN,
            value="Edges fraying",
            unit="complaint_post",
            observed_at="2026-10-01T12:00:00Z"
        )
        seen = set()
        assert ProvenanceTracker.check_duplicate(ev1, seen) is False
        assert ProvenanceTracker.check_duplicate(ev2, seen) is True


# ─────────────────────────────────────────────────────────────────────────────
# 5. ANTI-HALLUCINATION BOUNDARY ENFORCEMENT
# ─────────────────────────────────────────────────────────────────────────────
class TestAntiHallucinationEnforcement:
    """Verify that external signals cannot masquerade as verified sales or decisions."""

    def test_external_source_cannot_claim_decision_evidence_type(self):
        """If a raw adapter claims DECISION or PREDICTION, normalizer downgrades to ESTIMATE."""
        ev = EvidenceNormalizer.normalize_record(
            source_name="trendwatch",
            source_type="ANALYTICS",
            entity="smart watch",
            signal_type=SignalType.TREND,
            value=95.0,
            unit="velocity",
            claimed_evidence_type=EvidenceType.DECISION  # Attempting illegal classification
        )
        assert ev.evidence_type != EvidenceType.DECISION
        assert ev.evidence_type == EvidenceType.ESTIMATE

    def test_trend_signal_is_not_sales(self):
        """A trend signal is typed as TREND or DEMAND, never SALES."""
        ev = EvidenceNormalizer.normalize_record(
            source_name="tiktok",
            source_type="SOCIAL_FEED",
            entity="#cleaninghack",
            signal_type=SignalType.ENGAGEMENT,
            value=1000000,
            unit="hashtag_views"
        )
        assert ev.signal_type == SignalType.ENGAGEMENT
        assert ev.unit == "hashtag_views"
        assert ev.evidence_type == EvidenceType.OBSERVED_SIGNAL


# ─────────────────────────────────────────────────────────────────────────────
# 6. CONFLICT DETECTION TESTS (NON-BLIND AVERAGING)
# ─────────────────────────────────────────────────────────────────────────────
class TestConflictDetection:
    """Verify that divergent signals produce structured conflicts without blind averaging."""

    def test_divergent_demand_signals_detected_as_conflict(self):
        ev_trends = EvidenceNormalizer.normalize_record(
            source_name="google_trends",
            source_type="PUBLIC_API",
            entity="yoga mat",
            signal_type=SignalType.DEMAND,
            value=95.0,  # High demand
            unit="index_0_100",
            observed_at="2026-10-01T12:00:00Z"
        )
        ev_mcp = EvidenceNormalizer.normalize_record(
            source_name="trends_mcp_google",
            source_type="MCP",
            entity="yoga mat",
            signal_type=SignalType.DEMAND,
            value=20.0,  # Very low demand -> divergence > 70%
            unit="index_0_100",
            observed_at="2026-10-01T12:00:00Z"
        )

        conflicts = EvidenceNormalizer.detect_conflicts([ev_trends, ev_mcp], divergence_threshold=0.35)
        assert len(conflicts) == 1
        conf = conflicts[0]
        assert conf.entity == "yoga mat"
        assert conf.signal_type == SignalType.DEMAND
        assert conf.conflict_type == "MAGNITUDE_DIVERGENCE"
        assert conf.divergence_score > 0.5
        assert conf.resolution_status == "UNRESOLVED"
        # Provenance of both sources preserved
        assert conf.source_a in ["google_trends", "trends_mcp_google"]
        assert conf.source_b in ["google_trends", "trends_mcp_google"]

    def test_consistent_signals_do_not_produce_conflict(self):
        ev1 = EvidenceNormalizer.normalize_record(
            source_name="source_a", source_type="API", entity="earbuds",
            signal_type=SignalType.DEMAND, value=80.0, unit="index_0_100"
        )
        ev2 = EvidenceNormalizer.normalize_record(
            source_name="source_b", source_type="API", entity="earbuds",
            signal_type=SignalType.DEMAND, value=85.0, unit="index_0_100"
        )
        conflicts = EvidenceNormalizer.detect_conflicts([ev1, ev2], divergence_threshold=0.35)
        assert len(conflicts) == 0


# ─────────────────────────────────────────────────────────────────────────────
# 7. REGISTRY ORCHESTRATION & FAILURE ISOLATION
# ─────────────────────────────────────────────────────────────────────────────
class TestRegistryOrchestration:
    """Verify registry aggregation, health checks, and cross-source failure isolation."""

    def test_registry_contains_all_11_sources(self):
        reg = ResearchSourceRegistry.get_instance()
        sources = reg.list_sources()
        expected = [
            "trends_mcp", "scavio_mcp", "amazon_india", "google_trends",
            "reddit", "youtube", "gdelt", "trendwatch", "tiktok", "rivalsearch", "trendscope"
        ]
        for exp in expected:
            assert exp in sources

    def test_registry_failure_isolation(self):
        """If one adapter crashes with an exception, others still deliver evidence."""
        reg = ResearchSourceRegistry.get_instance()
        
        # Inject mock failure into one adapter
        failing_adapter = reg.get_adapter("gdelt")
        original_fetch = failing_adapter.fetch_signals
        failing_adapter.fetch_signals = MagicMock(side_effect=RuntimeError("GDELT API down"))

        try:
            # Query registry
            evidence, conflicts = reg.fetch_all_signals("ergonomic chair", limit_per_source=2)
            assert isinstance(evidence, list)
            # Other sources succeeded despite GDELT failure
            assert len(evidence) > 0
        finally:
            failing_adapter.fetch_signals = original_fetch

    def test_health_sync_to_sqlite(self, tmp_path):
        """Verify health metrics write to SQLite without schema error."""
        import sqlite3
        test_db = str(tmp_path / "test_health.db")
        conn = sqlite3.connect(test_db)
        conn.execute("""
            CREATE TABLE source_health (
                source_id TEXT PRIMARY KEY,
                source_name TEXT UNIQUE,
                data_type TEXT,
                last_successful_fetch TEXT,
                failure_count INTEGER,
                freshness_status TEXT,
                response_time_ms REAL,
                details_json TEXT,
                updated_at TEXT
            )
        """)
        conn.commit()
        conn.close()

        reg = ResearchSourceRegistry.get_instance()
        reg.sync_health_to_db(test_db)

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM source_health")
        count = cursor.fetchone()[0]
        assert count == 11
        conn.close()
