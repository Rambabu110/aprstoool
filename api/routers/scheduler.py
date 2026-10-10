"""
api/routers/scheduler.py — Research Scheduler & Observation Maturity Router.
Reuses daemon_controller from core.background_daemon and ObservationScheduler from core.observation_scheduler.
"""
from typing import Dict, Any, List, Optional, Union
import datetime
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from core.background_daemon import daemon_controller
from core.observation_scheduler import ObservationScheduler

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


class DaemonStatusResponse(BaseModel):
    is_paused: bool
    current_niche: str
    niche_index: int
    total_niches: int
    total_discovered_session: int
    swarm_pass_count: int
    swarm_fail_count: int
    recent_logs: List[Any]
    thread_alive: bool
    # Frontend compatibility fields
    daemon_name: str = "APRS Autonomous Research Daemon"
    is_running: bool = False
    last_heartbeat: Optional[str] = None
    poll_interval_seconds: int = 3600
    mode: str = "STANDBY"
    message: str = "Autonomous background supervisor awaiting scheduled cycle."


class ObservationMaturitySummary(BaseModel):
    total_launched_products: int
    total_scheduled_windows: int
    observed_count: int
    partially_observed_count: int
    due_count: int
    overdue_count: int
    not_due_count: int
    as_of_date: str


class ScheduledProductItem(BaseModel):
    product_id: str
    product_name: str
    is_launched: bool
    launch_status: str
    effective_launch_date: Optional[str] = None
    schedule_status: str
    windows: List[Dict[str, Any]]
    next_expected_observation: Optional[Any] = None
    due_windows_count: int
    overdue_windows_count: int
    observed_windows_count: int


class ObservationSchedulesResponse(BaseModel):
    maturity_summary: ObservationMaturitySummary
    schedules: List[ScheduledProductItem]
    # Frontend compatibility fields
    total_scheduled: int = 0
    ready_for_observation: int = 0
    pending_observation: int = 0
    products: List[Dict[str, Any]] = []


@router.get("/daemon", response_model=DaemonStatusResponse)
def get_daemon_status():
    """Returns live status of the autonomous background scraping and swarm daemon."""
    status = daemon_controller.get_status()
    thread_alive = bool(status.get("thread_alive", False))
    is_paused = bool(status.get("is_paused", False))
    is_running = thread_alive and not is_paused
    mode = "PAUSED" if is_paused else ("RUNNING" if thread_alive else "STANDBY")
    
    return DaemonStatusResponse(
        **status,
        daemon_name="APRS Autonomous Research Daemon",
        is_running=is_running,
        last_heartbeat=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC") if thread_alive else "Standby on demand",
        poll_interval_seconds=3600,
        mode=mode,
        message="Daemon thread active and processing niches." if thread_alive else "Autonomous background supervisor standing by."
    )


@router.post("/daemon/pause")
def pause_daemon():
    """Pauses background research cycle execution."""
    daemon_controller.pause()
    return {"status": "paused", "is_paused": True}


@router.post("/daemon/resume")
def resume_daemon():
    """Resumes background research cycle execution."""
    daemon_controller.resume()
    return {"status": "resumed", "is_paused": False}


@router.get("/observation-maturity", response_model=ObservationSchedulesResponse)
def get_observation_maturity():
    """Returns V8 observation schedules and maturity tracking across launched products."""
    maturity = ObservationScheduler.get_maturity_summary()
    catalog_schedules = ObservationScheduler.get_catalog_schedules()
    
    # Compute legacy/frontend table fields
    fe_products = []
    ready_count = 0
    pending_count = 0
    for s in catalog_schedules:
        next_obs = s.get("next_expected_observation") or {}
        is_ready = (s.get("due_windows_count", 0) > 0 or s.get("overdue_windows_count", 0) > 0)
        if is_ready:
            ready_count += 1
        else:
            pending_count += 1
            
        fe_products.append({
            "product_id": s.get("product_id"),
            "decision_date": s.get("effective_launch_date") or "-",
            "first_expected_date": next_obs.get("due_date") if isinstance(next_obs, dict) else "-",
            "observation_window_days": next_obs.get("duration_days", 30) if isinstance(next_obs, dict) else 30,
            "status": "READY" if is_ready else "PENDING",
            "next_expected_observation": next_obs,
        })
        
    return ObservationSchedulesResponse(
        maturity_summary=ObservationMaturitySummary(**maturity),
        schedules=[ScheduledProductItem(**s) for s in catalog_schedules],
        total_scheduled=maturity.get("total_launched_products", len(catalog_schedules)),
        ready_for_observation=ready_count,
        pending_observation=pending_count,
        products=fe_products
    )


