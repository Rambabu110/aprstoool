"""
tests/test_phase5_production_foundation.py — Phase 5 Test Suite
Focus:
  1. Test Isolation from Production DB
  2. GET Endpoints Read-Only Immutability Verification
  3. Explicit Action / Mutation Endpoints (/products/{id}/refresh, /outcomes/ingest, /scheduler/observe/{id})
  4. Honest Integration / Source State Verification (Keepa without API key, 11 adapters)
  5. Ingestion Provenance and Idempotency
"""
import os
import sys
import shutil
import tempfile
import hashlib
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api.main import app
from tools.keepa_api_client import KeepaAPIClient
from core.research_sources import ResearchSourceRegistry


def file_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


@pytest.fixture(scope="module")
def isolated_db_client():
    """Provides TestClient bound to an isolated temporary copy of the production DB."""
    prod_db = PROJECT_ROOT / "data" / "research_engine.db"
    orig_env = os.environ.get("APRS_DB_PATH")

    temp_dir = tempfile.TemporaryDirectory()
    temp_db_path = Path(temp_dir.name) / "test_phase5_isolated.db"
    shutil.copy2(str(prod_db), str(temp_db_path))

    os.environ["APRS_DB_PATH"] = str(temp_db_path)

    with TestClient(app) as client:
        yield client, temp_db_path

    if orig_env is not None:
        os.environ["APRS_DB_PATH"] = orig_env
    else:
        os.environ.pop("APRS_DB_PATH", None)
    temp_dir.cleanup()


def test_test_environment_isolation(isolated_db_client):
    """Proves that tests are executing against an isolated temporary copy, not production DB."""
    client, temp_db_path = isolated_db_client
    prod_db = PROJECT_ROOT / "data" / "research_engine.db"

    assert str(temp_db_path) != str(prod_db)
    assert os.environ.get("APRS_DB_PATH") == str(temp_db_path)
    assert temp_db_path.exists()
    assert prod_db.exists()


def test_get_endpoints_strict_immutability(isolated_db_client):
    """Proves that calling GET endpoints does NOT mutate the database (SHA256 identical before and after)."""
    client, temp_db_path = isolated_db_client

    sha_before = file_sha256(temp_db_path)
    size_before = temp_db_path.stat().st_size

    # List of critical GET endpoints
    get_endpoints = [
        "/health",
        "/dashboard",
        "/products?page=1&page_size=5",
        "/products/IN_B08KLT",
        "/trends?page=1&page_size=5",
        "/opportunities?page=1&page_size=5",
        "/economics/IN_B08KLT",
        "/operations/jobs",
        "/operations/supervisor-logs?limit=5",
        "/operations/war-room-debate/IN_B08KLT",
        "/db-explorer/overview",
        "/launchpad/summary",
        "/calibration/portfolio-summary",
        "/predictions/catalog?limit=5",
        "/predictions/dossier/IN_B08KLT",
        "/integrations/overview",
        "/telemetry/keepa",
        "/scheduler/daemon",
        "/scheduler/observation-maturity",
        "/outcomes/list",
        "/outcomes/schema",
        "/archive/overview",
    ]

    for ep in get_endpoints:
        resp = client.get(ep)
        assert resp.status_code in (200, 404), f"GET {ep} returned unexpected status {resp.status_code}"

    sha_after = file_sha256(temp_db_path)
    size_after = temp_db_path.stat().st_size

    assert sha_after == sha_before, "CRITICAL: Database SHA256 was mutated during GET requests!"
    assert size_after == size_before, "CRITICAL: Database size changed during GET requests!"


def test_explicit_product_refresh_action(isolated_db_client):
    """Proves that product research refresh is an explicit POST mutation, returning structured result."""
    client, temp_db_path = isolated_db_client

    resp = client.post("/products/IN_B08KLT/refresh")
    assert resp.status_code == 200
    data = resp.json()
    assert data["product_id"] == "IN_B08KLT"
    assert data["success"] is True
    assert "evidence_count" in data
    assert "refreshed_at" in data

    # 404 on nonexistent
    resp_404 = client.post("/products/NONEXISTENT_XYZ_000/refresh")
    assert resp_404.status_code == 404


def test_explicit_outcome_ingest_mutation(isolated_db_client):
    """Proves that outcome ingestion requires explicit POST with valid schema and records provenance."""
    client, temp_db_path = isolated_db_client

    valid_payload = {
        "product_id": "IN_B08KLT",
        "period_start": "2026-10-01",
        "period_end": "2026-10-30",
        "period_type": "DAY_30",
        "actual_units_sold": 150,
        "actual_revenue": 119850.0,
        "actual_landed_cogs": 30000.0,
        "actual_ad_spend": 15000.0,
        "data_source": "phase5_test_adapter"
    }

    resp = client.post("/outcomes/ingest", json=valid_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "outcome_id" in data
    assert data["product_id"] == "IN_B08KLT"
    assert "actual_avg_selling_price" in data["derived_metrics"]


def test_explicit_observation_maturity_trigger(isolated_db_client):
    """Proves that observation trigger requires explicit POST and returns observation job state."""
    client, temp_db_path = isolated_db_client

    resp = client.post("/scheduler/observe/US_B09ABC")
    assert resp.status_code == 200
    data = resp.json()
    assert data["product_id"] == "US_B09ABC"
    assert "observation_job_state" in data
    assert "checked_at" in data


def test_keepa_client_honest_state():
    """Proves Keepa client reports disabled and returns None when no API key is provided."""
    client = KeepaAPIClient(api_key="")
    # With no Keepa API key configured:
    assert client._enabled is False
    assert client.get_product("B09ABC") is None


def test_source_registry_inventory():
    """Proves 11 standardized research source adapters exist in the registry."""
    registry = ResearchSourceRegistry.get_instance()
    names = set(registry.list_sources())
    assert len(names) == 11
    assert "trends_mcp" in names
    assert "amazon_india" in names
    assert "google_trends" in names
    assert "reddit" in names
    assert "youtube" in names
    assert "gdelt" in names
    assert "tiktok" in names
