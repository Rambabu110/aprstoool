"""
core/research_sources package initialization.
"""

from core.research_sources.base import (
    BaseResearchSourceAdapter,
    NormalizedEvidence,
    SourceConflict,
    SourceHealth,
    EvidenceType,
    SignalType,
    RateLimiter,
    RetryPolicy
)
from core.research_sources.provenance import ProvenanceTracker
from core.research_sources.normalizer import EvidenceNormalizer
from core.research_sources.registry import ResearchSourceRegistry

from core.research_sources.scheduler import (
    ObservationJobScheduler,
    ObservationJob,
    JobStatus,
    SourceEligibility,
    check_source_eligibility
)
from core.research_sources.worker import (
    ObservationWorker,
    WorkerState,
    WorkerConfig,
    WorkerStats,
    observation_worker_controller
)

__all__ = [
    "BaseResearchSourceAdapter",
    "NormalizedEvidence",
    "SourceConflict",
    "SourceHealth",
    "EvidenceType",
    "SignalType",
    "RateLimiter",
    "RetryPolicy",
    "ProvenanceTracker",
    "EvidenceNormalizer",
    "ResearchSourceRegistry",
    "ObservationJobScheduler",
    "ObservationJob",
    "JobStatus",
    "SourceEligibility",
    "check_source_eligibility",
    "ObservationWorker",
    "WorkerState",
    "WorkerConfig",
    "WorkerStats",
    "observation_worker_controller"
]