class ProductObservationTriggerResponse(BaseModel):
    product_id: str
    product_name: str
    is_launched: bool
    schedule_status: str
    effective_launch_date: Optional[str] = None
    due_windows_count: int
    overdue_windows_count: int
    observed_windows_count: int
    next_expected_observation: Optional[Any] = None
    observation_job_state: str
    checked_at: str


@router.post("/observe/{product_id}", response_model=ProductObservationTriggerResponse)
def trigger_product_observation(product_id: str):
    """
    Explicit action endpoint: Triggers an observation window maturity check for a product.
    Determines due/overdue status without mutating production data unless actual observations are supplied.
    """
    try:
        sched = ObservationScheduler.get_product_schedule(product_id)
    except (ValueError, KeyError):
        raise HTTPException(status_code=404, detail=f"Product '{product_id}' not found in catalog.")

    if not sched:
        raise HTTPException(status_code=404, detail=f"Product '{product_id}' not found in catalog.")

    if not sched.get("is_launched"):
        job_state = "SKIPPED_NOT_LAUNCHED"
    elif sched.get("due_windows_count", 0) > 0 or sched.get("overdue_windows_count", 0) > 0:
        job_state = "QUEUED_FOR_INGESTION"
    elif sched.get("observed_windows_count", 0) > 0:
        job_state = "COMPLETED"
    else:
        job_state = "SCHEDULED_NOT_DUE"

    return ProductObservationTriggerResponse(
        product_id=product_id,
        product_name=sched.get("product_name", "Product"),
        is_launched=sched.get("is_launched", False),
        schedule_status=sched.get("schedule_status", "UNKNOWN"),
        effective_launch_date=sched.get("effective_launch_date"),
        due_windows_count=sched.get("due_windows_count", 0),
        overdue_windows_count=sched.get("overdue_windows_count", 0),
        observed_windows_count=sched.get("observed_windows_count", 0),
        next_expected_observation=sched.get("next_expected_observation"),
        observation_job_state=job_state,
        checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat()
    )


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 6 SAFE OBSERVATION JOB SCHEDULER & ONE-SHOT RUNNER ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

class ObservationJobResponse(BaseModel):
    job_id: int
    product_id: str
    source_id: str
    scheduled_at: str
    status: str
    attempt_count: int
    last_attempt_at: Optional[str] = None
    last_success_at: Optional[str] = None
    next_run_at: Optional[str] = None
    last_error: Optional[str] = None
    created_at: str
    updated_at: str


class ObservationJobCreate(BaseModel):
    product_id: str
    source_id: str
    scheduled_at: Optional[str] = None


class SchedulerRunOnceResponse(BaseModel):
    dry_run: bool
    requested_limit: int
    due_jobs_count: Optional[int] = None
    found_due: Optional[int] = None
    eligible_count: Optional[int] = None
    skipped_count: Optional[int] = None
    executed: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    jobs: Union[List[Dict[str, Any]], Dict[str, Any]]


@router.get("/jobs", response_model=List[ObservationJobResponse], summary="List Observation Jobs")
def list_observation_jobs(
    status: Optional[str] = None,
    product_id: Optional[str] = None,
    source_id: Optional[str] = None,
    limit: int = 50
):
    """
    Returns observation jobs with optional status, product, or source filtering.
    """
    from core.research_sources.scheduler import ObservationJobScheduler
    bounded_limit = max(1, min(limit, 100))
    jobs = ObservationJobScheduler.list_jobs(
        status=status,
        product_id=product_id,
        source_id=source_id,
        limit=bounded_limit
    )
    return [ObservationJobResponse(**j.model_dump()) for j in jobs]


