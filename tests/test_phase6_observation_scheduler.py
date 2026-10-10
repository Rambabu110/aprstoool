"""
tests/test_phase6_observation_scheduler.py — Test Suite for Phase 6 Observation Scheduler.

Validates the complete scheduler layer:
1. Job Creation (valid product + source, invalid product, ineligible source)
2. Due Selection (future jobs excluded, due included, deterministic ordering)
3. Job Execution (successful observation, skipped unconfigured, missing product)
4. Retry Policy (transient failure backoff, max retry reached -> FAILED)
5. Next-run Calculation (+24h cadence, timestamps)
6. Duplicate / Concurrency Safety (atomic transition prevents duplicate claim)
7. Dry Run Mode (identifies jobs, performs zero writes)
8. FastAPI Endpoints (GET /jobs, GET /jobs/due, POST /jobs, POST /run-once)
9. Production Database Immutability (zero mutation to data/research_engine.db)
"""

import os
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
    check_source_eligibility,
    ensure_job_tables
)
from api.main import create_app


# ─────────────────────────────────────────────────────────────────────────────
# FIXTURES: Isolated SQLite Database
# ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def isolated_scheduler_db(tmp_path, monkeypatch):
    """
    Creates an isolated temporary SQLite database populated with test schema and product.
    Guarantees production DB at data/research_engine.db is NEVER touched.
    """
    db_file = str(tmp_path / "test_scheduler.db")
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
            timestamp TEXT,
            event_type TEXT,
            description TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE source_health (
            source_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name TEXT UNIQUE NOT NULL,
            data_type TEXT,
            last_successful_fetch TEXT,
            failure_count INTEGER DEFAULT 0,
            freshness_status TEXT DEFAULT 'UNINITIALIZED',
            response_time_ms REAL DEFAULT 0.0,
            details_json TEXT,
            updated_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE product_intelligence (
            product_id TEXT PRIMARY KEY,
            overall_score REAL,
            kill_status TEXT,
            computed_at TEXT
        )
    """)

    # Seed test products
    cur.execute("INSERT INTO master_products (product_id, name, target_region) VALUES ('TEST_PROD_1', 'Ergonomic Chair', 'IN')")
    cur.execute("INSERT INTO master_products (product_id, name, target_region) VALUES ('TEST_PROD_2', 'Standing Desk', 'IN')")

    conn.commit()
    conn.close()

    # Initialize observation_jobs in this isolated DB
    ensure_job_tables(db_file)

    return db_file


# ─────────────────────────────────────────────────────────────────────────────
# 1. JOB CREATION TESTS
# ─────────────────────────────────────────────────────────────────────────────
def test_create_job_valid(isolated_scheduler_db):
    """Verifies that a valid job is scheduled with PENDING status and correct initial fields."""
    job = ObservationJobScheduler.create_job(
        product_id="TEST_PROD_1",
        source_id="google_trends",
        db_path=isolated_scheduler_db
    )
    assert job.job_id is not None
    assert job.product_id == "TEST_PROD_1"
    assert job.source_id == "google_trends"
    assert job.status == JobStatus.PENDING
    assert job.attempt_count == 0
    assert job.last_attempt_at is None
    assert job.last_success_at is None
    assert job.last_error is None
    assert job.next_run_at is not None


def test_create_job_invalid_product(isolated_scheduler_db):
    """Verifies that creating a job for a non-existent product raises ValueError."""
    with pytest.raises(ValueError, match="does not exist in master_products"):
        ObservationJobScheduler.create_job(
            product_id="NON_EXISTENT_PROD",
            source_id="google_trends",
            db_path=isolated_scheduler_db
        )


def test_create_job_ineligible_source(isolated_scheduler_db):
    """Verifies that creating a job with an unverified/ineligible source raises ValueError."""
    with pytest.raises(ValueError, match="is ineligible for scheduling"):
        ObservationJobScheduler.create_job(
            product_id="TEST_PROD_1",
            source_id="unregistered_fake_source",
            db_path=isolated_scheduler_db
        )


def test_create_job_keepa_missing_key(isolated_scheduler_db, monkeypatch):
    """Verifies that Keepa cannot be scheduled when KEEPA_API_KEY is not configured."""
    monkeypatch.delenv("KEEPA_API_KEY", raising=False)
    with pytest.raises(ValueError, match="NOT_CONFIGURED"):
        ObservationJobScheduler.create_job(
            product_id="TEST_PROD_1",
            source_id="keepa",
            db_path=isolated_scheduler_db
        )


# ─────────────────────────────────────────────────────────────────────────────
# 2. DUE SELECTION & DETERMINISTIC ORDERING
# ─────────────────────────────────────────────────────────────────────────────
def test_due_selection_filtering(isolated_scheduler_db):
    """Verifies that future jobs are excluded, while due jobs are returned."""
    now = datetime.datetime(2026, 10, 8, 12, 0, 0, tzinfo=datetime.timezone.utc)
    past = now - datetime.timedelta(minutes=15)
    future = now + datetime.timedelta(hours=2)

    # 1. Due job
    ObservationJobScheduler.create_job(
        product_id="TEST_PROD_1",
        source_id="google_trends",
        scheduled_at=past,
        next_run_at=past,
        db_path=isolated_scheduler_db
    )

    # 2. Future job
    ObservationJobScheduler.create_job(
        product_id="TEST_PROD_2",
        source_id="google_trends",
        scheduled_at=future,
        next_run_at=future,
        db_path=isolated_scheduler_db
    )

    due_jobs = ObservationJobScheduler.get_due_jobs(now=now, db_path=isolated_scheduler_db)
    assert len(due_jobs) == 1
    assert due_jobs[0].product_id == "TEST_PROD_1"


def test_due_selection_deterministic_ordering(isolated_scheduler_db):
    """Verifies deterministic ordering: next_run_at ASC, created_at ASC, job_id ASC."""
    t1 = datetime.datetime(2026, 10, 8, 10, 0, 0, tzinfo=datetime.timezone.utc)
    t2 = datetime.datetime(2026, 10, 8, 11, 0, 0, tzinfo=datetime.timezone.utc)
    now = datetime.datetime(2026, 10, 8, 12, 0, 0, tzinfo=datetime.timezone.utc)

    # Job B with later next_run_at
    j_b = ObservationJobScheduler.create_job(
        product_id="TEST_PROD_2",
        source_id="google_trends",
        next_run_at=t2,
        db_path=isolated_scheduler_db
    )

    # Job A with earlier next_run_at
    j_a = ObservationJobScheduler.create_job(
        product_id="TEST_PROD_1",
        source_id="google_trends",
        next_run_at=t1,
        db_path=isolated_scheduler_db
    )

    due_jobs = ObservationJobScheduler.get_due_jobs(now=now, db_path=isolated_scheduler_db)
    assert len(due_jobs) == 2
    assert due_jobs[0].job_id == j_a.job_id
    assert due_jobs[1].job_id == j_b.job_id


# ─────────────────────────────────────────────────────────────────────────────
# 3. SINGLE JOB EXECUTION TESTS
# ─────────────────────────────────────────────────────────────────────────────
def test_run_observation_job_success(isolated_scheduler_db):
    """Verifies full execution pass: RUNNING -> SUCCESS, next_run_at scheduled +24h."""
    now = datetime.datetime(2026, 10, 8, 12, 0, 0, tzinfo=datetime.timezone.utc)
    job = ObservationJobScheduler.create_job(
        product_id="TEST_PROD_1",
        source_id="google_trends",
        next_run_at=now,
        db_path=isolated_scheduler_db
    )

    result = ObservationJobScheduler.run_observation_job(
        job_id=job.job_id,
        db_path=isolated_scheduler_db,
        now=now
    )

    assert result["success"] is True
    assert result["status"] == "SUCCESS"

    # Reload job
    updated = ObservationJobScheduler.get_job(job.job_id, db_path=isolated_scheduler_db)
    assert updated.status == JobStatus.SUCCESS
    assert updated.last_success_at is not None
    assert updated.attempt_count == 0
    assert updated.last_error is None

    # Next run scheduled ~24h in future
    expected_next = now + datetime.timedelta(hours=24)
    assert updated.next_run_at == expected_next.isoformat()

    # Check evidence row created in isolated DB
    conn = sqlite3.connect(isolated_scheduler_db)
    ev_count = conn.execute("SELECT COUNT(*) FROM intelligence_evidence WHERE product_id = 'TEST_PROD_1'").fetchone()[0]
    conn.close()
    assert ev_count > 0


def test_run_observation_job_ineligible_source_skipped(isolated_scheduler_db):
    """Verifies that an unverified source is marked SKIPPED without infinite retries."""
    # Force insert an unverified job directly
    conn = sqlite3.connect(isolated_scheduler_db)
    cur = conn.cursor()
    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
    cur.execute("""
        INSERT INTO observation_jobs (product_id, source_id, scheduled_at, status, next_run_at, created_at, updated_at)
        VALUES ('TEST_PROD_1', 'unverified_feed', ?, 'PENDING', ?, ?, ?)
    """, (now_str, now_str, now_str, now_str))
    job_id = cur.lastrowid
    conn.commit()
    conn.close()

    result = ObservationJobScheduler.run_observation_job(job_id=job_id, db_path=isolated_scheduler_db)
    assert result["success"] is False
    assert result["status"] == "SKIPPED"

    updated = ObservationJobScheduler.get_job(job_id, db_path=isolated_scheduler_db)
    assert updated.status == JobStatus.SKIPPED
    assert updated.next_run_at is None
    assert "Ineligible source" in updated.last_error


def test_run_observation_job_missing_product_failed(isolated_scheduler_db):
    """Verifies that if a product disappears from master_products, job transitions to FAILED."""
    job = ObservationJobScheduler.create_job(
        product_id="TEST_PROD_1",
        source_id="google_trends",
        db_path=isolated_scheduler_db
    )

    # Delete product from master_products
    conn = sqlite3.connect(isolated_scheduler_db)
    conn.execute("DELETE FROM master_products WHERE product_id = 'TEST_PROD_1'")
    conn.commit()
    conn.close()

    result = ObservationJobScheduler.run_observation_job(job_id=job.job_id, db_path=isolated_scheduler_db)
    assert result["success"] is False
    assert result["status"] == "FAILED"

    updated = ObservationJobScheduler.get_job(job.job_id, db_path=isolated_scheduler_db)
    assert updated.status == JobStatus.FAILED
    assert updated.next_run_at is None
    assert "not found in master_products" in updated.last_error


# ─────────────────────────────────────────────────────────────────────────────
# 4. RETRY POLICY TESTS
# ─────────────────────────────────────────────────────────────────────────────
def test_retry_policy_transient_failure_and_backoff(isolated_scheduler_db, monkeypatch):
    """Verifies that transient errors increment attempt_count and apply deterministic backoff."""
    from core.research_sources.registry import ResearchSourceRegistry
    from core.research_sources.observation import SourceStatus, SourceExecutionResult

    job = ObservationJobScheduler.create_job(
        product_id="TEST_PROD_1",
        source_id="google_trends",
        db_path=isolated_scheduler_db
    )

    # Mock registry failure
    registry = ResearchSourceRegistry.get_instance()
    def mock_fail(*args, **kwargs):
        return {
            "source_results": {
                "google_trends": SourceExecutionResult(
                    source_id="google_trends",
                    status=SourceStatus.FAILED,
                    started_at="2026-10-08T12:00:00Z",
                    completed_at="2026-10-08T12:00:01Z",
                    duration_ms=100.0,
                    error_type="TIMEOUT",
                    error_message="Network timed out."
                )
            }
        }

    monkeypatch.setattr(registry, "execute_observation_pipeline", mock_fail)

    now = datetime.datetime(2026, 10, 8, 12, 0, 0, tzinfo=datetime.timezone.utc)
    res = ObservationJobScheduler.run_observation_job(job.job_id, db_path=isolated_scheduler_db, now=now)

    assert res["success"] is False
    assert res["status"] == "RETRY"
    assert res["attempt_count"] == 1

    updated = ObservationJobScheduler.get_job(job.job_id, db_path=isolated_scheduler_db)
    assert updated.status == JobStatus.RETRY
    assert updated.attempt_count == 1
    # 1st retry backoff is 1 hour
    assert updated.next_run_at == (now + datetime.timedelta(hours=1)).isoformat()


def test_retry_policy_max_attempts_reached(isolated_scheduler_db, monkeypatch):
    """Verifies that reaching MAX_ATTEMPTS transitions job to FAILED with next_run_at = NULL."""
    from core.research_sources.registry import ResearchSourceRegistry
    from core.research_sources.observation import SourceStatus, SourceExecutionResult

    job = ObservationJobScheduler.create_job(
        product_id="TEST_PROD_1",
        source_id="google_trends",
        db_path=isolated_scheduler_db
    )

    # Set attempt_count to 2
    conn = sqlite3.connect(isolated_scheduler_db)
    conn.execute("UPDATE observation_jobs SET attempt_count = 2 WHERE job_id = ?", (job.job_id,))
    conn.commit()
    conn.close()

    registry = ResearchSourceRegistry.get_instance()
    def mock_fail(*args, **kwargs):
        return {
            "source_results": {
                "google_trends": SourceExecutionResult(
                    source_id="google_trends",
                    status=SourceStatus.FAILED,
                    started_at="2026-10-08T12:00:00Z",
                    completed_at="2026-10-08T12:00:01Z",
                    duration_ms=100.0,
                    error_type="FATAL_500",
                    error_message="Fatal server error."
                )
            }
        }

    monkeypatch.setattr(registry, "execute_observation_pipeline", mock_fail)

    now = datetime.datetime(2026, 10, 8, 12, 0, 0, tzinfo=datetime.timezone.utc)
    res = ObservationJobScheduler.run_observation_job(job.job_id, db_path=isolated_scheduler_db, now=now)

    assert res["success"] is False
    assert res["status"] == "FAILED"
    assert res["attempt_count"] == 3

    updated = ObservationJobScheduler.get_job(job.job_id, db_path=isolated_scheduler_db)
    assert updated.status == JobStatus.FAILED
    assert updated.next_run_at is None


# ─────────────────────────────────────────────────────────────────────────────
# 5. DUPLICATE / CONCURRENCY SAFETY TESTS
# ─────────────────────────────────────────────────────────────────────────────
def test_concurrency_duplicate_claim_prevention(isolated_scheduler_db):
    """Verifies atomic state transition: same job cannot be claimed twice concurrently."""
    job = ObservationJobScheduler.create_job(
        product_id="TEST_PROD_1",
        source_id="google_trends",
        db_path=isolated_scheduler_db
    )

    # Manually transition to RUNNING to simulate ongoing execution
    conn = sqlite3.connect(isolated_scheduler_db)
    conn.execute("UPDATE observation_jobs SET status = 'RUNNING' WHERE job_id = ?", (job.job_id,))
    conn.commit()
    conn.close()

    # Second worker tries to run
    res = ObservationJobScheduler.run_observation_job(job.job_id, db_path=isolated_scheduler_db)
    assert res["success"] is False
    assert res["status"] == "NOT_CLAIMED"


# ─────────────────────────────────────────────────────────────────────────────
# 6. ONE-SHOT RUNNER & DRY-RUN TESTS
# ─────────────────────────────────────────────────────────────────────────────
def test_one_shot_dry_run_zero_writes(isolated_scheduler_db):
    """Verifies dry-run mode evaluates due jobs without writing to observation_jobs or evidence."""
    now = datetime.datetime.now(datetime.timezone.utc)
    ObservationJobScheduler.create_job(
        product_id="TEST_PROD_1",
        source_id="google_trends",
        next_run_at=now,
        db_path=isolated_scheduler_db
    )

    # Snapshot tables
    conn = sqlite3.connect(isolated_scheduler_db)
    jobs_before = conn.execute("SELECT * FROM observation_jobs").fetchall()
    ev_count_before = conn.execute("SELECT COUNT(*) FROM intelligence_evidence").fetchone()[0]
    sh_count_before = conn.execute("SELECT COUNT(*) FROM source_health").fetchone()[0]
    conn.close()

    res = ObservationJobScheduler.run_due_jobs(
        now=now,
        limit=10,
        dry_run=True,
        db_path=isolated_scheduler_db
    )

    assert res["dry_run"] is True
    assert res["due_jobs_count"] == 1
    assert res["eligible_count"] == 1
    assert res["skipped_count"] == 0

    # Verify zero mutations
    conn = sqlite3.connect(isolated_scheduler_db)
    jobs_after = conn.execute("SELECT * FROM observation_jobs").fetchall()
    ev_count_after = conn.execute("SELECT COUNT(*) FROM intelligence_evidence").fetchone()[0]
    sh_count_after = conn.execute("SELECT COUNT(*) FROM source_health").fetchone()[0]
    conn.close()

    assert jobs_before == jobs_after
    assert ev_count_before == ev_count_after
    assert sh_count_before == sh_count_after


def test_one_shot_runner_execution_pass(isolated_scheduler_db):
    """Verifies that run_due_jobs executes due jobs up to limit and returns structured summary."""
    now = datetime.datetime.now(datetime.timezone.utc)
    ObservationJobScheduler.create_job(
        product_id="TEST_PROD_1",
        source_id="google_trends",
        next_run_at=now,
        db_path=isolated_scheduler_db
    )
    ObservationJobScheduler.create_job(
        product_id="TEST_PROD_2",
        source_id="gdelt",
        next_run_at=now,
        db_path=isolated_scheduler_db
    )

    res = ObservationJobScheduler.run_due_jobs(
        now=now,
        limit=5,
        dry_run=False,
        db_path=isolated_scheduler_db
    )

    assert res["dry_run"] is False
    assert res["found_due"] == 2
    assert res["executed"] == 2
    assert res["succeeded"] == 2
    assert res["failed"] == 0
    assert res["skipped"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# 7. FASTAPI API ENDPOINT TESTS
# ─────────────────────────────────────────────────────────────────────────────
def test_api_scheduler_endpoints(isolated_scheduler_db):
    """Tests /scheduler/jobs, /scheduler/jobs/due, and /scheduler/run-once via TestClient."""
    app = create_app()
    client = TestClient(app)

    # 1. Create job via POST /scheduler/jobs
    resp = client.post("/scheduler/jobs", json={
        "product_id": "TEST_PROD_1",
        "source_id": "google_trends"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["product_id"] == "TEST_PROD_1"
    assert data["status"] == "PENDING"
    job_id = data["job_id"]

    # 2. List jobs via GET /scheduler/jobs
    resp = client.get("/scheduler/jobs?limit=10")
    assert resp.status_code == 200
    jobs = resp.json()
    assert len(jobs) >= 1
    assert any(j["job_id"] == job_id for j in jobs)

    # 3. List due jobs via GET /scheduler/jobs/due
    resp = client.get("/scheduler/jobs/due")
    assert resp.status_code == 200
    due = resp.json()
    assert len(due) >= 1

    # 4. Dry run via POST /scheduler/run-once?dry_run=true
    resp = client.post("/scheduler/run-once?limit=5&dry_run=true")
    assert resp.status_code == 200
    sim = resp.json()
    assert sim["dry_run"] is True
    assert sim["due_jobs_count"] >= 1

    # 5. Execute via POST /scheduler/run-once?dry_run=false
    resp = client.post("/scheduler/run-once?limit=5&dry_run=false")
    assert resp.status_code == 200
    run_res = resp.json()
    assert run_res["dry_run"] is False
    assert run_res["executed"] >= 1
    assert run_res["succeeded"] >= 1


# ─────────────────────────────────────────────────────────────────────────────
# 8. PRODUCTION DATABASE IMMUTABILITY PROOF
# ─────────────────────────────────────────────────────────────────────────────
def test_production_db_remains_strictly_unmutated_during_scheduler_tests(isolated_scheduler_db):
    """
    Guarantees that scheduler tests strictly mutate isolated_scheduler_db
    and leave production data/research_engine.db 100% byte-identical.
    """
    prod_path = "data/research_engine.db"
    assert os.path.exists(prod_path)

    size_before = os.path.getsize(prod_path)
    sha_before = hashlib.sha256(open(prod_path, "rb").read()).hexdigest()

    # Perform extensive scheduler operations in isolated DB
    now = datetime.datetime.now(datetime.timezone.utc)
    j1 = ObservationJobScheduler.create_job(
        product_id="TEST_PROD_1",
        source_id="google_trends",
        scheduled_at=now,
        next_run_at=now,
        db_path=isolated_scheduler_db
    )
    j2 = ObservationJobScheduler.create_job(
        product_id="TEST_PROD_2",
        source_id="gdelt",
        scheduled_at=now,
        next_run_at=now,
        db_path=isolated_scheduler_db
    )
    ObservationJobScheduler.run_due_jobs(now=now, limit=10, dry_run=False, db_path=isolated_scheduler_db)

    # Verify isolated DB got mutated
    conn = sqlite3.connect(isolated_scheduler_db)
    ev_count = conn.execute("SELECT COUNT(*) FROM intelligence_evidence").fetchone()[0]
    conn.close()
    assert ev_count > 0

    # Verify production DB is completely untouched
    size_after = os.path.getsize(prod_path)
    sha_after = hashlib.sha256(open(prod_path, "rb").read()).hexdigest()

    assert size_before == size_after
    assert sha_before == sha_after
