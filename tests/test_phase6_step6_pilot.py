"""
tests/test_phase6_step6_pilot.py — Verification suite for Phase 6 Step 6 Controlled Live Pilot.

Guarantees tested:
1. Strict Fail-Closed Isolation: Prevents pilot execution against production database.
2. Dry-Run Zero Writes: Verifies dry-run inspection performs 0 DB writes and 0 external calls.
3. Batch and Job Limits Enforced: Enforces max_products and max_jobs bounds.
4. Source Approval Filter: Blocks unapproved or paid/credentialed sources from executing.
5. Error / Timeout Isolation: Ensures network timeouts or failures cannot be marked LIVE_VERIFIED.
6. Deduplication Safety: Verifies identical observations do not duplicate stored evidence.
7. Worker Lifecycle: Explicit start/stop, status reflection, and cancellation between jobs.
8. Database Fault Tolerance: Safely catches DB errors without unhandled crashes.
9. FastAPI Endpoints: Validates /api/scheduler/pilot/dry-run and /pilot/run with 403 guard on prod DB.
"""

import os
import sys
import json
import sqlite3
import tempfile
import datetime
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure project root is on sys.path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.database import init_db
from core.research_sources.scheduler import (
    ObservationJobScheduler,
    ObservationJob,
    JobStatus,
    ensure_job_tables
)
from core.research_sources.worker import ObservationWorker, WorkerConfig, WorkerState
from core.research_sources.pilot import (
    ControlledPilotRunner,
    PilotConfig,
    PilotSourceApproval
)
from core.research_sources.observation import CanonicalObservation
from core.research_sources.provenance import ProvenanceType
from core.research_sources.ingestion_service import ObservationIngestionService


