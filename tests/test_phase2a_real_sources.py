"""
tests/test_phase2a_real_sources.py — Comprehensive Unit & Integration Tests for Phase 2A (Google Trends + GDELT).

Strictly tests:
1. Google Trends Adapter: live format parsing, error isolation, zero-synthetic enforcement, anti-hallucination.
2. GDELT Adapter: TimelineVol & ArtList parsing, rate limit detection, timeout isolation, zero-synthetic enforcement.
3. Real Source Health Semantics: INITIALIZED != ONLINE, error states (RATE_LIMITED, DEGRADED), true success.
4. Database Persistence: SQLite intelligence_evidence insertion, complete provenance preservation in details JSON.
5. Idempotency: Duplicate prevention on re-runs.
6. Failure Isolation: Google Trends failure does not crash GDELT; GDELT failure does not crash Google Trends.
7. Conflict Detection: Semantic respect (DEMAND vs NEWS are never falsely conflicted).
"""

import pytest
import os
import json
import sqlite3
import tempfile
from unittest.mock import patch, MagicMock

import core.database
from core.research_sources.base import (
    EvidenceType,
    SignalType,
    SourceHealth,
    NormalizedEvidence
)
from core.research_sources.google_trends import GoogleTrendsAdapter
from core.research_sources.gdelt import GDELTResearchAdapter
from core.research_sources.registry import ResearchSourceRegistry
from core.research_sources.normalizer import EvidenceNormalizer
from core.research_sources.provenance import ProvenanceTracker


