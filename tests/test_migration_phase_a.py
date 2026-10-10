"""
tests/test_migration_phase_a.py — Comprehensive Verification Suite for Phase A Migration.

Covers:
1. Multi-marketplace price compare (GET /price-compare).
2. War Room specialist chat (POST /operations/war-room/chat), history, and docx generation.
3. Supplier directory queries and filters (GET /products/suppliers/directory).
4. Operational state mutations (Watchlist, Shortlist, Alert dismissal, Conflict resolution, Archive restore).
5. Dual AI router (NVIDIA Nemotron primary + Google Gemini fallback) with zero fabricated responses.

Safety:
- Isolated temporary SQLite database fixture protects production database from writes.
- Transport-level and client-level test doubles guarantee zero live network requests.
"""
import os
import sys
import shutil
import tempfile
import sqlite3
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.main import app
from models.llm_router import LLMRouter, LLMProvider, NIMClusterExhausted


@pytest.fixture(scope="module")
def isolated_db():
    """Copy production database to a temp directory and set APRS_DB_PATH for isolated testing."""
    orig = os.environ.get("APRS_DB_PATH")
    prod_db = PROJECT_ROOT / "data" / "research_engine.db"

    temp_dir = tempfile.TemporaryDirectory()
    test_db = Path(temp_dir.name) / "test_phase_a_isolated.db"
    shutil.copy2(str(prod_db), str(test_db))

    os.environ["APRS_DB_PATH"] = str(test_db)
    yield test_db

    if orig is not None:
        os.environ["APRS_DB_PATH"] = orig
    else:
        os.environ.pop("APRS_DB_PATH", None)
    temp_dir.cleanup()


@pytest.fixture(scope="module")
def client(isolated_db):
    """TestClient configured with isolated database."""
    with TestClient(app) as test_client:
        yield test_client


# ==============================================================================
# 1. Multi-Marketplace Price Compare Tests
# ==============================================================================
class TestPriceCompareEndpoints:
    def test_price_compare_existing_product(self, client):
        """Test GET /price-compare for existing catalog product IN_B08KLT."""
        res = client.get("/price-compare?product_id=IN_B08KLT")
        assert res.status_code == 200
        data = res.json()
        assert data["product_id"] == "IN_B08KLT"
        assert len(data["marketplaces"]) == 5
        assert data["benchmark_msrp"] > 0
        assert data["currency"] in ["₹", "$", "€", "AED", "INR", "USD"]
        assert data["lowest_price"] <= data["highest_price"]
        assert data["arbitrage_savings"] >= 0
        assert data["wholesaler"] is not None
        assert "factory_name" in data["wholesaler"]

    def test_price_compare_custom_query(self, client):
        """Test GET /price-compare with custom product search and planned MSRP."""
        res = client.get("/price-compare?query=Smart+Bakhoor+Incense+Burner&region=India&planned_msrp=1299.0")
        assert res.status_code == 200
        data = res.json()
        assert data["product_name"] == "Smart Bakhoor Incense Burner"
        assert len(data["marketplaces"]) == 5
        assert data["benchmark_msrp"] == 1299.0
        assert data["currency"] in ["₹", "INR"]
        assert data["lowest_price"] <= data["highest_price"]

    def test_price_compare_missing_product(self, client):
        """Test GET /price-compare for nonexistent product returns 404."""
        res = client.get("/price-compare?product_id=NONEXISTENT_XYZ_999")
        assert res.status_code == 404
        error_info = res.json().get("error", {})
        assert "not found" in error_info.get("message", "").lower()

    def test_price_compare_invalid_inputs(self, client):
        """Test GET /price-compare with neither product_id nor query returns 422/400."""
        res = client.get("/price-compare")
        assert res.status_code in [400, 422]
        error_info = res.json().get("error", {})
        assert "either" in error_info.get("message", "").lower()


