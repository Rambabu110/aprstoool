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
    "ResearchSourceRegistry"
]
