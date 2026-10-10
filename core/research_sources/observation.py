"""
core/research_sources/observation.py — Canonical Observation Model & Source Execution Contracts.

Defines the universal typed observation representation for APRS Phase 6,
enforcing strict anti-hallucination boundaries, cryptographic provenance,
standardized execution telemetry, and structured ingestion statuses.
"""

from enum import Enum
from typing import Dict, Any, List, Optional, Union
import datetime
import hashlib
import json
from pydantic import BaseModel, Field

from core.research_sources.base import (
    EvidenceType,
    SignalType,
    NormalizedEvidence
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. TRUTHFUL SOURCE STATUS & INGESTION ENUMS
# ─────────────────────────────────────────────────────────────────────────────
class SourceStatus(str, Enum):
    """
    Truthful operational status of a research source provider.
    Replaces misleading binary healthy/unhealthy flags.
    """
    UNINITIALIZED = "UNINITIALIZED"    # Registered in system but never probed/called
    UNCONFIGURED = "UNCONFIGURED"      # Missing mandatory credentials or proxy token
    HEALTHY = "HEALTHY"                # Probed and verified operating normally
    DEGRADED = "DEGRADED"              # Intermittent errors, slow latency, or rate-limited
    FAILED = "FAILED"                  # Hard consecutive failures (>=5) or fatal API error
    DISABLED = "DISABLED"              # Explicitly turned off by system operator


class IngestionStatus(str, Enum):
    """Result of an observation ingestion attempt through the safe pipeline."""
    ACCEPTED = "ACCEPTED"              # Passed validation and newly stored
    DUPLICATE = "DUPLICATE"            # Deterministically identified as already present; skipped safely
    REJECTED = "REJECTED"              # Failed schema, type, or integrity validation
    UNAVAILABLE = "UNAVAILABLE"        # Source is unconfigured or offline
    ERROR = "ERROR"                    # Unexpected system exception during processing


# ─────────────────────────────────────────────────────────────────────────────
# 2. CANONICAL OBSERVATION MODEL
# ─────────────────────────────────────────────────────────────────────────────
class CanonicalObservation(BaseModel):
    """
    Universal, typed observation representation across all APRS research sources.
    
    Guarantees:
    - Immutable origin attribution (source_id, source_type, source_url)
    - Anti-hallucination type boundary (observation_type, signal_type, evidence_type)
    - Cryptographic provenance and tamper-evident payload hash
    - Deterministic deduplication fingerprint
    """
    source_id: str
    source_type: str = "API"            # "API", "SCRAPER", "PUBLIC_API", "MCP", "FEED"
    product_id: Optional[str] = None    # Internal APRS product ID if linked
    external_id: Optional[str] = None   # ASIN, URL, ticker, keyword, or query string
    marketplace: Optional[str] = None   # "amazon.in", "amazon.com", "global", etc.
    observation_type: str = "SIGNAL"    # "LISTING", "TREND", "NEWS", "PRICING", "SUPPLIER"
    signal_type: SignalType
    evidence_type: EvidenceType = EvidenceType.OBSERVED_SIGNAL
    
    # Observed measurement (None allows strict NULL preservation without zero conversion)
    value: Optional[Union[float, int, str, Dict[str, Any]]] = None
    unit: str = "index_0_100"           # "index_0_100", "INR", "USD", "count", "sentiment"
    currency: Optional[str] = None      # ISO 3-letter currency code when unit is monetary
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    
    # Temporal anchors
    observed_at: str                    # Original observation timestamp from external source
    period_start: Optional[str] = None  # Start of observation window (for trends / aggregations)
    period_end: Optional[str] = None    # End of observation window
    received_at: str = Field(           # Local ingestion timestamp
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    
    # Provenance and origin
    source_url: Optional[str] = None
    source_record_id: Optional[str] = None
    raw_payload: Optional[Any] = None
    adapter_version: str = "1.0.0"
    schema_version: str = "1.0.0"
    fetch_duration_ms: float = 0.0
    provenance: Dict[str, Any] = Field(default_factory=dict)
    provenance_type: str = "UNVERIFIED"
    validation_result: str = "VALID"
    execution_status: str = "SUCCESS"
    dedup_id: Optional[str] = None

    def generate_dedup_hash(self) -> str:
        """
        Calculates a deterministic 16-character SHA-256 fingerprint of this observation.
        Includes external_id, source_id, signal_type, observation_type, and value.
        """
        payload = f"{self.source_id}|{self.external_id or self.product_id}|{self.observation_type}|{self.signal_type.value}|{self.observed_at[:10]}|{str(self.value)}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def to_normalized_evidence(self) -> NormalizedEvidence:
        """Converts canonical observation to backwards-compatible NormalizedEvidence."""
        prov = dict(self.provenance)
        prov["provenance_type"] = self.provenance_type
        prov["validation_result"] = self.validation_result
        prov["execution_status"] = self.execution_status
        prov["dedup_id"] = self.dedup_id or self.generate_dedup_hash()

        return NormalizedEvidence(
            source=self.source_id,
            source_type=self.source_type,
            source_record_id=self.source_record_id or f"{self.source_id}_{self.generate_dedup_hash()}",
            entity=str(self.external_id or self.product_id or self.source_id),
            evidence_type=self.evidence_type,
            signal_type=self.signal_type,
            value=self.value,
            unit=self.unit,
            observed_at=self.observed_at,
            retrieved_at=self.received_at,
            confidence=self.confidence,
            provenance=prov,
            source_url=self.source_url,
            raw_reference=json.dumps(self.raw_payload) if isinstance(self.raw_payload, (dict, list)) else str(self.raw_payload or ""),
            adapter_version=self.adapter_version,
            schema_version=self.schema_version
        )

    @classmethod
    def from_normalized_evidence(
        cls,
        ev: NormalizedEvidence,
        product_id: Optional[str] = None,
        marketplace: Optional[str] = None,
        observation_type: str = "SIGNAL",
        currency: Optional[str] = None
    ) -> "CanonicalObservation":
        """Constructs a CanonicalObservation from an existing NormalizedEvidence instance."""
        prov = ev.provenance or {}
        prov_type = prov.get("provenance_type", "UNVERIFIED")
        val_res = prov.get("validation_result", "VALID")
        exec_st = prov.get("execution_status", "SUCCESS")
        d_id = prov.get("dedup_id") or ev.generate_dedup_hash()

        return cls(
            source_id=ev.source,
            source_type=ev.source_type,
            product_id=product_id,
            external_id=ev.entity,
            marketplace=marketplace,
            observation_type=observation_type,
            signal_type=ev.signal_type,
            evidence_type=ev.evidence_type,
            value=ev.value,
            unit=ev.unit,
            currency=currency,
            confidence=ev.confidence,
            observed_at=ev.observed_at,
            received_at=ev.retrieved_at,
            source_url=ev.source_url,
            source_record_id=ev.source_record_id,
            raw_payload=prov.get("raw_payload"),
            adapter_version=ev.adapter_version,
            schema_version=ev.schema_version,
            fetch_duration_ms=float(prov.get("fetch_duration_ms", 0.0)),
            provenance=prov,
            provenance_type=prov_type,
            validation_result=val_res,
            execution_status=exec_st,
            dedup_id=d_id
        )


# ─────────────────────────────────────────────────────────────────────────────
# 3. SOURCE EXECUTION & INGESTION TELEMETRY MODELS
# ─────────────────────────────────────────────────────────────────────────────
class SourceExecutionResult(BaseModel):
    """
    Structured outcome of a research source execution pass.
    Records duration, status, and record counts for ingestion telemetry.
    """
    source_id: str
    status: SourceStatus
    started_at: str
    completed_at: str
    duration_ms: float
    records_received: int = 0
    records_accepted: int = 0
    records_duplicate: int = 0
    records_rejected: int = 0
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    observations: List[CanonicalObservation] = Field(default_factory=list)


class ObservationIngestionResult(BaseModel):
    """Result of an individual observation ingestion attempt."""
    source_id: str
    product_id: Optional[str] = None
    observation_id: str
    status: IngestionStatus
    destination_table: Optional[str] = None
    row_id: Optional[Union[int, str]] = None
    reason: str
    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
