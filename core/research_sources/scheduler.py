"""
core/research_sources/scheduler.py — Observation Job Scheduler & Execution Engine.

Architectural Layer: Phase 6 Step 3 Safe Observation Scheduler
Guarantees:
1. Deterministic Due Selection: Order-independent, time-parameterized job selection.
2. Anti-Fabrication Source Verification: Only verified, live-capable sources are scheduled/executed.
3. Concurrency Safety: Atomic PENDING/RETRY -> RUNNING state transition prevents duplicate execution.
4. Bounded Retry & Graceful Skip: Deterministic backoff; permanent configuration errors marked SKIPPED.
5. Zero Production Mutation During Tests: Strictly routes all DB writes through target db_path.
6. One-Shot Deterministic Runner: Terminates cleanly without background daemons.
"""

import os
import sqlite3
import datetime
import logging
from enum import Enum
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
from pydantic import BaseModel, Field

from core.database import get_connection

logger = logging.getLogger("aprs.research_sources.scheduler")


# ─────────────────────────────────────────────────────────────────────────────
# 1. ENUMS & DATA CONTRACTS
# ─────────────────────────────────────────────────────────────────────────────
class JobStatus(str, Enum):
    """Execution status of an observation job."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    RETRY = "RETRY"


class SourceEligibility(str, Enum):
    """Operational eligibility for autonomous scheduling."""
    VERIFIED = "VERIFIED"               # Verified live-capable (e.g. google_trends, gdelt)
    UNVERIFIED = "UNVERIFIED"           # Registered in system but unverified/experimental
    NOT_CONFIGURED = "NOT_CONFIGURED"   # Missing required API credentials or proxy
    DISABLED = "DISABLED"               # Explicitly disabled by operator


class ObservationJob(BaseModel):
    """
    Canonical scheduler job model representing a scheduled observation task.
    """
    job_id: int
    product_id: str
    source_id: str
    scheduled_at: str
    status: JobStatus = JobStatus.PENDING
    attempt_count: int = 0
    last_attempt_at: Optional[str] = None
    last_success_at: Optional[str] = None
    next_run_at: Optional[str] = None
    last_error: Optional[str] = None
    created_at: str
    updated_at: str


# ─────────────────────────────────────────────────────────────────────────────
# 2. SOURCE ELIGIBILITY VERIFICATION
# ─────────────────────────────────────────────────────────────────────────────
def check_source_eligibility(source_id: str) -> Tuple[SourceEligibility, str]:
    """
    Truthful check of source eligibility for observation scheduling.
    Never claims a source is live merely because an adapter file exists.
    """
    from core.research_sources.registry import ResearchSourceRegistry
    registry = ResearchSourceRegistry.get_instance()
    adapter = registry.get_adapter(source_id)
    if not adapter and source_id == "amazon_scraper":
        from core.research_sources.amazon_adapter import AmazonResearchAdapter
        adapter = AmazonResearchAdapter()

    if not adapter and source_id != "keepa":
        return SourceEligibility.UNVERIFIED, f"Source '{source_id}' is not registered."

    # Verified live-capable public APIs
    if source_id in ("google_trends", "gdelt"):
        return SourceEligibility.VERIFIED, f"Source '{source_id}' is verified live-capable public API."

    # Keepa API Client
    if source_id == "keepa":
        key = os.getenv("KEEPA_API_KEY")
        if not key or key.strip() == "":
            return SourceEligibility.NOT_CONFIGURED, "Keepa requires KEEPA_API_KEY environment variable."
        return SourceEligibility.VERIFIED, "Keepa is configured with active API key."

    # Amazon India Scraper
    if source_id == "amazon_india":
        mock_mode = os.getenv("APRS_RESEARCH_MOCK") == "1"
        proxy = os.getenv("DECODO_PROXY_URL")
        if not proxy and not mock_mode:
            return SourceEligibility.NOT_CONFIGURED, "Amazon India requires DECODO_PROXY_URL in production."
        return SourceEligibility.VERIFIED, "Amazon India adapter has proxy configured or mock active."

    # MCP Adapters
    if source_id == "scavio_mcp":
        endpoint = os.getenv("SCAVIO_MCP_ENDPOINT")
        if not endpoint:
            return SourceEligibility.UNVERIFIED, "Scavio MCP adapter requires SCAVIO_MCP_ENDPOINT."
        return SourceEligibility.VERIFIED, "Scavio MCP endpoint configured."

    if source_id == "trends_mcp":
        endpoint = os.getenv("TRENDS_MCP_ENDPOINT")
        if not endpoint:
            return SourceEligibility.UNVERIFIED, "Trends MCP adapter requires TRENDS_MCP_ENDPOINT."
        return SourceEligibility.VERIFIED, "Trends MCP endpoint configured."

    # Unverified / experimental feeds
    return SourceEligibility.UNVERIFIED, f"Source '{source_id}' is unverified for autonomous live execution."


# ─────────────────────────────────────────────────────────────────────────────
# 3. DATABASE TABLE INITIALIZATION
# ─────────────────────────────────────────────────────────────────────────────
def ensure_job_tables(db_path: Optional[str] = None):
    """
    Initializes observation_jobs table in the specified database.
    Strictly isolated to db_path; does not touch production DB during tests.
    """
    target = db_path or os.getenv("APRS_DB_PATH") or "data/research_engine.db"
    conn = get_connection(target)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS observation_jobs (
            job_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            source_id TEXT NOT NULL,
            scheduled_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            attempt_count INTEGER NOT NULL DEFAULT 0,
            last_attempt_at TEXT,
            last_success_at TEXT,
            next_run_at TEXT,
            last_error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (product_id) REFERENCES master_products(product_id)
        );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_obs_jobs_due ON observation_jobs (status, next_run_at);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_obs_jobs_prod_src ON observation_jobs (product_id, source_id);")
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# 4. OBSERVATION JOB SCHEDULER ENGINE
# ─────────────────────────────────────────────────────────────────────────────
class ObservationJobScheduler:
    """
    Core engine managing observation job creation, due selection,
    retry policies, and one-shot execution passes.
    """
    MAX_ATTEMPTS: int = 3
    DEFAULT_INTERVAL_HOURS: int = 24
    RETRY_BACKOFF_HOURS: List[int] = [1, 2, 4]

    @classmethod
    def _now_iso(cls, dt: Optional[Union[datetime.datetime, str]] = None) -> str:
        if isinstance(dt, str):
            return dt
        if dt is None:
            dt = datetime.datetime.now(datetime.timezone.utc)
        elif dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.isoformat()

    @classmethod
    def _parse_dt(cls, val: Union[datetime.datetime, str]) -> datetime.datetime:
        if isinstance(val, datetime.datetime):
            return val if val.tzinfo is not None else val.replace(tzinfo=datetime.timezone.utc)
        # Parse ISO string
        try:
            return datetime.datetime.fromisoformat(val)
        except Exception:
            return datetime.datetime.now(datetime.timezone.utc)

    @classmethod
    def create_job(
        cls,
        product_id: str,
        source_id: str,
        scheduled_at: Optional[Union[datetime.datetime, str]] = None,
        next_run_at: Optional[Union[datetime.datetime, str]] = None,
        db_path: Optional[str] = None,
        validate_source: bool = True
    ) -> ObservationJob:
        """
        Creates and persists a new observation job for a product and source.
        Validates product existence in master_products.
        Optionally validates source eligibility before scheduling.
        """
        target = db_path or os.getenv("APRS_DB_PATH") or "data/research_engine.db"
        ensure_job_tables(target)

        now_str = cls._now_iso()
        sched_str = cls._now_iso(scheduled_at) if scheduled_at else now_str
        next_run_str = cls._now_iso(next_run_at) if next_run_at else sched_str

        conn = get_connection(target)
        cur = conn.cursor()

        # 1. Product existence check
        cur.execute("SELECT product_id FROM master_products WHERE product_id = ?", (product_id,))
        if not cur.fetchone():
            conn.close()
            raise ValueError(f"Product '{product_id}' does not exist in master_products.")

        # 2. Source eligibility check
        if validate_source:
            elig, reason = check_source_eligibility(source_id)
            if elig != SourceEligibility.VERIFIED:
                conn.close()
                raise ValueError(f"Source '{source_id}' is ineligible for scheduling ({elig.value}): {reason}")

        # 3. Insert job
        cur.execute("""
            INSERT INTO observation_jobs (
                product_id, source_id, scheduled_at, status, attempt_count,
                next_run_at, created_at, updated_at
            ) VALUES (?, ?, ?, 'PENDING', 0, ?, ?, ?)
        """, (product_id, source_id, sched_str, next_run_str, now_str, now_str))
        
        job_id = cur.lastrowid
        conn.commit()

        cur.execute("SELECT * FROM observation_jobs WHERE job_id = ?", (job_id,))
        row = dict(cur.fetchone())
        conn.close()

        return ObservationJob(**row)

    @classmethod
    def get_job(cls, job_id: int, db_path: Optional[str] = None) -> Optional[ObservationJob]:
        """Retrieves a single job by its ID."""
        target = db_path or os.getenv("APRS_DB_PATH") or "data/research_engine.db"
        ensure_job_tables(target)
        conn = get_connection(target)
        cur = conn.cursor()
        cur.execute("SELECT * FROM observation_jobs WHERE job_id = ?", (job_id,))
        row = cur.fetchone()
        conn.close()
        return ObservationJob(**dict(row)) if row else None

    @classmethod
    def list_jobs(
        cls,
        status: Optional[str] = None,
        product_id: Optional[str] = None,
        source_id: Optional[str] = None,
        limit: int = 50,
        db_path: Optional[str] = None
    ) -> List[ObservationJob]:
        """Queries observation jobs with optional filtering."""
        target = db_path or os.getenv("APRS_DB_PATH") or "data/research_engine.db"
        ensure_job_tables(target)
        conn = get_connection(target)
        cur = conn.cursor()

        query = "SELECT * FROM observation_jobs WHERE 1=1"
        params: List[Any] = []

        if status:
            query += " AND status = ?"
            params.append(status.upper())
        if product_id:
            query += " AND product_id = ?"
            params.append(product_id)
        if source_id:
            query += " AND source_id = ?"
            params.append(source_id)

        query += " ORDER BY job_id DESC LIMIT ?"
        params.append(limit)

        cur.execute(query, params)
        rows = cur.fetchall()
        conn.close()
        return [ObservationJob(**dict(r)) for r in rows]

    @classmethod
    def get_due_jobs(
        cls,
        now: Optional[Union[datetime.datetime, str]] = None,
        limit: Optional[int] = None,
        db_path: Optional[str] = None
    ) -> List[ObservationJob]:
        """
        Deterministically selects DUE jobs ready for execution.
        Requirements:
        - status in ('PENDING', 'RETRY', 'SUCCESS')
        - next_run_at <= now
        - Ordered deterministically by next_run_at ASC, created_at ASC, job_id ASC.
        """
        target = db_path or os.getenv("APRS_DB_PATH") or "data/research_engine.db"
        ensure_job_tables(target)

        now_str = cls._now_iso(now)
        conn = get_connection(target)
        cur = conn.cursor()

        query = """
            SELECT * FROM observation_jobs
            WHERE status IN ('PENDING', 'RETRY', 'SUCCESS')
              AND next_run_at IS NOT NULL
              AND next_run_at <= ?
            ORDER BY next_run_at ASC, created_at ASC, job_id ASC
        """
        params: List[Any] = [now_str]
        if limit and limit > 0:
            query += " LIMIT ?"
            params.append(limit)

        cur.execute(query, params)
        rows = cur.fetchall()
        conn.close()

        return [ObservationJob(**dict(r)) for r in rows]

    @classmethod
    def recover_abandoned_jobs(
        cls,
        lease_seconds: float = 300.0,
        now: Optional[Union[datetime.datetime, str]] = None,
        immediate_retry: bool = True,
        db_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Scans for abandoned RUNNING jobs whose execution lease has expired
        (e.g. following a worker crash or unexpected process termination).

        If attempt_count < MAX_ATTEMPTS:
            Resets to RETRY status.
            If immediate_retry is True, next_run_at = now (so it becomes due immediately).
            Otherwise, schedules with exponential backoff.
        If attempt_count >= MAX_ATTEMPTS:
            Transitions to FAILED status.
        """
        target = db_path or os.getenv("APRS_DB_PATH") or "data/research_engine.db"
        ensure_job_tables(target)

        now_dt = cls._parse_dt(now) if now else datetime.datetime.now(datetime.timezone.utc)
        cutoff_dt = now_dt - datetime.timedelta(seconds=lease_seconds)
        cutoff_str = cls._now_iso(cutoff_dt)
        now_str = cls._now_iso(now_dt)

        conn = get_connection(target)
        cur = conn.cursor()

        cur.execute("""
            SELECT * FROM observation_jobs
            WHERE status = 'RUNNING'
              AND (last_attempt_at IS NULL OR last_attempt_at <= ?)
        """, (cutoff_str,))
        stale_rows = cur.fetchall()

        recovered_retry: List[int] = []
        marked_failed: List[int] = []

        for row in stale_rows:
            job_id = row["job_id"]
            attempts = row["attempt_count"]

            if attempts < cls.MAX_ATTEMPTS:
                if immediate_retry:
                    next_run_str = now_str
                else:
                    backoff = cls.RETRY_BACKOFF_HOURS[min(max(0, attempts - 1), len(cls.RETRY_BACKOFF_HOURS) - 1)]
                    next_run_str = cls._now_iso(now_dt + datetime.timedelta(hours=backoff))

                err_msg = f"Recovered from abandoned RUNNING lease timeout ({lease_seconds}s)"
                cur.execute("""
                    UPDATE observation_jobs
                    SET status = 'RETRY',
                        last_error = ?,
                        next_run_at = ?,
                        updated_at = ?
                    WHERE job_id = ?
                """, (err_msg, next_run_str, now_str, job_id))
                recovered_retry.append(job_id)
            else:
                err_msg = f"Abandoned in RUNNING state and exceeded max attempts ({attempts}/{cls.MAX_ATTEMPTS})"
                cur.execute("""
                    UPDATE observation_jobs
                    SET status = 'FAILED',
                        last_error = ?,
                        next_run_at = NULL,
                        updated_at = ?
                    WHERE job_id = ?
                """, (err_msg, now_str, job_id))
                marked_failed.append(job_id)

        conn.commit()
        conn.close()

        logger.info(
            f"[RECOVERY] Scanned {len(stale_rows)} abandoned RUNNING jobs. "
            f"Reset to RETRY: {len(recovered_retry)}, Marked FAILED: {len(marked_failed)}"
        )

        return {
            "lease_seconds": lease_seconds,
            "cutoff_timestamp": cutoff_str,
            "scanned_count": len(stale_rows),
            "recovered_to_retry": recovered_retry,
            "marked_failed": marked_failed,
            "total_recovered": len(stale_rows)
        }

    @classmethod
    def run_observation_job(
        cls,
        job_id: int,
        db_path: Optional[str] = None,
        now: Optional[Union[datetime.datetime, str]] = None
    ) -> Dict[str, Any]:
        """
        Safely executes a single observation job through the Phase 6 pipeline.
        Enforces atomic concurrency claim (PENDING/RETRY/SUCCESS -> RUNNING).
        Captures pipeline results, handles retries, and computes next_run_at.
        """
        target = db_path or os.getenv("APRS_DB_PATH") or "data/research_engine.db"
        ensure_job_tables(target)

        now_dt = cls._parse_dt(now) if now else datetime.datetime.now(datetime.timezone.utc)
        now_str = cls._now_iso(now_dt)

        conn = get_connection(target)
        cur = conn.cursor()

        # 1. Atomic claim: transition from runnable state to RUNNING
        cur.execute("""
            UPDATE observation_jobs
            SET status = 'RUNNING',
                last_attempt_at = ?,
                attempt_count = attempt_count + 1,
                updated_at = ?
            WHERE job_id = ?
              AND (
                  status IN ('PENDING', 'RETRY')
                  OR (status = 'SUCCESS' AND (next_run_at IS NULL OR next_run_at <= ?))
              )
        """, (now_str, now_str, job_id, now_str))

        if cur.rowcount == 0:
            conn.close()
            return {
                "success": False,
                "job_id": job_id,
                "status": "NOT_CLAIMED",
                "message": f"Job {job_id} is already RUNNING or not in a runnable state."
            }

        conn.commit()

        # Load updated job
        cur.execute("SELECT * FROM observation_jobs WHERE job_id = ?", (job_id,))
        job_row = dict(cur.fetchone())
        product_id = job_row["product_id"]
        source_id = job_row["source_id"]
        attempt_count = job_row["attempt_count"]

        # 2. Product existence check
        cur.execute("SELECT * FROM master_products WHERE product_id = ?", (product_id,))
        prod = cur.fetchone()
        if not prod:
            err_msg = f"Product '{product_id}' not found in master_products."
            cur.execute("""
                UPDATE observation_jobs
                SET status = 'FAILED',
                    last_error = ?,
                    next_run_at = NULL,
                    updated_at = ?
                WHERE job_id = ?
            """, (err_msg, now_str, job_id))
            conn.commit()
            conn.close()
            return {
                "success": False,
                "job_id": job_id,
                "status": "FAILED",
                "error": err_msg
            }

        product_name = prod["name"]
        prod_dict = dict(prod)
        region = prod_dict.get("region") or prod_dict.get("target_region") or "IN"
        marketplace = "amazon.in" if "in" in str(region).lower() else "amazon.com"

        # 3. Source eligibility validation
        elig, reason = check_source_eligibility(source_id)
        if elig != SourceEligibility.VERIFIED:
            skip_msg = f"Ineligible source ({elig.value}): {reason}"
            cur.execute("""
                UPDATE observation_jobs
                SET status = 'SKIPPED',
                    last_error = ?,
                    next_run_at = NULL,
                    updated_at = ?
                WHERE job_id = ?
            """, (skip_msg, now_str, job_id))
            conn.commit()
            conn.close()
            return {
                "success": False,
                "job_id": job_id,
                "status": "SKIPPED",
                "reason": skip_msg
            }

        conn.close()

        # 4. Invoke existing Phase 6 Observation Pipeline
        from core.research_sources.registry import ResearchSourceRegistry
        registry = ResearchSourceRegistry.get_instance()

        try:
            pipeline_result = registry.execute_observation_pipeline(
                query=product_name,
                product_id=product_id,
                sources=[source_id],
                marketplace=marketplace,
                db_path=target,
                run_diff=True
            )

            # Check source result for errors
            src_results = pipeline_result.get("source_results", {})
            src_res = src_results.get(source_id, {})
            if isinstance(src_res, dict):
                src_status = src_res.get("status")
                if hasattr(src_status, "value"):
                    src_status = src_status.value
                error_type = src_res.get("error_type")
                error_msg = src_res.get("error_message") or f"Source '{source_id}' returned {src_status}"
                records_received = src_res.get("records_received", 0)
            else:
                src_status = getattr(src_res, "status", None)
                if hasattr(src_status, "value"):
                    src_status = src_status.value
                error_type = getattr(src_res, "error_type", None)
                error_msg = getattr(src_res, "error_message", None) or f"Source '{source_id}' returned {src_status}"
                records_received = getattr(src_res, "records_received", 0)

            is_failed = str(src_status).upper() in ("FAILED", "UNAVAILABLE") or (error_type is not None and records_received == 0)
            if is_failed:
                return cls._handle_job_failure(
                    job_id=job_id,
                    attempt_count=attempt_count,
                    error_message=error_msg,
                    now_dt=now_dt,
                    target_db=target
                )

            # Success path: schedule next recurring run
            next_run_dt = now_dt + datetime.timedelta(hours=cls.DEFAULT_INTERVAL_HOURS)
            next_run_str = cls._now_iso(next_run_dt)

            conn = get_connection(target)
            cur = conn.cursor()
            cur.execute("""
                UPDATE observation_jobs
                SET status = 'SUCCESS',
                    last_success_at = ?,
                    next_run_at = ?,
                    attempt_count = 0,
                    last_error = NULL,
                    updated_at = ?
                WHERE job_id = ?
            """, (now_str, next_run_str, now_str, job_id))
            conn.commit()
            conn.close()

            # Refresh intelligence if material change detected
            refreshed = False
            if pipeline_result.get("requires_intelligence_refresh"):
                try:
                    from api.services.product_service import ProductService
                    ref_res = ProductService.refresh_product_intelligence(product_id, db_path=target)
                    refreshed = getattr(ref_res, "success", False)
                except Exception as ex:
                    logger.warning(f"Intelligence refresh error for {product_id}: {ex}")

            return {
                "success": True,
                "job_id": job_id,
                "status": "SUCCESS",
                "product_id": product_id,
                "source_id": source_id,
                "next_run_at": next_run_str,
                "pipeline_summary": pipeline_result.get("ingestion_summary"),
                "material_change": pipeline_result.get("requires_intelligence_refresh", False),
                "intelligence_refreshed": refreshed
            }

        except Exception as e:
            return cls._handle_job_failure(
                job_id=job_id,
                attempt_count=attempt_count,
                error_message=str(e),
                now_dt=now_dt,
                target_db=target
            )

    @classmethod
    def _handle_job_failure(
        cls,
        job_id: int,
        attempt_count: int,
        error_message: str,
        now_dt: datetime.datetime,
        target_db: str
    ) -> Dict[str, Any]:
        """Handles job failure with deterministic retry backoff or final FAILED state."""
        now_str = cls._now_iso(now_dt)
        conn = get_connection(target_db)
        cur = conn.cursor()

        if attempt_count < cls.MAX_ATTEMPTS:
            backoff_hours = cls.RETRY_BACKOFF_HOURS[min(attempt_count - 1, len(cls.RETRY_BACKOFF_HOURS) - 1)]
            retry_dt = now_dt + datetime.timedelta(hours=backoff_hours)
            retry_str = cls._now_iso(retry_dt)

            cur.execute("""
                UPDATE observation_jobs
                SET status = 'RETRY',
                    last_error = ?,
                    next_run_at = ?,
                    updated_at = ?
                WHERE job_id = ?
            """, (error_message, retry_str, now_str, job_id))
            conn.commit()
            conn.close()

            return {
                "success": False,
                "job_id": job_id,
                "status": "RETRY",
                "attempt_count": attempt_count,
                "max_attempts": cls.MAX_ATTEMPTS,
                "next_run_at": retry_str,
                "error": error_message
            }
        else:
            cur.execute("""
                UPDATE observation_jobs
                SET status = 'FAILED',
                    last_error = ?,
                    next_run_at = NULL,
                    updated_at = ?
                WHERE job_id = ?
            """, (error_message, now_str, job_id))
            conn.commit()
            conn.close()

            return {
                "success": False,
                "job_id": job_id,
                "status": "FAILED",
                "attempt_count": attempt_count,
                "max_attempts": cls.MAX_ATTEMPTS,
                "error": error_message
            }

    @classmethod
    def run_due_jobs(
        cls,
        now: Optional[Union[datetime.datetime, str]] = None,
        limit: int = 10,
        dry_run: bool = False,
        db_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        One-shot scheduler runner:
        1. Selects due jobs up to limit.
        2. If dry_run=True: validates eligibility without writes and reports what would run.
        3. If dry_run=False: executes each due job deterministically and captures summary.
        Terminates cleanly; zero infinite loops or daemon threads.
        """
        target = db_path or os.getenv("APRS_DB_PATH") or "data/research_engine.db"
        ensure_job_tables(target)

        limit = max(1, min(limit, 100))  # Bounded execution: 1 to 100
        now_dt = cls._parse_dt(now) if now else datetime.datetime.now(datetime.timezone.utc)
        due_jobs = cls.get_due_jobs(now=now_dt, limit=limit, db_path=target)

        if dry_run:
            eligible: List[Dict[str, Any]] = []
            skipped: List[Dict[str, Any]] = []

            conn = get_connection(target)
            cur = conn.cursor()

            for j in due_jobs:
                cur.execute("SELECT product_id FROM master_products WHERE product_id = ?", (j.product_id,))
                prod_exists = bool(cur.fetchone())
                elig, reason = check_source_eligibility(j.source_id)

                job_info = {
                    "job_id": j.job_id,
                    "product_id": j.product_id,
                    "source_id": j.source_id,
                    "scheduled_at": j.scheduled_at,
                    "next_run_at": j.next_run_at,
                    "product_exists": prod_exists,
                    "source_eligibility": elig.value,
                    "reason": reason
                }

                if prod_exists and elig == SourceEligibility.VERIFIED:
                    eligible.append(job_info)
                else:
                    skipped.append(job_info)

            conn.close()

            return {
                "dry_run": True,
                "requested_limit": limit,
                "due_jobs_count": len(due_jobs),
                "eligible_count": len(eligible),
                "skipped_count": len(skipped),
                "jobs": {
                    "eligible": eligible,
                    "skipped": skipped
                }
            }

        # Actual execution pass
        executed_count = 0
        succeeded_count = 0
        failed_count = 0
        skipped_count = 0
        results: List[Dict[str, Any]] = []

        for j in due_jobs:
            res = cls.run_observation_job(j.job_id, db_path=target, now=now_dt)
            results.append(res)
            st = res.get("status")

            if st != "NOT_CLAIMED":
                executed_count += 1

            if st == "SUCCESS":
                succeeded_count += 1
            elif st in ("FAILED", "RETRY"):
                failed_count += 1
            elif st == "SKIPPED":
                skipped_count += 1

        return {
            "dry_run": False,
            "requested_limit": limit,
            "found_due": len(due_jobs),
            "executed": executed_count,
            "succeeded": succeeded_count,
            "failed": failed_count,
            "skipped": skipped_count,
            "jobs": results
        }