from pathlib import Path


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """Creates a temporary SQLite database with the full APRS schema and a test product."""
    test_db = str(tmp_path / "test_research.db")
    monkeypatch.setenv("APRS_DB_PATH", test_db)
    core.database.DB_PATH = Path(test_db)
    core.database.init_db()

    conn = sqlite3.connect(test_db)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO master_products (product_id, name, category, region, planned_msrp)
        VALUES ('TEST_PROD_101', 'Smart Air Purifier', 'Appliances', 'IN', 8999.0)
    """)
    conn.commit()
    conn.close()
    return test_db



# ─────────────────────────────────────────────────────────────────────────────
# 1. GOOGLE TRENDS ADAPTER TESTS
# ─────────────────────────────────────────────────────────────────────────────
class TestGoogleTrendsRealAdapter:
    """Verifies Google Trends adapter integration, error handling, and zero fake data rules."""

    def test_google_trends_mock_mode(self):
        """When mock response is provided, returns normalized observed signals."""
        adapter = GoogleTrendsAdapter()
        mock_data = {
            "interest_index": 72.0,
            "rising_queries": ["air purifier filter", "best hepa purifier"]
        }
        evs = adapter.fetch_signals("air purifier", mock_response=mock_data)
        assert len(evs) == 3
        # Main demand signal
        assert evs[0].source == "google_trends"
        assert evs[0].signal_type == SignalType.DEMAND
        assert evs[0].value == 72.0
        assert evs[0].evidence_type == EvidenceType.OBSERVED_SIGNAL
        # Keyword signals
        assert evs[1].signal_type == SignalType.KEYWORD
        assert evs[1].entity == "air purifier filter"
        assert evs[1].evidence_type == EvidenceType.OBSERVED_SIGNAL

    def test_google_trends_empty_query_raises_value_error(self):
        """Empty or whitespace query raises ValueError and is recorded as INVALID_QUERY."""
        adapter = GoogleTrendsAdapter()
        evs = adapter.fetch_signals("   ")
        assert evs == []
        assert adapter.consecutive_errors >= 1
        assert "INVALID_QUERY" in (adapter.last_error or "")

    def test_google_trends_rejects_synthetic_suggest_fallback(self):
        """
        CRITICAL OPERATING RULE 3:
        If RealGoogleTrendsEngine falls back to google_suggest_live (sine-wave synthesis),
        the adapter must REJECT it and return empty list, never emitting fake 50.0 evidence.
        """
        adapter = GoogleTrendsAdapter()
        fake_synthetic_engine = MagicMock()
        fake_synthetic_engine.get_interest_over_time.return_value = {
            "success": True,
            "keyword": "test",
            "current_interest": 45,
            "source": "google_suggest_live"  # Synthetic fallback!
        }
        adapter._engine = fake_synthetic_engine

        evs = adapter.fetch_signals("test")
        assert evs == []
        assert adapter.consecutive_errors >= 1
        assert "UNAVAILABLE" in (adapter.last_error or "")

    def test_google_trends_handles_rate_limit_429(self):
        """When Google Trends returns 429, adapter records RATE_LIMITED and returns []."""
        adapter = GoogleTrendsAdapter()
        failing_engine = MagicMock()
        failing_engine.get_interest_over_time.return_value = {
            "success": False,
            "error": "too many 429 error responses"
        }
        adapter._engine = failing_engine

        evs = adapter.fetch_signals("test")
        assert evs == []
        assert adapter.consecutive_errors >= 1
        assert "RATE_LIMITED" in (adapter.last_error or "")

    def test_google_trends_handles_timeout(self):
        """When Google Trends times out, adapter records TIMEOUT and returns []."""
        adapter = GoogleTrendsAdapter()
        failing_engine = MagicMock()
        failing_engine.get_interest_over_time.return_value = {
            "success": False,
            "error": "Connection timed out"
        }
        adapter._engine = failing_engine

        evs = adapter.fetch_signals("test")
        assert evs == []
        assert adapter.consecutive_errors >= 1
        assert "TIMEOUT" in (adapter.last_error or "")

    def test_google_trends_no_hardcoded_50_fallback(self):
        """Ensures that any general exception results in empty list, NEVER hardcoded 50.0."""
        adapter = GoogleTrendsAdapter()
        failing_engine = MagicMock()
        failing_engine.get_interest_over_time.side_effect = RuntimeError("Explosive network failure")
        adapter._engine = failing_engine

        evs = adapter.fetch_signals("test")
        assert evs == []
        for e in evs:
            assert e.value != 50.0


# ─────────────────────────────────────────────────────────────────────────────
# 2. GDELT RESEARCH ADAPTER TESTS
# ─────────────────────────────────────────────────────────────────────────────
class TestGDELTRealAdapter:
    """Verifies GDELT adapter integration, rate limit handling, and zero fake data rules."""

    def test_gdelt_mock_mode(self):
        """When mock response is provided, returns normalized news evidence."""
        adapter = GDELTResearchAdapter()
        mock_data = [
            {"title": "Surge in Eco Products", "url": "https://news.com/1", "seendate": "20261001T120000Z"}
        ]
        evs = adapter.fetch_signals("eco product", mock_response=mock_data)
        assert len(evs) == 1
        assert evs[0].source == "gdelt"
        assert evs[0].signal_type == SignalType.NEWS
        assert evs[0].value == "Surge in Eco Products"
        assert evs[0].evidence_type == EvidenceType.OBSERVED_SIGNAL

    def test_gdelt_empty_query_raises_value_error(self):
        """Empty query raises ValueError and is recorded as INVALID_QUERY."""
        adapter = GDELTResearchAdapter()
        evs = adapter.fetch_signals("")
        assert evs == []
        assert adapter.consecutive_errors >= 1
        assert "INVALID_QUERY" in (adapter.last_error or "")

    @patch("requests.get")
    def test_gdelt_parses_real_timelinevol_json(self, mock_get):
        """When GDELT returns 200 with TimelineVol JSON, extracts intensity and normalizes."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_dict = {
            "query_details": {"title": "retail", "date_resolution": "day"},
            "timeline": [
                {
                    "series": "Volume Intensity",
                    "data": [
                        {"date": "20260930T000000Z", "value": 1.25},
                        {"date": "20261001T000000Z", "value": 1.45}
                    ]
                }
            ]
        }
        mock_resp.text = json.dumps(mock_dict)
        mock_resp.json.return_value = mock_dict
        mock_get.return_value = mock_resp

        adapter = GDELTResearchAdapter()
        adapter._pace_gdelt_request = MagicMock()  # Skip sleep during unit test
        evs = adapter.fetch_signals("retail")

        assert len(evs) == 1
        ev = evs[0]
        assert ev.source == "gdelt"
        assert ev.signal_type == SignalType.NEWS
        assert ev.value == 1.45
        assert ev.unit == "volume_intensity_pct"
        assert ev.evidence_type == EvidenceType.OBSERVED_SIGNAL
        assert ev.observed_at == "20261001T000000Z"
        assert adapter.health_check().is_healthy is True

    @patch("requests.get")
    def test_gdelt_handles_rate_limit_429_text(self, mock_get):
        """When GDELT sheds load with 429 text, records RATE_LIMITED without crashing."""
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.text = "Please limit requests to one every 5 seconds or contact kalev..."
        mock_get.return_value = mock_resp

        adapter = GDELTResearchAdapter()
        adapter._pace_gdelt_request = MagicMock()
        evs = adapter.fetch_signals("retail")

        assert evs == []
        assert adapter.consecutive_errors >= 1
        assert "RATE_LIMITED" in (adapter.last_error or "")
        health = adapter.health_check()
        assert health.status_message == "RATE_LIMITED"

    @patch("requests.get")
    def test_gdelt_handles_timeout(self, mock_get):
        """When GDELT times out, records TIMEOUT and returns []."""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout("Read timed out after 15s")

        adapter = GDELTResearchAdapter()
        adapter._pace_gdelt_request = MagicMock()
        evs = adapter.fetch_signals("retail")

        assert evs == []
        assert adapter.consecutive_errors >= 1
        assert "TIMEOUT" in (adapter.last_error or "")

    @patch("requests.get")
    def test_gdelt_handles_server_error_500(self, mock_get):
        """When GDELT returns 500 error, records HTTP_ERROR."""
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_get.return_value = mock_resp

        adapter = GDELTResearchAdapter()
        adapter._pace_gdelt_request = MagicMock()
        evs = adapter.fetch_signals("retail")

        assert evs == []
        assert adapter.consecutive_errors >= 1
        assert "HTTP_ERROR" in (adapter.last_error or "")