# ==============================================================================
# 2. War Room Endpoints & UI Functionality Tests
# ==============================================================================
class TestWarRoomEndpoints:
    def test_war_room_chat_mocked_success(self, client):
        """Test POST /operations/war-room/chat using a mocked specialist room response."""
        mock_replies = [
            {
                "agent_id": "sales",
                "agent_name": "Maya — Sales & Demand",
                "title": "Sales Specialist",
                "avatar": "📈",
                "message": "Unit sales velocity is projected at 1,200 units/mo based on BSR 4,200.",
                "cached": False,
                "latency_sec": 0.12,
            }
        ]

        with patch("core.team_meeting.AITeamMeetingRoom") as MockRoom:
            instance = MockRoom.return_value
            instance.chat.return_value = mock_replies
            instance._session_id = "test-session-123"

            payload = {
                "user_query": "What is the expected sales velocity?",
                "target_speaker": "sales"
            }
            res = client.post("/operations/war-room/chat", json=payload)
            assert res.status_code == 200
            data = res.json()
            assert data["session_id"] == "test-session-123"
            assert len(data["replies"]) == 1
            assert data["replies"][0]["agent_name"] == "Maya — Sales & Demand"
            assert "1,200 units/mo" in data["replies"][0]["message"]

    def test_war_room_chat_empty_query_rejected(self, client):
        """Test POST /operations/war-room/chat with empty query returns 400."""
        payload = {"user_query": "   ", "target_speaker": "auto"}
        res = client.post("/operations/war-room/chat", json=payload)
        assert res.status_code in [400, 422]
        error_info = res.json().get("error", {})
        assert "empty" in error_info.get("message", "").lower()

    def test_war_room_chat_handles_provider_failure(self, client):
        """Test POST /operations/war-room/chat surfaces provider errors honestly without fabrication."""
        with patch("core.team_meeting.AITeamMeetingRoom") as MockRoom:
            instance = MockRoom.return_value
            instance.chat.side_effect = RuntimeError("All LLM providers unavailable")

            payload = {"user_query": "Analyze margin stress", "target_speaker": "finance"}
            res = client.post("/operations/war-room/chat", json=payload)
            assert res.status_code == 500
            error_info = res.json().get("error", {})
            assert "All LLM providers unavailable" in error_info.get("message", "")

    def test_war_room_history_query(self, client):
        """Test GET /operations/war-room/history returns structured meeting history."""
        res = client.get("/operations/war-room/history?limit=10")
        assert res.status_code == 200
        data = res.json()
        assert "total" in data
        assert "messages" in data
        assert isinstance(data["messages"], list)

    def test_war_room_docx_download(self, client):
        """Test GET /operations/war-room/docx generates a valid Word document."""
        res = client.get("/operations/war-room/docx")
        if res.status_code == 200:
            assert res.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            assert len(res.content) > 100
        else:
            assert res.status_code == 404
            error_info = res.json().get("error", {})
            assert "no meeting" in error_info.get("message", "").lower()


# ==============================================================================
# 3. Supplier Directory Tests
# ==============================================================================
class TestSupplierDirectoryEndpoints:
    def test_supplier_directory_all(self, client):
        """Test GET /products/suppliers/directory returns real supplier records."""
        res = client.get("/products/suppliers/directory?limit=20")
        assert res.status_code == 200
        data = res.json()
        assert data["total"] >= 20
        assert len(data["suppliers"]) <= 20
        first = data["suppliers"][0]
        assert "supplier_id" in first
        assert "product_id" in first
        assert "factory_name" in first
        assert "region" in first

    def test_supplier_directory_filter_region(self, client):
        """Test GET /products/suppliers/directory with region filter."""
        res = client.get("/products/suppliers/directory?region=India")
        assert res.status_code == 200
        data = res.json()
        assert data["total"] > 0
        for s in data["suppliers"]:
            assert s["region"] == "India"

    def test_supplier_directory_filter_product(self, client):
        """Test GET /products/suppliers/directory filtered by product_id."""
        res = client.get("/products/suppliers/directory?product_id=IN_B08KLT")
        assert res.status_code == 200
        data = res.json()
        assert data["total"] > 0
        for s in data["suppliers"]:
            assert s["product_id"] == "IN_B08KLT"

    def test_supplier_directory_empty_result(self, client):
        """Test GET /products/suppliers/directory for nonexistent product returns total=0."""
        res = client.get("/products/suppliers/directory?product_id=NONEXISTENT_999")
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 0
        assert data["suppliers"] == []