@router.get("/jobs/due", response_model=List[ObservationJobResponse], summary="List Due Observation Jobs")
def get_due_observation_jobs(
    limit: int = 50,
    as_of: Optional[str] = None
):
    """
    Deterministically returns jobs currently due for observation (next_run_at <= as_of/now).
    """
    from core.research_sources.scheduler import ObservationJobScheduler
    bounded_limit = max(1, min(limit, 100))
    due_jobs = ObservationJobScheduler.get_due_jobs(
        now=as_of,
        limit=bounded_limit
    )
    return [ObservationJobResponse(**j.model_dump()) for j in due_jobs]


@router.post("/jobs", response_model=ObservationJobResponse, summary="Create Observation Job")
def create_observation_job(payload: ObservationJobCreate):
    """
    Creates and schedules a new observation job for a product and verified source.
    """
    from core.research_sources.scheduler import ObservationJobScheduler
    try:
        job = ObservationJobScheduler.create_job(
            product_id=payload.product_id,
            source_id=payload.source_id,
            scheduled_at=payload.scheduled_at
        )
        return ObservationJobResponse(**job.model_dump())
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))


@router.post("/run-once", response_model=SchedulerRunOnceResponse, summary="One-Shot Observation Job Runner")
def run_due_jobs_once(
    limit: int = 10,
    dry_run: bool = False,
    as_of: Optional[str] = None
):
    """
    Safe one-shot execution pass:
    - Finds due jobs (next_run_at <= as_of/now) up to bounded limit.
    - If dry_run=True: verifies eligibility and reports what WOULD run without mutating DB.
    - If dry_run=False: executes each due job through the Phase 6 observation pipeline and captures summary.
    - Terminates cleanly without background daemons.
    """
    from core.research_sources.scheduler import ObservationJobScheduler
    bounded_limit = max(1, min(limit, 100))
    summary = ObservationJobScheduler.run_due_jobs(
        now=as_of,
        limit=bounded_limit,
        dry_run=dry_run
    )
    return SchedulerRunOnceResponse(**summary)


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 6 STEP 4 CONTROLLED PERSISTENT OBSERVATION WORKER ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

class WorkerStatsResponse(BaseModel):
    worker_id: str
    state: str
    is_running: bool
    thread_alive: bool
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


class WorkerStartRequest(BaseModel):
    poll_interval_seconds: Optional[float] = None
    batch_size: Optional[int] = None
    running_lease_seconds: Optional[float] = None


class WorkerRecoveryResponse(BaseModel):
    lease_seconds: float
    cutoff_timestamp: str
    scanned_count: int
    recovered_to_retry: List[int]
    marked_failed: List[int]
    total_recovered: int


@router.get("/worker/status", response_model=WorkerStatsResponse, summary="Get Observation Worker Status")
def get_observation_worker_status():
    """
    Returns live health, state, and telemetry of the controlled persistent observation worker.
    Does NOT start the worker.
    """
    from core.research_sources.worker import observation_worker_controller
    stats = observation_worker_controller.get_status()
    return WorkerStatsResponse(**stats.model_dump())