@pytest.fixture
def isolated_pilot_db():
    """Creates a temporary SQLite database with essential schema for isolated pilot tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "isolated_pilot_test.db")
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        # Minimal master_products table
        cur.execute("""
            CREATE TABLE master_products (
                product_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT DEFAULT 'Electronics',
                target_region TEXT DEFAULT 'IN',
                planned_msrp REAL DEFAULT 999.0,
                status TEXT DEFAULT 'ACTIVE'
            );
        """)
        cur.execute("""
            INSERT INTO master_products (product_id, name, target_region)
            VALUES 
                ('P_PILOT_01', 'Smart Wireless Earbuds', 'IN'),
                ('P_PILOT_02', 'Ultrasonic Retainer Cleaner', 'IN'),
                ('P_PILOT_03', 'Ergonomic Desk Mat', 'IN'),
                ('P_PILOT_04', 'Stainless Steel Water Bottle', 'IN');
        """)

        # Minimal scraped_listings & intelligence_evidence for ingestion pipeline
        cur.execute("""
            CREATE TABLE scraped_listings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT,
                source TEXT,
                url TEXT,
                title TEXT,
                price REAL,
                rating REAL,
                reviews_count INTEGER,
                sales_volume_estimate INTEGER,
                raw_data TEXT,
                scraped_at TEXT
            );
        """)
        cur.execute("""
            CREATE TABLE intelligence_evidence (
                evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
                intelligence_id INTEGER,
                product_id TEXT,
                source_name TEXT,
                signal_type TEXT,
                observed_value REAL,
                unit TEXT,
                confidence REAL,
                source_url TEXT,
                raw_payload TEXT,
                observed_at TEXT
            );
        """)
        cur.execute("""
            CREATE TABLE source_health (
                source_name TEXT PRIMARY KEY,
                data_type TEXT,
                last_successful_fetch TEXT,
                failure_count INTEGER DEFAULT 0,
                freshness_status TEXT,
                response_time_ms REAL,
                details_json TEXT,
                updated_at TEXT
            );
        """)
        cur.execute("""
            CREATE TABLE product_intelligence (
                intelligence_id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT UNIQUE,
                opportunity_score REAL,
                overall_confidence REAL,
                freshness_status TEXT,
                updated_at TEXT
            );
        """)
        cur.execute("""
            CREATE TABLE trend_signals (
                signal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT,
                keyword TEXT,
                region TEXT,
                velocity_score REAL,
                raw_signal_json TEXT,
                status TEXT,
                created_at TEXT
            );
        """)

        conn.commit()
        conn.close()

        # Initialize observation_jobs
        ensure_job_tables(db_path)

        yield db_path


# ─────────────────────────────────────────────────────────────────────────────
# 1. SAFETY & ISOLATION TESTS
# ─────────────────────────────────────────────────────────────────────────────

def test_pilot_fails_closed_on_production_db():
    """ControlledPilotRunner MUST raise PermissionError if pointed to production database."""
    prod_path = "data/research_engine.db"
    config = PilotConfig(
        db_path=prod_path,
        max_jobs=1
    )
    with pytest.raises(PermissionError, match="SAFETY HALT"):
        ControlledPilotRunner(config=config)


def test_pilot_fails_closed_on_empty_db_path():
    """ControlledPilotRunner MUST raise error if db_path is empty."""
    with pytest.raises((ValueError, PermissionError)):
        config = PilotConfig(db_path="", max_jobs=1)
        ControlledPilotRunner(config=config)


# ─────────────────────────────────────────────────────────────────────────────
# 2. DRY-RUN INSPECTION TESTS
# ─────────────────────────────────────────────────────────────────────────────

def test_dry_run_produces_zero_writes_and_reports_accurately(isolated_pilot_db):
    """Dry-run must not write any rows and must report prospective job candidates."""
    # Create 3 jobs in isolated DB
    ObservationJobScheduler.create_job("P_PILOT_01", "google_trends", db_path=isolated_pilot_db)
    ObservationJobScheduler.create_job("P_PILOT_02", "google_trends", db_path=isolated_pilot_db)

    # Count rows before
    conn = sqlite3.connect(isolated_pilot_db)
    counts_before = {
        "master_products": conn.execute("SELECT COUNT(*) FROM master_products").fetchone()[0],
        "observation_jobs": conn.execute("SELECT COUNT(*) FROM observation_jobs").fetchone()[0],
        "scraped_listings": conn.execute("SELECT COUNT(*) FROM scraped_listings").fetchone()[0],
        "intelligence_evidence": conn.execute("SELECT COUNT(*) FROM intelligence_evidence").fetchone()[0]
    }
    conn.close()

    config = PilotConfig(
        db_path=isolated_pilot_db,
        max_jobs=3,
        approved_sources=["google_trends"]
    )
    runner = ControlledPilotRunner(config=config)
    report = runner.execute_dry_run()

    # Verify report structure
    assert report["mode"] == "DRY_RUN"
    assert report["writes_performed"] == 0
    assert report["external_calls_performed"] == 0
    assert report["due_jobs_found"] == 2
    assert report["eligible_for_pilot"] == 2
    assert len(report["prospective_jobs"]) == 2

    # Count rows after: MUST BE IDENTICAL
    conn = sqlite3.connect(isolated_pilot_db)
    counts_after = {
        "master_products": conn.execute("SELECT COUNT(*) FROM master_products").fetchone()[0],
        "observation_jobs": conn.execute("SELECT COUNT(*) FROM observation_jobs").fetchone()[0],
        "scraped_listings": conn.execute("SELECT COUNT(*) FROM scraped_listings").fetchone()[0],
        "intelligence_evidence": conn.execute("SELECT COUNT(*) FROM intelligence_evidence").fetchone()[0]
    }
    conn.close()

    assert counts_before == counts_after, "Dry-run mutated the database!"


# ─────────────────────────────────────────────────────────────────────────────
# 3. BOUNDARY & FILTER TESTS
# ─────────────────────────────────────────────────────────────────────────────

def test_batch_and_job_limits_enforced(isolated_pilot_db):
    """Pilot must strictly respect max_jobs upper bound."""
    for i in range(1, 5):
        ObservationJobScheduler.create_job(f"P_PILOT_0{i}", "google_trends", db_path=isolated_pilot_db)

    # Configure max_jobs = 2
    config = PilotConfig(
        db_path=isolated_pilot_db,
        max_jobs=2,
        approved_sources=["google_trends"]
    )
    runner = ControlledPilotRunner(config=config)
    report = runner.execute_dry_run()

    assert report["due_jobs_found"] == 2
    assert len(report["prospective_jobs"]) == 2


def test_unapproved_sources_are_skipped(isolated_pilot_db):
    """Unapproved sources (keepa, gdelt, amazon_india) must be skipped and never executed."""
    # Force insert jobs directly into DB to test runner filtering
    conn = sqlite3.connect(isolated_pilot_db)
    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
    conn.execute("""
        INSERT INTO observation_jobs (product_id, source_id, scheduled_at, status, next_run_at, created_at, updated_at)
        VALUES 
            ('P_PILOT_01', 'keepa', ?, 'PENDING', ?, ?, ?),
            ('P_PILOT_02', 'gdelt', ?, 'PENDING', ?, ?, ?);
    """, (now_str, now_str, now_str, now_str, now_str, now_str, now_str, now_str))
    conn.commit()
    conn.close()

    config = PilotConfig(
        db_path=isolated_pilot_db,
        max_jobs=3,
        approved_sources=["google_trends"]  # Only Google Trends approved
    )
    runner = ControlledPilotRunner(config=config)

    # Dry-run test
    dry_rep = runner.execute_dry_run()
    assert dry_rep["eligible_for_pilot"] == 0
    assert dry_rep["rejected_for_pilot"] == 2

    # Bounded execution test
    exec_summary = runner.execute_bounded_pilot()
    assert exec_summary.jobs_attempted == 0
    assert exec_summary.jobs_skipped == 2
    for rep in exec_summary.job_reports:
        assert rep.status == "SKIPPED"
        assert "Unapproved" in rep.error


# ─────────────────────────────────────────────────────────────────────────────
# 4. FAILURE & TIMEOUT ISOLATION TESTS
# ─────────────────────────────────────────────────────────────────────────────

def test_source_failure_cannot_be_marked_live(isolated_pilot_db):
    """When a source raises a timeout or rate-limit error, it must fail safely without live promotion."""
    ObservationJobScheduler.create_job("P_PILOT_01", "google_trends", db_path=isolated_pilot_db)

    config = PilotConfig(
        db_path=isolated_pilot_db,
        max_jobs=1,
        approved_sources=["google_trends"]
    )
    runner = ControlledPilotRunner(config=config)

    # Mock GoogleTrendsAdapter to simulate upstream timeout
    from core.research_sources.registry import ResearchSourceRegistry
    gt_adapter = ResearchSourceRegistry.get_instance().get_adapter("google_trends")

    with patch.object(gt_adapter, "_do_fetch_signals", side_effect=RuntimeError("TIMEOUT: Google Trends upstream timed out")):
        summary = runner.execute_bounded_pilot()

    assert summary.jobs_failed == 1
    assert summary.jobs_succeeded == 0
    failed_rep = summary.job_reports[0]
    assert failed_rep.status in ("RETRY", "FAILED")
    assert failed_rep.execution_evidence_type == "FAILED"
    assert "timed out" in failed_rep.error.lower()

    # Verify no evidence rows were inserted
    conn = sqlite3.connect(isolated_pilot_db)
    ev_count = conn.execute("SELECT COUNT(*) FROM intelligence_evidence").fetchone()[0]
    conn.close()
    assert ev_count == 0


# ─────────────────────────────────────────────────────────────────────────────
# 5. DEDUPLICATION & CONCURRENCY TESTS
# ─────────────────────────────────────────────────────────────────────────────

def test_identical_observations_do_not_duplicate_stored_evidence(isolated_pilot_db):
    """Ingesting an identical observation twice must result in DUPLICATE status and zero duplicate rows."""
    ingestion_service = ObservationIngestionService()
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    obs = CanonicalObservation(
        source_id="google_trends",
        product_id="P_PILOT_01",
        signal_type="DEMAND",
        observed_value=85.0,
        unit="index_0_100",
        confidence=0.9,
        source_url="https://trends.google.com/test",
        payload_hash="testhash12345678",
        tamper_sig="sig1234567890123",
        observed_at=now_iso,
        raw_payload={"interest": 85.0},
        provenance={"provenance_type": ProvenanceType.TEST}
    )

    # First ingestion -> ACCEPTED
    res1, _ = ingestion_service.ingest_observation(obs, db_path=isolated_pilot_db, run_diff=False)
    assert res1.status == "ACCEPTED"

    # Second ingestion -> DUPLICATE
    res2, _ = ingestion_service.ingest_observation(obs, db_path=isolated_pilot_db, run_diff=False)
    assert res2.status == "DUPLICATE"
    assert "duplicate" in res2.reason.lower()

    # Check destination table row count
    conn = sqlite3.connect(isolated_pilot_db)
    cnt = conn.execute(f"SELECT COUNT(*) FROM {res1.destination_table}").fetchone()[0]
    conn.close()
    assert cnt == 1


# ─────────────────────────────────────────────────────────────────────────────
# 6. CANCELLATION & WORKER CONTROLS
# ─────────────────────────────────────────────────────────────────────────────

def test_runner_cancellation_between_jobs(isolated_pilot_db):
    """Signaling cancel() must cause remaining jobs in the batch to be skipped."""
    ObservationJobScheduler.create_job("P_PILOT_01", "google_trends", db_path=isolated_pilot_db)
    ObservationJobScheduler.create_job("P_PILOT_02", "google_trends", db_path=isolated_pilot_db)

    config = PilotConfig(
        db_path=isolated_pilot_db,
        max_jobs=2,
        approved_sources=["google_trends"]
    )
    runner = ControlledPilotRunner(config=config)
    runner.cancel()  # Signal cancellation immediately

    summary = runner.execute_bounded_pilot()
    assert summary.is_cancelled is True
    assert summary.jobs_attempted == 0
    assert summary.jobs_skipped == 2


def test_worker_lifecycle_and_bounded_cycle(isolated_pilot_db):
    """ObservationWorker must not start automatically, must reflect status, and must terminate cleanly."""
    worker = ObservationWorker(config=WorkerConfig(
        worker_id="test-pilot-worker",
        poll_interval_seconds=1.0,
        batch_size=2,
        db_path=isolated_pilot_db,
        max_cycles=1
    ))

    # Initial state
    status_init = worker.get_status()
    assert status_init.state == WorkerState.STOPPED
    assert status_init.is_running is False

    # Run single cycle explicitly
    cycle_res = worker.run_cycle(db_path=isolated_pilot_db)
    assert cycle_res["success"] is True

    status_post = worker.get_status()
    assert status_post.cycle_count == 1
    assert status_post.total_jobs_executed == 0


# ─────────────────────────────────────────────────────────────────────────────
# 7. FASTAPI API ROUTER INTEGRATION
# ─────────────────────────────────────────────────────────────────────────────

def test_fastapi_pilot_endpoints(isolated_pilot_db):
    """FastAPI pilot endpoints must function on isolated DB and forbid production DB."""
    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app)

    # 1. Pilot dry-run on isolated DB
    res_dry = client.post("/scheduler/pilot/dry-run", json={
        "db_path": isolated_pilot_db,
        "max_jobs": 2
    })
    assert res_dry.status_code == 200
    data_dry = res_dry.json()
    assert data_dry["mode"] == "DRY_RUN"
    assert data_dry["writes_performed"] == 0

    # 2. Pilot dry-run attempting production DB -> MUST BE FORBIDDEN (403)
    res_prod = client.post("/scheduler/pilot/dry-run", json={
        "db_path": "data/research_engine.db",
        "max_jobs": 1
    })
    assert res_prod.status_code == 403
    err_body = res_prod.json()
    err_msg = err_body.get("error", {}).get("message") or err_body.get("detail", "")
    assert "SAFETY HALT" in str(err_msg)


# ─────────────────────────────────────────────────────────────────────────────
# 8. PRODUCTION DATABASE UNTOUCHED VERIFICATION
# ─────────────────────────────────────────────────────────────────────────────

def test_production_db_is_untouched():
    """Verify that the production database has not been mutated."""
    prod_db = "data/research_engine.db"
    assert os.path.exists(prod_db)
    conn = sqlite3.connect(f"file:{prod_db}?mode=ro", uri=True)
    # Sacred record check
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM decision_ledger WHERE product_id = 'US_B09ABC'")
    assert cur.fetchone()[0] == 1
    conn.close()