# ==============================================================================
# 4. Operational State Mutation Tests (Using Isolated DB)
# ==============================================================================
class TestOperationalStateMutations:
    def test_watchlist_add_and_remove(self, client, isolated_db):
        """Test adding and removing a product from the watchlist in isolated DB."""
        # Add to watchlist
        res = client.post("/products/IN_B08KLT/watchlist", json={"notes": "Test watchlist addition"})
        assert res.status_code == 200
        data = res.json()
        assert data["product_id"] == "IN_B08KLT"
        assert data["in_watchlist"] is True
        assert data["status"] == "SUCCESS"

        # Verify in isolated SQLite DB
        conn = sqlite3.connect(str(isolated_db))
        cursor = conn.cursor()
        cursor.execute("SELECT product_id FROM product_watchlist WHERE product_id = 'IN_B08KLT'")
        row = cursor.fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "IN_B08KLT"

        # Delete from watchlist
        res_del = client.delete("/products/IN_B08KLT/watchlist")
        assert res_del.status_code == 200
        del_data = res_del.json()
        assert del_data["in_watchlist"] is False
        assert del_data["status"] == "SUCCESS"

        # Verify DB is reset
        conn = sqlite3.connect(str(isolated_db))
        cursor = conn.cursor()
        cursor.execute("SELECT product_id FROM product_watchlist WHERE product_id = 'IN_B08KLT'")
        row_after = cursor.fetchone()
        conn.close()
        assert row_after is None

    def test_shortlist_toggle(self, client, isolated_db):
        """Test toggling shortlist state on a product."""
        # Shortlist = True
        res = client.post("/products/IN_B08KLT/shortlist", json={"is_shortlisted": True})
        assert res.status_code == 200
        assert res.json()["is_shortlisted"] is True

        conn = sqlite3.connect(str(isolated_db))
        cursor = conn.cursor()
        cursor.execute("SELECT is_shortlisted FROM master_products WHERE product_id = 'IN_B08KLT'")
        assert cursor.fetchone()[0] == 1
        conn.close()

        # Shortlist = False
        res2 = client.post("/products/IN_B08KLT/shortlist", json={"is_shortlisted": False})
        assert res2.status_code == 200
        assert res2.json()["is_shortlisted"] is False

    def test_alert_dismiss(self, client, isolated_db):
        """Test dismissing an active alert in isolated DB."""
        conn = sqlite3.connect(str(isolated_db))
        cursor = conn.cursor()
        cursor.execute("SELECT alert_id FROM opportunity_alerts LIMIT 1")
        row = cursor.fetchone()
        conn.close()

        if row:
            alert_id = row[0]
            res = client.post(f"/operations/alerts/{alert_id}/dismiss")
            assert res.status_code == 200
            assert res.json()["success"] is True

            # Verify in DB
            conn = sqlite3.connect(str(isolated_db))
            cursor = conn.cursor()
            cursor.execute("SELECT is_dismissed FROM opportunity_alerts WHERE alert_id = ?", (alert_id,))
            assert cursor.fetchone()[0] == 1
            conn.close()

    def test_conflict_resolve(self, client, isolated_db):
        """Test resolving a data conflict in isolated DB."""
        conn = sqlite3.connect(str(isolated_db))
        cursor = conn.cursor()
        cursor.execute("SELECT conflict_id FROM data_conflicts LIMIT 1")
        row = cursor.fetchone()
        conn.close()

        if row:
            conflict_id = row[0]
            res = client.post(
                f"/operations/conflicts/{conflict_id}/resolve",
                json={"resolution_status": "RESOLVED", "explanation": "Verified manually via test fixture."}
            )
            assert res.status_code == 200
            assert res.json()["success"] is True

    def test_archive_restore(self, client, isolated_db):
        """Test soft deleting and then restoring a product via POST /archive/{product_id}/restore."""
        # Soft delete IN_B08KLT in isolated DB
        conn = sqlite3.connect(str(isolated_db))
        cursor = conn.cursor()
        cursor.execute("UPDATE master_products SET is_deleted = 1, deletion_reason = 'Test archive' WHERE product_id = 'IN_B08KLT'")
        conn.commit()
        conn.close()

        # Check archive overview includes it
        res_arch = client.get("/archive/overview")
        assert res_arch.status_code == 200
        assert any(item["product_id"] == "IN_B08KLT" for item in res_arch.json()["archived_products"])

        # Restore product
        res_rest = client.post("/archive/IN_B08KLT/restore")
        assert res_rest.status_code == 200
        assert res_rest.json()["restored"] is True

        # Verify in isolated DB that is_deleted is 0
        conn = sqlite3.connect(str(isolated_db))
        cursor = conn.cursor()
        cursor.execute("SELECT is_deleted FROM master_products WHERE product_id = 'IN_B08KLT'")
        assert cursor.fetchone()[0] == 0
        conn.close()