# ─────────────────────────────────────────────────────────────────────────────
# 3. REAL SOURCE HEALTH SEMANTICS
# ─────────────────────────────────────────────────────────────────────────────
class TestRealSourceHealthSemantics:
    """Verifies that INITIALIZED != ONLINE and health reflects actual operations."""

    def test_newly_created_adapter_is_not_online(self):
        """A source with 0 calls must NOT report ONLINE."""
        adapter = GoogleTrendsAdapter()
        health = adapter.health_check()
        assert health.is_healthy is False
        assert health.status_message == "INITIALIZED (UNPROBED)"
        assert health.last_successful_run is None

    def test_adapter_becomes_online_only_after_success(self):
        """A source becomes ONLINE only after a successful fetch."""
        adapter = GoogleTrendsAdapter()
        mock_data = {"interest_index": 80.0, "rising_queries": []}
        adapter.fetch_signals("air purifier", mock_response=mock_data)

        health = adapter.health_check()
        assert health.is_healthy is True
        assert health.status_message == "ONLINE"
        assert health.last_successful_run is not None

    def test_adapter_records_error_and_degrades(self):
        """A source after an error reports DEGRADED or RATE_LIMITED, not ONLINE."""
        adapter = GoogleTrendsAdapter()
        adapter.record_error("RATE_LIMITED: 429 Too Many Requests")

        health = adapter.health_check()
        assert health.is_healthy is False
        assert health.status_message == "RATE_LIMITED"
        assert health.consecutive_errors == 1


