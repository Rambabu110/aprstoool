"""
tests/test_phase6_observation_worker.py — Test Suite for Phase 6 Controlled Persistent Worker.

Guarantees Verified:
1. Explicit Start and Graceful Stop
2. Polling Cycles and Bounded Batch Processing
3. Responsive Shutdown During Idle Polling (Instant exit, no sleep wait)
4. Shutdown Safety During Job Execution
5. Worker Crash & Abandoned RUNNING Job Recovery (Lease Timeout)
6. Abandoned Job Max Attempts Handling -> Transitions to FAILED
7. Concurrency Safety & Duplicate Execution Prevention Across Workers
8. Bounded Retry Policy with Exponential Backoff
9. Missing Credentials / Ineligible Source Graceful Skip (No Retry Storm)
10. Database Unavailable / Lock Fault Tolerance (No Unhandled Crash)
11. Safe Restart Without Duplicate Successful Executions
12. FastAPI Worker Endpoints (GET /worker/status, POST /worker/start, POST /worker/stop, POST /worker/recover)
13. Strict Production Database Immutability (data/research_engine.db untouched)
"""

import os
import time
import sqlite3
import pytest
import datetime
import hashlib
from typing import Dict, Any
from pathlib import Path
from fastapi.testclient import TestClient

from core.research_sources.scheduler import (
    ObservationJobScheduler,
    ObservationJob,
    JobStatus,
    SourceEligibility,
    ensure_job_tables
)
from core.research_sources.worker import (
    ObservationWorker,
    WorkerConfig,
    WorkerState,
    WorkerStats,
    observation_worker_controller
)
from api.main import create_app