@router.post("/worker/start", response_model=WorkerStatsResponse, summary="Start Observation Worker")
def start_observation_worker(payload: Optional[WorkerStartRequest] = None):
    """
    Explicitly starts the controlled persistent observation worker in a background thread.
    """
    from core.research_sources.worker import observation_worker_controller
    if payload:
        if payload.poll_interval_seconds is not None:
            observation_worker_controller.config.poll_interval_seconds = max(1.0, payload.poll_interval_seconds)
            observation_worker_controller._stats.poll_interval_seconds = observation_worker_controller.config.poll_interval_seconds
        if payload.batch_size is not None:
            observation_worker_controller.config.batch_size = max(1, min(100, payload.batch_size))
            observation_worker_controller._stats.batch_size = observation_worker_controller.config.batch_size
        if payload.running_lease_seconds is not None:
            observation_worker_controller.config.running_lease_seconds = max(5.0, payload.running_lease_seconds)
            observation_worker_controller._stats.running_lease_seconds = observation_worker_controller.config.running_lease_seconds

    observation_worker_controller.start()
    stats = observation_worker_controller.get_status()
    return WorkerStatsResponse(**stats.model_dump())


@router.post("/worker/stop", response_model=WorkerStatsResponse, summary="Stop Observation Worker")
def stop_observation_worker(timeout: float = 10.0):
    """
    Gracefully signals the controlled observation worker to stop and waits for in-flight jobs to complete.
    """
    from core.research_sources.worker import observation_worker_controller
    observation_worker_controller.stop(timeout=max(1.0, min(60.0, timeout)))
    stats = observation_worker_controller.get_status()
    return WorkerStatsResponse(**stats.model_dump())


@router.post("/worker/recover", response_model=WorkerRecoveryResponse, summary="Recover Abandoned Observation Jobs")
def recover_abandoned_observation_jobs(lease_seconds: Optional[float] = None):
    """
    Explicitly triggers crash recovery of abandoned RUNNING jobs whose execution lease has expired.
    """
    from core.research_sources.worker import observation_worker_controller
    recovery_res = observation_worker_controller.recover_abandoned_jobs(lease_seconds=lease_seconds)
    return WorkerRecoveryResponse(**recovery_res)


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 6 STEP 6 CONTROLLED BOUNDED PILOT ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

class PilotRequest(BaseModel):
    max_products: int = Field(default=3, ge=1, le=10)
    max_jobs: int = Field(default=3, ge=1, le=10)
    approved_sources: Optional[List[str]] = None
    timeout_seconds: float = Field(default=8.0, ge=1.0, le=30.0)
    db_path: Optional[str] = None


@router.post("/pilot/dry-run", summary="Execute Pilot Dry Run")
def execute_pilot_dry_run(payload: Optional[PilotRequest] = None):
    """
    Executes a dry-run of the bounded observation pilot.
    Reports prospective jobs, product queries, and source approvals without mutating DB or calling paid APIs.
    Fails closed if the database path points to production.
    """
    from core.research_sources.pilot import ControlledPilotRunner, PilotConfig
    req = payload or PilotRequest()
    target_db = req.db_path or os.getenv("APRS_DB_PATH")
    if not target_db:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pilot requires an explicit isolated db_path or APRS_DB_PATH environment variable."
        )

    try:
        config = PilotConfig(
            max_products=req.max_products,
            max_jobs=req.max_jobs,
            approved_sources=req.approved_sources or ["google_trends"],
            timeout_seconds=req.timeout_seconds,
            db_path=target_db
        )
        runner = ControlledPilotRunner(config=config)
        return runner.execute_dry_run()
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/pilot/run", summary="Execute Bounded Live Pilot")
def execute_bounded_pilot(payload: Optional[PilotRequest] = None):
    """
    Executes a tightly bounded pilot against approved zero-cost sources in an isolated DB.
    Fails closed if the database path points to production.
    """
    from core.research_sources.pilot import ControlledPilotRunner, PilotConfig
    req = payload or PilotRequest()
    target_db = req.db_path or os.getenv("APRS_DB_PATH")
    if not target_db:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pilot requires an explicit isolated db_path or APRS_DB_PATH environment variable."
        )

    try:
        config = PilotConfig(
            max_products=req.max_products,
            max_jobs=req.max_jobs,
            approved_sources=req.approved_sources or ["google_trends"],
            timeout_seconds=req.timeout_seconds,
            db_path=target_db
        )
        runner = ControlledPilotRunner(config=config)
        summary = runner.execute_bounded_pilot()
        return summary.model_dump()
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))



