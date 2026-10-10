"""
core/research_sources/worker.py — Controlled Persistent Observation Worker.

Architectural Layer: Phase 6 Step 4 Controlled Persistent Observation Worker
Guarantees:
1. Controllable Lifecycle: Explicit start, graceful stop, and restart without uncontrolled auto-start.
2. Graceful Shutdown: Instant exit during idle wait; finishes current job before stopping.
3. Crash Recovery: Recovers abandoned RUNNING jobs using a lease timeout mechanism.
4. Concurrency Safety: Atomic job claiming prevents duplicate execution across cycles.
5. Truthful Observability: Structured logs for job start, success, failure, skip; accurate health telemetry.
6. DB Fault Tolerance: Handles database locks or unavailability gracefully without crashing the loop.
7. Out-of-Process Capable: Can run as an independent background process or controlled service.
"""

import os
import sys
import time
import signal
import logging
import sqlite3
import datetime
import threading
from enum import Enum
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field

from core.database import get_connection
from core.research_sources.scheduler import (
    ObservationJobScheduler,
    ObservationJob,
    JobStatus,
    SourceEligibility,
    check_source_eligibility,
    ensure_job_tables
)

logger = logging.getLogger("aprs.research_sources.worker")


# ─────────────────────────────────────────────────────────────────────────────
# 1. ENUMS & DATA CONTRACTS
# ─────────────────────────────────────────────────────────────────────────────
class WorkerState(str, Enum):
    """Lifecycle state of the observation worker."""
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    IDLE = "IDLE"
    PROCESSING = "PROCESSING"
    STOPPING = "STOPPING"
    ERROR = "ERROR"


class WorkerConfig(BaseModel):
    """Configuration parameters for the observation worker."""
    worker_id: str = "obs-worker-1"
    poll_interval_seconds: float = 30.0
    batch_size: int = 10
    running_lease_seconds: float = 300.0
    db_path: Optional[str] = None
    max_cycles: Optional[int] = None  # None = run indefinitely; int = stop after N cycles


class WorkerStats(BaseModel):
    """Runtime telemetry and health stats of the observation worker."""
    worker_id: str
    state: WorkerState = WorkerState.STOPPED
    is_running: bool = False
    thread_alive: bool = False
    started_at: Optional[str] = None
    stopped_at: Optional[str] = None
    last_heartbeat: Optional[str] = None
    last_cycle_at: Optional[str] = None
    cycle_count: int = 0
    total_jobs_executed: int = 0
    total_jobs_succeeded: int = 0
    total_jobs_failed: int = 0
    total_jobs_skipped: int = 0
    recovered_jobs_count: int = 0
    last_error: Optional[str] = None
    consecutive_errors: int = 0
    poll_interval_seconds: float = 30.0
    batch_size: int = 10
    running_lease_seconds: float = 300.0
    last_cycle_summary: Optional[Dict[str, Any]] = None