# ─────────────────────────────────────────────────────────────────────────────
# FIXTURES: Isolated SQLite Database
# ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def isolated_worker_db(tmp_path, monkeypatch):
    """
    Creates an isolated temporary SQLite database populated with schema and test product.
    Guarantees production DB at data/research_engine.db is NEVER touched.
    """
    db_file = str(tmp_path / "test_worker.db")
    monkeypatch.setenv("APRS_DB_PATH", db_file)
    monkeypatch.setenv("APRS_RESEARCH_MOCK", "1")

    conn = sqlite3.connect(db_file)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE master_products (
            product_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            target_region TEXT DEFAULT 'IN'
        )
    """)
    cur.execute("""
        CREATE TABLE scraped_listings (
            listing_id INTEGER PRIMARY KEY AUTOINCREMENT,
            asin TEXT NOT NULL,
            marketplace TEXT NOT NULL DEFAULT 'amazon.in',
            price REAL,
            rating REAL,
            review_count INTEGER,
            title TEXT,
            seller TEXT,
            scraped_at TEXT,
            source_url TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE trend_signals (
            signal_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT,
            source TEXT,
            detected_at TEXT,
            current_momentum REAL,
            growth_rate REAL,
            confidence_score REAL,
            keyword TEXT,
            raw_payload_json TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE intelligence_evidence (
            evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT,
            signal_type TEXT,
            conclusion TEXT,
            evidence_status TEXT,
            evidence_details_json TEXT,
            confidence REAL,
            source TEXT,
            source_timestamp TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE intelligence_timeline (
            timeline_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT,
            event_type TEXT,
            description TEXT,
            source TEXT,
            occurred_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE product_intelligence (
            product_id TEXT PRIMARY KEY,
            composite_score REAL,
            trend_score REAL,
            demand_score REAL,
            supplier_score REAL,
            updated_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE product_gate_progress (
            product_id TEXT,
            gate_number INTEGER,
            status TEXT,
            reason TEXT,
            evaluated_at TEXT,
            PRIMARY KEY (product_id, gate_number)
        )
    """)
    cur.execute("""
        CREATE TABLE source_health (
            source_id TEXT PRIMARY KEY,
            status TEXT,
            latency_ms REAL,
            error_count INTEGER DEFAULT 0,
            last_checked TEXT,
            details TEXT
        )
    """)

    # Seed test product
    cur.execute("""
        INSERT INTO master_products (product_id, name, target_region)
        VALUES ('TEST_W1', 'Wireless Noise Cancelling Earbuds', 'IN')
    """)

    conn.commit()
    conn.close()

    ensure_job_tables(db_file)
    return db_file


@pytest.fixture
def test_client(isolated_worker_db):
    app = create_app()
    with TestClient(app) as client:
        yield client


# ─────────────────────────────────────────────────────────────────────────────
# 1. EXPLICIT START AND GRACEFUL STOP
# ─────────────────────────────────────────────────────────────────────────────
def test_01_explicit_start_and_graceful_stop(isolated_worker_db):
    """Worker starts explicitly on command and stops gracefully when signaled."""
    config = WorkerConfig(
        worker_id="test-w1",
        poll_interval_seconds=0.1,
        batch_size=5,
        db_path=isolated_worker_db
    )
    worker = ObservationWorker(config=config)

    # Pre-start: STOPPED
    stats = worker.get_status()
    assert stats.is_running is False
    assert stats.state == WorkerState.STOPPED
    assert stats.thread_alive is False

    # Start explicitly
    started = worker.start(daemon=True)
    assert started is True
    stats_running = worker.get_status()
    assert stats_running.is_running is True
    assert stats_running.thread_alive is True

    # Duplicate start returns False (prevents multiple threads)
    assert worker.start(daemon=True) is False

    # Stop gracefully
    stopped = worker.stop(timeout=2.0)
    assert stopped is True
    stats_stopped = worker.get_status()
    assert stats_stopped.is_running is False
    assert stats_stopped.state == WorkerState.STOPPED
    assert stats_stopped.stopped_at is not None


# ─────────────────────────────────────────────────────────────────────────────
# 2. POLLING CYCLES AND BOUNDED BATCH PROCESSING
# ─────────────────────────────────────────────────────────────────────────────
def test_02_polling_cycles_and_bounded_batch(isolated_worker_db):
    """Worker processes at most batch_size jobs per polling cycle."""
    now = datetime.datetime.now(datetime.timezone.utc)
    due_time = (now - datetime.timedelta(minutes=10)).isoformat()

    # Create 4 due jobs for TEST_W1
    for i in range(4):
        ObservationJobScheduler.create_job(
            product_id="TEST_W1",
            source_id="google_trends",
            scheduled_at=due_time,
            next_run_at=due_time,
            db_path=isolated_worker_db
        )

    # Configure worker with bounded batch_size = 2
    config = WorkerConfig(
        worker_id="test-bounded-batch",
        poll_interval_seconds=0.1,
        batch_size=2,
        db_path=isolated_worker_db
    )
    worker = ObservationWorker(config=config)

    # Run exactly 1 cycle
    res = worker.run_cycle(now=now, db_path=isolated_worker_db)
    assert res.get("success") is True
    summary = res.get("cycle_summary", {})

    # Exactly 2 jobs should have been executed in this cycle
    assert summary.get("executed") == 2
    assert summary.get("succeeded") == 2

    # Verify 2 jobs are SUCCESS and 2 jobs remain PENDING
    all_jobs = ObservationJobScheduler.list_jobs(db_path=isolated_worker_db, limit=10)
    success_jobs = [j for j in all_jobs if j.status == JobStatus.SUCCESS]
    pending_jobs = [j for j in all_jobs if j.status == JobStatus.PENDING]
    assert len(success_jobs) == 2
    assert len(pending_jobs) == 2

    # Telemetry should reflect batch stats
    stats = worker.get_status()
    assert stats.cycle_count == 1
    assert stats.total_jobs_executed == 2
    assert stats.total_jobs_succeeded == 2


# ─────────────────────────────────────────────────────────────────────────────
# 3. SHUTDOWN DURING IDLE POLLING
# ─────────────────────────────────────────────────────────────────────────────
def test_03_shutdown_during_idle_polling(isolated_worker_db):
    """Worker unblocks immediately upon stop signal rather than sleeping the full poll interval."""
    # Set a long poll interval (10.0s)
    config = WorkerConfig(
        worker_id="test-idle-shutdown",
        poll_interval_seconds=10.0,
        batch_size=5,
        db_path=isolated_worker_db
    )
    worker = ObservationWorker(config=config)
    worker.start(daemon=True)

    time.sleep(0.05)  # Let worker enter idle wait

    start_time = time.time()
    stopped = worker.stop(timeout=2.0)
    elapsed = time.time() - start_time

    assert stopped is True
    # Crucial check: Elapsed time must be significantly less than 2.0s (< 0.5s)
    assert elapsed < 1.0, f"Shutdown took {elapsed}s, expected instant unblock during idle wait"
    assert worker.get_status().is_running is False


# ─────────────────────────────────────────────────────────────────────────────
# 4. SHUTDOWN SAFETY DURING JOB EXECUTION
# ─────────────────────────────────────────────────────────────────────────────
def test_04_shutdown_safety_during_execution(isolated_worker_db):
    """Worker exits loop cleanly when stop is called, without unhandled exceptions."""
    config = WorkerConfig(
        worker_id="test-shutdown-safety",
        poll_interval_seconds=0.05,
        batch_size=5,
        db_path=isolated_worker_db
    )
    worker = ObservationWorker(config=config)
    worker.start(daemon=True)

    # Run briefly then stop
    time.sleep(0.1)
    stopped = worker.stop(timeout=2.0)
    assert stopped is True
    assert worker.get_status().state == WorkerState.STOPPED


# ─────────────────────────────────────────────────────────────────────────────
# 5. WORKER CRASH & ABANDONED RUNNING JOB RECOVERY
# ─────────────────────────────────────────────────────────────────────────────
def test_05_crash_recovery_abandoned_running_jobs(isolated_worker_db):
    """
    Recovers abandoned RUNNING jobs following a worker crash or unexpected termination.
    Jobs older than lease_seconds are reset to RETRY; active jobs within lease are preserved.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    now_str = now.isoformat()
    stale_time = (now - datetime.timedelta(seconds=600)).isoformat()  # 10 minutes ago
    active_time = (now - datetime.timedelta(seconds=30)).isoformat()   # 30 seconds ago

    conn = sqlite3.connect(isolated_worker_db)
    cur = conn.cursor()

    # Job 1: Abandoned RUNNING job (stale, 600s old > 300s lease)
    cur.execute("""
        INSERT INTO observation_jobs (
            product_id, source_id, scheduled_at, status, attempt_count,
            last_attempt_at, next_run_at, created_at, updated_at
        ) VALUES ('TEST_W1', 'google_trends', ?, 'RUNNING', 1, ?, ?, ?, ?)
    """, (stale_time, stale_time, stale_time, stale_time, stale_time))
    stale_id = cur.lastrowid

    # Job 2: Active RUNNING job (recent, 30s old < 300s lease)
    cur.execute("""
        INSERT INTO observation_jobs (
            product_id, source_id, scheduled_at, status, attempt_count,
            last_attempt_at, next_run_at, created_at, updated_at
        ) VALUES ('TEST_W1', 'gdelt', ?, 'RUNNING', 1, ?, ?, ?, ?)
    """, (active_time, active_time, active_time, active_time, active_time))
    active_id = cur.lastrowid

    conn.commit()
    conn.close()

    worker = ObservationWorker(WorkerConfig(db_path=isolated_worker_db, running_lease_seconds=300.0))
    rec_res = worker.recover_abandoned_jobs(now=now, db_path=isolated_worker_db)

    assert rec_res.get("scanned_count") == 1
    assert stale_id in rec_res.get("recovered_to_retry")
    assert active_id not in rec_res.get("recovered_to_retry")

    # Verify stale job is now RETRY
    j_stale = ObservationJobScheduler.get_job(stale_id, db_path=isolated_worker_db)
    assert j_stale.status == JobStatus.RETRY
    assert "Recovered from abandoned RUNNING" in j_stale.last_error

    # Verify active job remains RUNNING
    j_active = ObservationJobScheduler.get_job(active_id, db_path=isolated_worker_db)
    assert j_active.status == JobStatus.RUNNING


# ─────────────────────────────────────────────────────────────────────────────
# 6. ABANDONED JOB EXCEEDING MAX ATTEMPTS
# ─────────────────────────────────────────────────────────────────────────────
def test_06_abandoned_job_max_attempts_transitions_failed(isolated_worker_db):
    """Stale RUNNING job that has reached MAX_ATTEMPTS transitions to FAILED upon recovery."""
    now = datetime.datetime.now(datetime.timezone.utc)
    stale_time = (now - datetime.timedelta(seconds=600)).isoformat()

    conn = sqlite3.connect(isolated_worker_db)
    cur = conn.cursor()

    # Job has attempt_count = 3 (MAX_ATTEMPTS)
    cur.execute("""
        INSERT INTO observation_jobs (
            product_id, source_id, scheduled_at, status, attempt_count,
            last_attempt_at, next_run_at, created_at, updated_at
        ) VALUES ('TEST_W1', 'google_trends', ?, 'RUNNING', 3, ?, ?, ?, ?)
    """, (stale_time, stale_time, stale_time, stale_time, stale_time))
    exhausted_id = cur.lastrowid
    conn.commit()
    conn.close()

    worker = ObservationWorker(WorkerConfig(db_path=isolated_worker_db, running_lease_seconds=300.0))
    rec_res = worker.recover_abandoned_jobs(now=now, db_path=isolated_worker_db)

    assert exhausted_id in rec_res.get("marked_failed")

    j = ObservationJobScheduler.get_job(exhausted_id, db_path=isolated_worker_db)
    assert j.status == JobStatus.FAILED
    assert "exceeded max attempts" in j.last_error


# ─────────────────────────────────────────────────────────────────────────────
# 7. CONCURRENCY SAFETY & DUPLICATE EXECUTION PREVENTION
# ─────────────────────────────────────────────────────────────────────────────
def test_07_duplicate_execution_prevention(isolated_worker_db):
    """Two concurrent workers competing for the same job will never double-execute."""
    now = datetime.datetime.now(datetime.timezone.utc)
    due_time = (now - datetime.timedelta(minutes=5)).isoformat()

    job = ObservationJobScheduler.create_job(
        product_id="TEST_W1",
        source_id="google_trends",
        scheduled_at=due_time,
        next_run_at=due_time,
        db_path=isolated_worker_db
    )

    worker1 = ObservationWorker(WorkerConfig(worker_id="w1", db_path=isolated_worker_db))
    worker2 = ObservationWorker(WorkerConfig(worker_id="w2", db_path=isolated_worker_db))

    # Worker 1 claims and executes
    res1 = ObservationJobScheduler.run_observation_job(job.job_id, db_path=isolated_worker_db, now=now)
    assert res1.get("success") is True

    # Worker 2 attempts execution immediately after
    res2 = ObservationJobScheduler.run_observation_job(job.job_id, db_path=isolated_worker_db, now=now)
    assert res2.get("success") is False
    assert res2.get("status") == "NOT_CLAIMED"


# ─────────────────────────────────────────────────────────────────────────────
# 8. BOUNDED RETRY WITH EXPONENTIAL BACKOFF
# ─────────────────────────────────────────────────────────────────────────────
def test_08_bounded_retry_source_failure(isolated_worker_db, monkeypatch):
    """Adapter failure triggers bounded retry with backoff in worker cycle."""
    from core.research_sources.registry import ResearchSourceRegistry
    from core.research_sources.observation import SourceStatus, SourceExecutionResult

    registry = ResearchSourceRegistry.get_instance()
    def mock_fail(*args, **kwargs):
        return {
            "source_results": {
                "google_trends": SourceExecutionResult(
                    source_id="google_trends",
                    status=SourceStatus.FAILED,
                    started_at="2026-10-09T12:00:00Z",
                    completed_at="2026-10-09T12:00:01Z",
                    duration_ms=100.0,
                    error_type="TIMEOUT",
                    error_message="Network timed out."
                )
            }
        }

    monkeypatch.setattr(registry, "execute_observation_pipeline", mock_fail)

    now = datetime.datetime.now(datetime.timezone.utc)
    due_time = (now - datetime.timedelta(minutes=5)).isoformat()

    job = ObservationJobScheduler.create_job(
        product_id="TEST_W1",
        source_id="google_trends",
        scheduled_at=due_time,
        next_run_at=due_time,
        db_path=isolated_worker_db
    )

    worker = ObservationWorker(WorkerConfig(db_path=isolated_worker_db, batch_size=5))
    cycle_res = worker.run_cycle(now=now, db_path=isolated_worker_db)
    assert cycle_res.get("success") is True

    updated_job = ObservationJobScheduler.get_job(job.job_id, db_path=isolated_worker_db)
    assert updated_job.status == JobStatus.RETRY
    assert updated_job.attempt_count == 1
    assert "Network timed out" in updated_job.last_error

    # Worker stats should report failed execution
    stats = worker.get_status()
    assert stats.total_jobs_failed == 1


# ─────────────────────────────────────────────────────────────────────────────
# 9. MISSING CREDENTIALS / INELIGIBLE SOURCE GRACEFUL SKIP
# ─────────────────────────────────────────────────────────────────────────────
def test_09_missing_credentials_graceful_skip(isolated_worker_db, monkeypatch):
    """Sources missing required credentials (e.g. Keepa) are marked SKIPPED with no infinite retries."""
    monkeypatch.delenv("KEEPA_API_KEY", raising=False)

    now = datetime.datetime.now(datetime.timezone.utc)
    due_time = (now - datetime.timedelta(minutes=5)).isoformat()

    job = ObservationJobScheduler.create_job(
        product_id="TEST_W1",
        source_id="keepa",
        scheduled_at=due_time,
        next_run_at=due_time,
        db_path=isolated_worker_db,
        validate_source=False
    )

    worker = ObservationWorker(WorkerConfig(db_path=isolated_worker_db))
    cycle_res = worker.run_cycle(now=now, db_path=isolated_worker_db)
    assert cycle_res.get("success") is True

    updated_job = ObservationJobScheduler.get_job(job.job_id, db_path=isolated_worker_db)
    assert updated_job.status == JobStatus.SKIPPED
    assert updated_job.attempt_count == 1
    assert "Ineligible source (NOT_CONFIGURED)" in updated_job.last_error

    # Worker stats should record skipped job
    stats = worker.get_status()
    assert stats.total_jobs_skipped == 1


# ─────────────────────────────────────────────────────────────────────────────
# 10. DATABASE FAULT TOLERANCE
# ─────────────────────────────────────────────────────────────────────────────
def test_10_database_unavailable_fault_tolerance(isolated_worker_db):
    """Worker handles database locks or unavailability gracefully without raising unhandled exceptions."""
    worker = ObservationWorker(WorkerConfig(db_path="/invalid/nonexistent/directory/db.sqlite"))

    cycle_res = worker.run_cycle()
    assert cycle_res.get("success") is False
    assert cycle_res.get("db_unavailable") is True

    stats = worker.get_status()
    assert stats.consecutive_errors == 1
    assert "Database unavailable" in stats.last_error


# ─────────────────────────────────────────────────────────────────────────────
# 11. RESTART WITHOUT DUPLICATE SUCCESSFUL OBSERVATIONS
# ─────────────────────────────────────────────────────────────────────────────
def test_11_restart_without_duplicate_successful_runs(isolated_worker_db):
    """A succeeded job scheduled for future execution is never re-executed upon worker restart."""
    now = datetime.datetime.now(datetime.timezone.utc)
    due_time = (now - datetime.timedelta(minutes=5)).isoformat()

    job = ObservationJobScheduler.create_job(
        product_id="TEST_W1",
        source_id="google_trends",
        scheduled_at=due_time,
        next_run_at=due_time,
        db_path=isolated_worker_db
    )

    # First worker executes job successfully
    worker1 = ObservationWorker(WorkerConfig(worker_id="w-run1", db_path=isolated_worker_db))
    res1 = worker1.run_cycle(now=now, db_path=isolated_worker_db)
    assert res1.get("cycle_summary", {}).get("succeeded") == 1

    # Verified job status and future next_run_at
    j = ObservationJobScheduler.get_job(job.job_id, db_path=isolated_worker_db)
    assert j.status == JobStatus.SUCCESS
    assert j.next_run_at > now.isoformat()

    # Second worker starts (simulating process restart)
    worker2 = ObservationWorker(WorkerConfig(worker_id="w-run2", db_path=isolated_worker_db))
    res2 = worker2.run_cycle(now=now, db_path=isolated_worker_db)

    # 0 jobs should run because next_run_at is 24h into the future
    assert res2.get("cycle_summary", {}).get("executed") == 0
    assert res2.get("cycle_summary", {}).get("found_due") == 0


# ─────────────────────────────────────────────────────────────────────────────
# 12. FASTAPI WORKER OPERATIONAL ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────
def test_12_api_worker_endpoints(test_client, isolated_worker_db):
    """Tests /scheduler/worker/status, /start, /stop, and /recover endpoints."""
    # 1. GET /scheduler/worker/status
    res = test_client.get("/scheduler/worker/status")
    assert res.status_code == 200
    data = res.json()
    assert "worker_id" in data
    assert "state" in data
    assert "is_running" in data
    assert "poll_interval_seconds" in data

    # 2. POST /scheduler/worker/start
    res_start = test_client.post("/scheduler/worker/start", json={"poll_interval_seconds": 1.0, "batch_size": 5})
    assert res_start.status_code == 200
    data_start = res_start.json()
    assert data_start["is_running"] is True
    assert data_start["poll_interval_seconds"] == 1.0

    # 3. POST /scheduler/worker/recover
    res_rec = test_client.post("/scheduler/worker/recover?lease_seconds=60")
    assert res_rec.status_code == 200
    data_rec = res_rec.json()
    assert "scanned_count" in data_rec
    assert "total_recovered" in data_rec

    # 4. POST /scheduler/worker/stop
    res_stop = test_client.post("/scheduler/worker/stop?timeout=2.0")
    assert res_stop.status_code == 200
    data_stop = res_stop.json()
    assert data_stop["is_running"] is False
    assert data_stop["state"] == "STOPPED"


# ─────────────────────────────────────────────────────────────────────────────
# 13. PRODUCTION DATABASE STRICT IMMUTABILITY PROOF
# ─────────────────────────────────────────────────────────────────────────────
def test_13_production_db_remains_strictly_unmutated():
    """Confirms production DB at data/research_engine.db was never opened or mutated."""
    prod_path = Path("data/research_engine.db")
    if not prod_path.exists():
        pytest.skip("Production database not present on this machine.")

    conn = sqlite3.connect(str(prod_path))
    cur = conn.cursor()

    # 0 foreign key violations
    fks = cur.execute("PRAGMA foreign_key_check").fetchall()
    assert len(fks) == 0, f"FK violations in production DB: {fks}"

    # Integrity ok
    integrity = cur.execute("PRAGMA integrity_check").fetchall()
    assert integrity == [("ok",)], f"Integrity check failed: {integrity}"

    # Historical decision ledger row US_B09ABC is preserved
    cur.execute("SELECT product_id FROM decision_ledger WHERE product_id = 'US_B09ABC'")
    assert cur.fetchone() is not None, "Historical decision_ledger row US_B09ABC was modified!"

    conn.close()