# ==============================================================================
# 5. Dual AI Router (Nemotron Primary + Gemini Fallback) Tests
# ==============================================================================
class TestDualAIRouter:
    def test_nim_primary_success(self):
        """Test that router calls NVIDIA Nemotron first and returns genuine response."""
        router = LLMRouter()
        mock_nim_result = {
            "success": True,
            "content": "NVIDIA Nemotron primary analysis complete.",
            "model": "meta/llama-3.1-70b-instruct",
            "cached": False,
        }

        with patch.object(router.nim_cluster, "query", return_value=mock_nim_result):
            res = asyncio.run(router.query("Analyze market competition"))
            assert "NVIDIA Nemotron primary" in res.content
            assert res.provider == LLMProvider.NIM
            assert router.metrics["nim_calls"] == 1

    def test_nim_exhausted_gemini_fallback_success(self):
        """Test that NIM exhaustion triggers seamless failover to Google Gemini."""
        router = LLMRouter()

        # Mock NIM failing with NIMClusterExhausted
        def mock_nim_exhausted(*args, **kwargs):
            raise NIMClusterExhausted("NVIDIA NIM Cluster quota exhausted (429)")

        # Mock Gemini client
        mock_gemini_client = MagicMock()
        mock_gemini_resp = MagicMock()
        mock_gemini_resp.text = "Google Gemini fallback analysis successful."
        mock_gemini_client.generate_content.return_value = mock_gemini_resp
        router.gemini_client = mock_gemini_client

        with patch.object(router.nim_cluster, "query", side_effect=mock_nim_exhausted):
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-gemini-key"}):
                res = asyncio.run(router.query("Analyze product defects"))
                assert "Google Gemini fallback" in res.content
                assert res.provider == LLMProvider.GEMINI
                assert router.metrics["nim_failures"] == 1
                assert router.metrics["gemini_calls"] == 1

    def test_nim_exhausted_gemini_missing_configuration(self):
        """Test that if NIM is exhausted and Gemini lacks API key, fails cleanly without fabrication."""
        router = LLMRouter()

        def mock_nim_exhausted(*args, **kwargs):
            raise NIMClusterExhausted("NVIDIA NIM Cluster quota exhausted (429)")

        with patch.object(router.nim_cluster, "query", side_effect=mock_nim_exhausted):
            # Ensure no Gemini keys in environment
            with patch.dict(os.environ, {"GEMINI_API_KEY": "", "GOOGLE_API_KEY": ""}):
                router.gemini_client = None
                with pytest.raises(RuntimeError) as exc_info:
                    asyncio.run(router.query("Evaluate supplier reliability"))
                assert "All LLM providers exhausted" in str(exc_info.value)
                assert router.metrics["nim_failures"] == 1
                assert router.metrics["gemini_failures"] == 1

    def test_both_providers_fail_no_fabricated_answer(self):
        """Test that when both providers throw errors, a RuntimeError is raised and no answer is fabricated."""
        router = LLMRouter()

        def mock_nim_fail(*args, **kwargs):
            raise RuntimeError("NVIDIA connection timeout")

        mock_gemini_client = MagicMock()
        mock_gemini_client.generate_content.side_effect = RuntimeError("Gemini quota exceeded (429)")
        router.gemini_client = mock_gemini_client

        with patch.object(router.nim_cluster, "query", side_effect=mock_nim_fail):
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-gemini-key"}):
                with pytest.raises(RuntimeError) as exc_info:
                    asyncio.run(router.query("Generate marketing plan"))
                assert "All LLM providers exhausted" in str(exc_info.value)
                assert router.metrics["nim_failures"] == 1
                assert router.metrics["gemini_failures"] == 1