# ─────────────────────────────────────────────────────────────────────────────
# 4. DATABASE PERSISTENCE, PROVENANCE, AND IDEMPOTENCY
# ─────────────────────────────────────────────────────────────────────────────
class TestPersistenceAndProvenance:
    """Verifies SQLite persistence, tamper-evident provenance, and idempotency."""

    def test_persist_evidence_to_db(self, isolated_db):
        """Normalized evidence is persisted into intelligence_evidence with provenance."""
        reg = ResearchSourceRegistry.get_instance()
        
        ev = EvidenceNormalizer.normalize_record(
            source_name="google_trends",
            source_type="PUBLIC_API",
            entity="Smart Air Purifier",
            signal_type=SignalType.DEMAND,
            value=65.0,
            unit="index_0_100",
            source_url="https://trends.google.com/trends/explore?geo=IN&q=Smart+Air+Purifier",
            raw_payload={"query": "Smart Air Purifier", "interest": 65}
        )

        persisted_ids = reg.persist_evidence_to_db([ev], product_id="TEST_PROD_101", db_path=isolated_db)
        assert len(persisted_ids) == 1

        conn = sqlite3.connect(isolated_db)
        cur = conn.cursor()
        cur.execute("SELECT product_id, signal_type, conclusion, evidence_status, confidence, source, evidence_details_json FROM intelligence_evidence WHERE evidence_id = ?", (persisted_ids[0],))
        row = cur.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == "TEST_PROD_101"
        assert row[1] == "DEMAND"
        assert "Google Trends Interest Index: 65.0/100" in row[2]
        assert row[3] == "VERIFIED"
        assert row[4] == 80.0
        assert row[5] == "google_trends"

        # Verify provenance in details JSON
        details = json.loads(row[6])
        assert details["source"] == "google_trends"
        assert details["evidence_type"] == "OBSERVED_SIGNAL"
        assert details["tamper_sig"] is not None
        assert details["payload_sha256"] is not None
        assert details["dedup_hash"] is not None

    def test_idempotency_prevents_duplicate_evidence_rows(self, isolated_db):
        """Persisting the exact same evidence twice must not duplicate rows."""
        reg = ResearchSourceRegistry.get_instance()
        ev = EvidenceNormalizer.normalize_record(
            source_name="google_trends",
            source_type="PUBLIC_API",
            entity="Smart Air Purifier",
            signal_type=SignalType.DEMAND,
            value=65.0,
            unit="index_0_100"
        )

        ids_1 = reg.persist_evidence_to_db([ev], product_id="TEST_PROD_101", db_path=isolated_db)
        ids_2 = reg.persist_evidence_to_db([ev], product_id="TEST_PROD_101", db_path=isolated_db)

        assert ids_1 == ids_2

        conn = sqlite3.connect(isolated_db)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM intelligence_evidence WHERE product_id = 'TEST_PROD_101'")
        count = cur.fetchone()[0]
        conn.close()

        assert count == 1, "Idempotency violated: duplicate rows were inserted!"

    def test_health_sync_records_null_for_unprobed_source(self, isolated_db):
        """sync_health_to_db writes NULL for last_successful_fetch if never probed."""
        reg = ResearchSourceRegistry.get_instance()
        # Reset adapter operational state
        gt = reg.get_adapter("google_trends")
        gt.last_successful_run = None
        gt.consecutive_errors = 0
        gt.total_calls = 0

        reg.sync_health_to_db(isolated_db)

        conn = sqlite3.connect(isolated_db)
        cur = conn.cursor()
        cur.execute("SELECT freshness_status, last_successful_fetch FROM source_health WHERE source_name = 'google_trends'")
        row = cur.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == "UNPROBED"
        assert row[1] is None, "Fabricated timestamp detected: last_successful_fetch should be NULL!"


# ─────────────────────────────────────────────────────────────────────────────
# 5. REGISTRY FAILURE ISOLATION & CONFLICT RESPECT
# ─────────────────────────────────────────────────────────────────────────────
class TestRegistryPhase2AIsolation:
    """Verifies that Google Trends and GDELT operate with strict mutual isolation."""

    def test_google_trends_failure_does_not_crash_gdelt(self):
        """If Google Trends fails, GDELT still delivers evidence."""
        reg = ResearchSourceRegistry.get_instance()
        gt = reg.get_adapter("google_trends")
        gdelt = reg.get_adapter("gdelt")

        # Mock GT failure
        orig_gt_fetch = gt.fetch_signals
        gt.fetch_signals = MagicMock(side_effect=RuntimeError("Google Trends outage"))

        # Mock GDELT success
        orig_gdelt_fetch = gdelt.fetch_signals
        gdelt.fetch_signals = MagicMock(return_value=[
            EvidenceNormalizer.normalize_record(
                source_name="gdelt",
                source_type="PUBLIC_API",
                entity="air purifier",
                signal_type=SignalType.NEWS,
                value=1.5,
                unit="volume_intensity_pct"
            )
        ])

        try:
            evidence, conflicts = reg.fetch_phase2a_signals("air purifier")
            assert len(evidence) == 1
            assert evidence[0].source == "gdelt"
        finally:
            gt.fetch_signals = orig_gt_fetch
            gdelt.fetch_signals = orig_gdelt_fetch

    def test_semantic_respect_prevents_false_conflicts(self):
        """DEMAND (0-100) and NEWS (intensity %) must not be compared as conflicting."""
        ev_gt = EvidenceNormalizer.normalize_record(
            source_name="google_trends",
            source_type="PUBLIC_API",
            entity="air purifier",
            signal_type=SignalType.DEMAND,
            value=75.0,
            unit="index_0_100"
        )
        ev_gdelt = EvidenceNormalizer.normalize_record(
            source_name="gdelt",
            source_type="PUBLIC_API",
            entity="air purifier",
            signal_type=SignalType.NEWS,
            value=1.5,
            unit="volume_intensity_pct"
        )

        conflicts = EvidenceNormalizer.detect_conflicts([ev_gt, ev_gdelt])
        assert len(conflicts) == 0, "False conflict detected between different signal types!"
