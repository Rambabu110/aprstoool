"""
api/schemas/operations.py — Schemas for War Room, Research Jobs, and Operational Telemetry.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ResearchJobSummary(BaseModel):
    research_run_id: str
    run_status: str
    started_at: str
    ended_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    products_processed: int = 0
    sources_consulted_count: int = 0
    signals_generated_count: int = 0
    alerts_generated_count: int = 0
    gate_transitions_count: int = 0
    errors_count: int = 0


class ResearchJobsResponse(BaseModel):
    jobs: List[ResearchJobSummary]
    total_jobs: int
    active_jobs_count: int
    completed_jobs_count: int
    last_successful_run: Optional[str] = None


class SupervisorLogItem(BaseModel):
    log_id: int
    event_type: str
    timestamp: str
    active_tasks: int
    total_validations: int
    details: Dict[str, Any] = Field(default_factory=dict)


class SupervisorLogsResponse(BaseModel):
    logs: List[SupervisorLogItem]
    total_events: int


class AgentDebatePacket(BaseModel):
    agent: str
    finding: str
    confidence: float
    evidence: List[str]
    risks: List[str]
    missing_data: List[str]
    recommendation: str


class WarRoomDebateResponse(BaseModel):
    product_id: str
    product_name: str
    decision_type: str  # CONSENSUS, DISAGREEMENT, MISSING_EVIDENCE, CRITICAL_RISK
    arbiter_verdict: str
    agent_packets: List[AgentDebatePacket]
    disagreements: List[str]
    consensus_score: float


# ── War Room Interactive Chat & Document Schemas ──────────────────────────
class WarRoomChatRequest(BaseModel):
    user_query: str
    target_speaker: str = "auto"


class WarRoomReply(BaseModel):
    agent_id: str
    agent_name: str
    title: str
    avatar: str
    message: str
    cached: Optional[bool] = False
    latency_sec: Optional[float] = 0.0


class WarRoomChatResponse(BaseModel):
    session_id: str
    replies: List[WarRoomReply]


class WarRoomHistoryItem(BaseModel):
    message_id: int
    session_id: str
    speaker_name: str
    speaker_role: str
    avatar: Optional[str] = None
    user_prompt: str
    response_text: str
    timestamp: str


class WarRoomHistoryResponse(BaseModel):
    total: int
    messages: List[WarRoomHistoryItem]


# ── Operational Alerts & Conflicts Schemas ────────────────────────────────
class AlertItem(BaseModel):
    alert_id: int
    product_id: Optional[str] = None
    severity: str
    title: str
    what_happened: str
    why_it_matters: str
    recommended_action: str
    is_dismissed: int = 0
    created_at: str


class AlertsListResponse(BaseModel):
    total: int
    alerts: List[AlertItem]


class AlertDismissResponse(BaseModel):
    success: bool
    alert_id: int
    message: str


class ConflictItem(BaseModel):
    conflict_id: int
    product_id: Optional[str] = None
    product_name: Optional[str] = None
    field_name: str
    source_a: str
    value_a: str
    source_b: str
    value_b: str
    explanation: Optional[str] = None
    resolution_status: str
    created_at: str


class ConflictsListResponse(BaseModel):
    total: int
    conflicts: List[ConflictItem]


class ConflictResolveRequest(BaseModel):
    resolution_status: str = "RESOLVED"
    explanation: str = "Resolved by operator review"


class ConflictResolveResponse(BaseModel):
    success: bool
    conflict_id: int
    message: str