# ─────────────────────────────────────────────────────────────────────────────
# 2. CONTROLLED OBSERVATION WORKER IMPLEMENTATION
# ─────────────────────────────────────────────────────────────────────────────
class ObservationWorker:
    """
    Controlled persistent observation worker.
    Repeatedly polls for due observation jobs, executes them safely using the
    existing ObservationJobScheduler pipeline, and handles crash recovery.
    """

    def __init__(self, config: Optional[WorkerConfig] = None):
        self.config = config or WorkerConfig()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # Telemetry state
        self._stats = WorkerStats(
            worker_id=self.config.worker_id,
            state=WorkerState.STOPPED,
            is_running=False,
            thread_alive=False,
            poll_interval_seconds=self.config.poll_interval_seconds,
            batch_size=self.config.batch_size,
            running_lease_seconds=self.config.running_lease_seconds
        )

    @classmethod
    def _now_iso(cls) -> str:
        return datetime.datetime.now(datetime.timezone.utc).isoformat()

    def get_status(self) -> WorkerStats:
        """Returns a snapshot of worker health, state, and execution metrics."""
        with self._lock:
            thread_alive = bool(self._thread and self._thread.is_alive())
            is_running = self._stats.state in (
                WorkerState.STARTING,
                WorkerState.IDLE,
                WorkerState.PROCESSING
            ) and thread_alive

            return WorkerStats(
                worker_id=self.config.worker_id,
                state=self._stats.state if is_running else WorkerState.STOPPED,
                is_running=is_running,
                thread_alive=thread_alive,
                started_at=self._stats.started_at,
                stopped_at=self._stats.stopped_at,
                last_heartbeat=self._stats.last_heartbeat,
                last_cycle_at=self._stats.last_cycle_at,
                cycle_count=self._stats.cycle_count,
                total_jobs_executed=self._stats.total_jobs_executed,
                total_jobs_succeeded=self._stats.total_jobs_succeeded,
                total_jobs_failed=self._stats.total_jobs_failed,
                total_jobs_skipped=self._stats.total_jobs_skipped,
                recovered_jobs_count=self._stats.recovered_jobs_count,
                last_error=self._stats.last_error,
                consecutive_errors=self._stats.consecutive_errors,
                poll_interval_seconds=self.config.poll_interval_seconds,
                batch_size=self.config.batch_size,
                running_lease_seconds=self.config.running_lease_seconds,
                last_cycle_summary=self._stats.last_cycle_summary
            )

    def recover_abandoned_jobs(
        self,
        lease_seconds: Optional[float] = None,
        now: Optional[Union[datetime.datetime, str]] = None,
        db_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Explicitly triggers recovery of stale RUNNING jobs whose execution lease has expired.
        """
        target = db_path or self.config.db_path or os.getenv("APRS_DB_PATH") or "data/research_engine.db"
        lease = lease_seconds if lease_seconds is not None else self.config.running_lease_seconds
        
        recovery_res = ObservationJobScheduler.recover_abandoned_jobs(
            lease_seconds=lease,
            now=now,
            immediate_retry=True,
            db_path=target
        )
        
        with self._lock:
            self._stats.recovered_jobs_count += recovery_res.get("total_recovered", 0)
            
        return recovery_res

    def run_cycle(
        self,
        now: Optional[Union[datetime.datetime, str]] = None,
        db_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes a single controlled polling cycle:
        1. Recovers abandoned RUNNING jobs.
        2. Queries due jobs and executes up to batch_size.
        3. Emits structured logs for job start, success, failure, and skip.
        4. Updates worker telemetry.
        Tolerates DB unavailability without unhandled exceptions.
        """
        target = db_path or self.config.db_path or os.getenv("APRS_DB_PATH") or "data/research_engine.db"
        now_str = self._now_iso()

        with self._lock:
            self._stats.last_heartbeat = now_str
            self._stats.last_cycle_at = now_str

        try:
            # Step 1: Crash recovery for abandoned RUNNING jobs
            recovery_info = ObservationJobScheduler.recover_abandoned_jobs(
                lease_seconds=self.config.running_lease_seconds,
                now=now,
                immediate_retry=True,
                db_path=target
            )
            recovered_count = recovery_info.get("total_recovered", 0)

            # Step 2: One-shot due job execution pass
            batch_result = ObservationJobScheduler.run_due_jobs(
                now=now,
                limit=self.config.batch_size,
                dry_run=False,
                db_path=target
            )

            executed = batch_result.get("executed", 0)
            succeeded = batch_result.get("succeeded", 0)
            failed = batch_result.get("failed", 0)
            skipped = batch_result.get("skipped", 0)
            job_details = batch_result.get("jobs", [])

            # Step 3: Structured logs for observability
            for j in job_details:
                jid = j.get("job_id")
                st = j.get("status")
                pid = j.get("product_id")
                sid = j.get("source_id")

                if st == "SUCCESS":
                    logger.info(
                        f"[OBS-WORKER][JOB-SUCCESS] job_id={jid} product={pid} "
                        f"source={sid} next_run={j.get('next_run_at')}"
                    )
                elif st in ("FAILED", "RETRY"):
                    logger.warning(
                        f"[OBS-WORKER][JOB-FAILURE] job_id={jid} status={st} "
                        f"attempts={j.get('attempt_count')}/{j.get('max_attempts')} "
                        f"error={j.get('error')}"
                    )
                elif st == "SKIPPED":
                    logger.info(
                        f"[OBS-WORKER][JOB-SKIP] job_id={jid} reason={j.get('reason')}"
                    )

            cycle_summary = {
                "timestamp": now_str,
                "found_due": batch_result.get("found_due", 0),
                "executed": executed,
                "succeeded": succeeded,
                "failed": failed,
                "skipped": skipped,
                "recovered_abandoned": recovered_count,
                "jobs": job_details
            }

            with self._lock:
                self._stats.cycle_count += 1
                self._stats.total_jobs_executed += executed
                self._stats.total_jobs_succeeded += succeeded
                self._stats.total_jobs_failed += failed
                self._stats.total_jobs_skipped += skipped
                self._stats.recovered_jobs_count += recovered_count
                self._stats.consecutive_errors = 0
                self._stats.last_cycle_summary = cycle_summary

            return {
                "success": True,
                "cycle_summary": cycle_summary
            }

        except (sqlite3.OperationalError, sqlite3.DatabaseError) as dbe:
            err_msg = f"Database unavailable / locked: {dbe}"
            logger.error(f"[OBS-WORKER][DB-ERROR] {err_msg}")
            with self._lock:
                self._stats.last_error = err_msg
                self._stats.consecutive_errors += 1
                self._stats.state = WorkerState.ERROR

            return {
                "success": False,
                "error": err_msg,
                "db_unavailable": True
            }

        except Exception as e:
            err_msg = f"Unexpected cycle error: {e}"
            logger.error(f"[OBS-WORKER][CYCLE-ERROR] {err_msg}", exc_info=True)
            with self._lock:
                self._stats.last_error = err_msg
                self._stats.consecutive_errors += 1

            return {
                "success": False,
                "error": err_msg
            }

    def start(self, daemon: bool = True) -> bool:
        """
        Explicitly starts the worker loop in a background thread.
        Returns True if started, False if already running.
        """
        with self._lock:
            if self._thread and self._thread.is_alive():
                logger.warning("[OBS-WORKER] Worker is already running.")
                return False

            self._stop_event.clear()
            self._stats.state = WorkerState.STARTING
            self._stats.is_running = True
            self._stats.started_at = self._now_iso()
            self._stats.stopped_at = None
            self._stats.consecutive_errors = 0

            self._thread = threading.Thread(
                target=self._worker_loop,
                daemon=daemon,
                name=f"aprs-{self.config.worker_id}"
            )
            self._thread.start()
            self._stats.state = WorkerState.IDLE
            self._stats.thread_alive = True

        logger.info(
            f"[OBS-WORKER] Worker '{self.config.worker_id}' started. "
            f"Poll interval: {self.config.poll_interval_seconds}s, Batch size: {self.config.batch_size}"
        )
        return True

    def stop(self, timeout: float = 10.0) -> bool:
        """
        Gracefully signals the worker to stop and waits up to timeout seconds.
        Returns True if stopped cleanly.
        """
        logger.info(f"[OBS-WORKER] Stopping worker '{self.config.worker_id}' gracefully...")
        with self._lock:
            if not self._thread or not self._thread.is_alive():
                self._stats.state = WorkerState.STOPPED
                self._stats.is_running = False
                self._stats.thread_alive = False
                return True

            self._stats.state = WorkerState.STOPPING
            self._stop_event.set()

        # Wait outside lock so loop can finish its current cycle
        self._thread.join(timeout=timeout)
        stopped_cleanly = not self._thread.is_alive()

        with self._lock:
            self._stats.state = WorkerState.STOPPED
            self._stats.is_running = False
            self._stats.thread_alive = False
            self._stats.stopped_at = self._now_iso()

        if stopped_cleanly:
            logger.info(f"[OBS-WORKER] Worker '{self.config.worker_id}' stopped cleanly.")
        else:
            logger.warning(f"[OBS-WORKER] Worker '{self.config.worker_id}' did not terminate within {timeout}s.")

        return stopped_cleanly

    def restart(self, timeout: float = 10.0) -> bool:
        """Stops the worker if running and starts a new worker cycle."""
        self.stop(timeout=timeout)
        return self.start()

    def _worker_loop(self):
        """
        Main worker polling loop.
        Repeatedly calls run_cycle and waits poll_interval_seconds between cycles.
        Exits promptly upon _stop_event.
        """
        logger.info(f"[OBS-WORKER] Entering loop for '{self.config.worker_id}'.")
        cycles = 0

        while not self._stop_event.is_set():
            # Check max_cycles limit (useful for bounded test runs)
            if self.config.max_cycles is not None and cycles >= self.config.max_cycles:
                logger.info(f"[OBS-WORKER] Reached max_cycles ({self.config.max_cycles}). Exiting loop.")
                break

            with self._lock:
                self._stats.state = WorkerState.PROCESSING

            # Execute single polling and observation cycle
            self.run_cycle()
            cycles += 1

            with self._lock:
                if not self._stop_event.is_set():
                    self._stats.state = WorkerState.IDLE
                    self._stats.last_heartbeat = self._now_iso()

            # Responsive wait: exits instantly when stop_event is signaled
            if self._stop_event.is_set():
                break

            # Interruptible sleep
            self._stop_event.wait(timeout=self.config.poll_interval_seconds)

        with self._lock:
            self._stats.state = WorkerState.STOPPED
            self._stats.is_running = False
            self._stats.thread_alive = False
            self._stats.stopped_at = self._now_iso()

        logger.info(f"[OBS-WORKER] Exited loop for '{self.config.worker_id}'. Total cycles: {cycles}")

    def run_forever(self):
        """
        CLI entrypoint runner. Runs in foreground, hooks OS signals (SIGINT, SIGTERM),
        and terminates cleanly on Ctrl+C.
        """
        def handle_signal(sig, frame):
            logger.info(f"[OBS-WORKER] Signal {sig} received. Initiating graceful shutdown...")
            self.stop(timeout=10.0)
            sys.exit(0)

        signal.signal(signal.SIGINT, handle_signal)
        try:
            signal.signal(signal.SIGTERM, handle_signal)
        except AttributeError:
            pass  # SIGTERM may not be available on some Windows Python builds

        logger.info(f"[OBS-WORKER] Running in standalone process mode. Press Ctrl+C to stop.")
        self.start(daemon=False)
        if self._thread:
            self._thread.join()


# ─────────────────────────────────────────────────────────────────────────────
# 3. GLOBAL CONTROLLER (STANDBY BY DEFAULT)
# ─────────────────────────────────────────────────────────────────────────────
# Instantiated in STOPPED state; NEVER started automatically on import or app launch.
observation_worker_controller = ObservationWorker()
