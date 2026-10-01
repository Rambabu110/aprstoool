"""
core/research_sources/normalizer.py — Evidence Normalizer & Conflict Engine.

Standardizes disparate provider formats into strict NormalizedEvidence models,
enforces anti-hallucination boundaries, and identifies inter-source conflicts
without destructive or blind averaging.
"""

from typing import Dict, Any, List, Optional
import datetime
import uuid
from core.research_sources.base import (
    NormalizedEvidence,
    EvidenceType,
    SignalType,
    SourceConflict
)
from core.research_sources.provenance import ProvenanceTracker


class EvidenceNormalizer:
    """Normalizes raw signals, prevents hallucination, and detects evidence conflicts."""

    @staticmethod
    def normalize_record(
        source_name: str,
        source_type: str,
        entity: str,
        signal_type: SignalType,
        value: Any,
        unit: str,
        observed_at: Optional[str] = None,
        confidence: float = 0.8,
        source_url: Optional[str] = None,
        raw_payload: Optional[Any] = None,
        retrieval_method: str = "API_REST",
        adapter_version: str = "1.0.0",
        schema_version: str = "1.0.0",
        claimed_evidence_type: Optional[EvidenceType] = None
    ) -> NormalizedEvidence:
        """
        Builds a verified NormalizedEvidence instance with strict anti-hallucination guardrails.
        """
        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        obs_time = observed_at or now_utc

        # -------------------------------------------------------------
        # ANTI-HALLUCINATION GUARD:
        # Never allow raw external sources to claim verified sales or purchase decisions.
        # -------------------------------------------------------------
        ev_type = claimed_evidence_type or EvidenceType.OBSERVED_SIGNAL
        if ev_type in (EvidenceType.DECISION, EvidenceType.PREDICTION):
            # Downgrade: external sources provide observations or estimates, not system decisions
            ev_type = EvidenceType.ESTIMATE

        # Ensure unit is clean
        clean_unit = str(unit).strip().lower()

        # Build provenance
        prov = ProvenanceTracker.create_provenance(
            source_name=source_name,
            retrieval_method=retrieval_method,
            source_url=source_url,
            raw_payload=raw_payload,
            adapter_version=adapter_version,
            schema_version=schema_version
        )

        # Deterministic record ID
        rec_id = f"{source_name}_{hash(f'{entity}_{obs_time}_{value}') & 0xFFFFFFFF:08x}"

        # Clamped confidence
        clamped_conf = max(0.0, min(1.0, float(confidence)))

        evidence = NormalizedEvidence(
            source=source_name,
            source_type=source_type,
            source_record_id=rec_id,
            entity=str(entity).strip(),
            evidence_type=ev_type,
            signal_type=signal_type,
            value=value,
            unit=clean_unit,
            observed_at=obs_time,
            retrieved_at=now_utc,
            confidence=clamped_conf,
            provenance=prov,
            source_url=source_url,
            adapter_version=adapter_version,
            schema_version=schema_version
        )
        return evidence

    @staticmethod
    def detect_conflicts(
        evidence_list: List[NormalizedEvidence],
        divergence_threshold: float = 0.35
    ) -> List[SourceConflict]:
        """
        Detects conflicts between distinct sources observing the same entity and signal.
        Does NOT blindly average contradictory signals; records structured divergence.
        """
        conflicts: List[SourceConflict] = []
        
        # Group by (entity, signal_type)
        grouped: Dict[tuple, List[NormalizedEvidence]] = {}
        for ev in evidence_list:
            key = (ev.entity.lower().strip(), ev.signal_type)
            grouped.setdefault(key, []).append(ev)

        for (entity, signal_type), records in grouped.items():
            if len(records) < 2:
                continue

            # Compare pairs from different sources
            for i in range(len(records)):
                for j in range(i + 1, len(records)):
                    r1 = records[i]
                    r2 = records[j]
                    if r1.source == r2.source:
                        continue  # Only compare cross-source

                    # If numerical values, compare delta
                    try:
                        v1 = float(r1.value)
                        v2 = float(r2.value)
                        denom = max(abs(v1), abs(v2), 1.0)
                        diff_ratio = abs(v1 - v2) / denom

                        if diff_ratio >= divergence_threshold:
                            conflict = SourceConflict(
                                conflict_id=f"conf_{uuid.uuid4().hex[:12]}",
                                entity=r1.entity,
                                signal_type=signal_type,
                                source_a=r1.source,
                                value_a=v1,
                                timestamp_a=r1.observed_at,
                                source_b=r2.source,
                                value_b=v2,
                                timestamp_b=r2.observed_at,
                                conflict_type="MAGNITUDE_DIVERGENCE",
                                divergence_score=round(diff_ratio, 3),
                                severity="HIGH" if diff_ratio > 0.6 else "MEDIUM",
                                resolution_status="UNRESOLVED",
                                explanation=(
                                    f"Source '{r1.source}' reported {v1} {r1.unit} while "
                                    f"source '{r2.source}' reported {v2} {r2.unit} (delta: {round(diff_ratio*100, 1)}%)."
                                )
                            )
                            conflicts.append(conflict)
                    except (ValueError, TypeError):
                        # Non-numeric comparison (e.g. sentiment or conclusion strings)
                        if str(r1.value).strip().lower() != str(r2.value).strip().lower():
                            conflict = SourceConflict(
                                conflict_id=f"conf_{uuid.uuid4().hex[:12]}",
                                entity=r1.entity,
                                signal_type=signal_type,
                                source_a=r1.source,
                                value_a=r1.value,
                                timestamp_a=r1.observed_at,
                                source_b=r2.source,
                                value_b=r2.value,
                                timestamp_b=r2.observed_at,
                                conflict_type="QUALITATIVE_CONTRADICTION",
                                divergence_score=1.0,
                                severity="MEDIUM",
                                resolution_status="UNRESOLVED",
                                explanation=f"Qualitative mismatch between '{r1.source}' and '{r2.source}'."
                            )
                            conflicts.append(conflict)

        return conflicts
