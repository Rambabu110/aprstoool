"""
core/research_sources/registry.py — Central Research Source Registry & Orchestration.

Manages the lifecycle, health synchronization, concurrent execution,
and failure isolation for all 11 research adapters in APRS.
"""

from typing import Dict, List, Optional, Tuple, Set, Any
import os
import sqlite3
import datetime
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger("aprs.research_sources.registry")

from core.research_sources.base import (
    BaseResearchSourceAdapter,
    NormalizedEvidence,
    SourceConflict,
    SourceHealth,
    SignalType,
    EvidenceType
)
from core.research_sources.normalizer import EvidenceNormalizer
from core.research_sources.provenance import ProvenanceTracker

# Import all adapters
from core.research_sources.trends_mcp import TrendsMCPAdapter
from core.research_sources.scavio import ScavioMCPAdapter
from core.research_sources.amazon_india import AmazonIndiaAdapter
from core.research_sources.google_trends import GoogleTrendsAdapter
from core.research_sources.reddit import RedditResearchAdapter
from core.research_sources.youtube import YouTubeResearchAdapter
from core.research_sources.gdelt import GDELTResearchAdapter
from core.research_sources.trendwatch import TrendWatchAdapter
from core.research_sources.tiktok import TikTokResearchAdapter
from core.research_sources.rivalsearch import RivalSearchAdapter
from core.research_sources.trendscope import TrendScopeAdapter
from core.research_sources.amazon_adapter import AmazonResearchAdapter
from core.research_sources.observation import (
    CanonicalObservation,
    SourceStatus,
    SourceExecutionResult,
    ObservationIngestionResult
)
from core.research_sources.ingestion_service import ObservationIngestionService
from core.research_sources.diff_engine import ObservationDiffEngine, ObservationDiffReport


class ResearchSourceRegistry:
    """Singleton registry coordinating all research source adapters."""

    _instance: Optional["ResearchSourceRegistry"] = None

    def __init__(self):
        self._adapters: Dict[str, BaseResearchSourceAdapter] = {}
        self._register_default_adapters()

    @classmethod
    def get_instance(cls) -> "ResearchSourceRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _register_default_adapters(self):
        """Initializes all 11 standardized research adapters."""
        adapters = [
            TrendsMCPAdapter(),
            ScavioMCPAdapter(),
            AmazonIndiaAdapter(),
            GoogleTrendsAdapter(),
            RedditResearchAdapter(),
            YouTubeResearchAdapter(),
            GDELTResearchAdapter(),
            TrendWatchAdapter(),
            TikTokResearchAdapter(),
            RivalSearchAdapter(),
            TrendScopeAdapter()
        ]
        for adapter in adapters:
            self.register_adapter(adapter)

    def register_adapter(self, adapter: BaseResearchSourceAdapter):
        """Registers a research source adapter."""
        self._adapters[adapter.source_name] = adapter

    def get_adapter(self, source_name: str) -> Optional[BaseResearchSourceAdapter]:
        """Retrieves an adapter by name."""
        return self._adapters.get(source_name)

    def list_sources(self) -> List[str]:
        """Returns names of all registered research sources."""
        return list(self._adapters.keys())

    def get_all_health(self) -> Dict[str, SourceHealth]:
        """Gathers health telemetry across all registered adapters."""
        return {name: adapter.health_check() for name, adapter in self._adapters.items()}

    def sync_health_to_db(self, db_path: Optional[str] = None):
        """
        Synchronizes operational health metrics to the SQLite source_health table.
        Truthfully records whether a source was probed/healthy. Never fabricates last_successful_fetch.
        """
        target_path = db_path or os.getenv("APRS_DB_PATH") or "data/research_engine.db"
        health_map = self.get_all_health()
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        try:
            conn = sqlite3.connect(target_path, timeout=5.0)
            cursor = conn.cursor()
            
            for src_name, h in health_map.items():
                freshness = "HEALTHY" if (h.is_healthy and h.last_successful_run is not None) else (
                    "UNPROBED" if (h.last_successful_run is None and h.consecutive_errors == 0) else "DEGRADED"
                )
                cursor.execute("""
                    INSERT INTO source_health (
                        source_name, data_type, last_successful_fetch,
                        failure_count, freshness_status, response_time_ms, details_json, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source_name) DO UPDATE SET
                        last_successful_fetch=excluded.last_successful_fetch,
                        failure_count=excluded.failure_count,
                        freshness_status=excluded.freshness_status,
                        response_time_ms=excluded.response_time_ms,
                        details_json=excluded.details_json,
                        updated_at=excluded.updated_at
                """, (
                    src_name,
                    self._adapters[src_name].source_type,
                    h.last_successful_run,  # NULL if never successfully run — NEVER fake timestamp
                    h.consecutive_errors,
                    freshness,
                    h.average_latency_ms,
                    json.dumps({
                        "status_message": h.status_message,
                        "status": getattr(h, "status", freshness),
                        "records_total": h.records_collected_total,
                        "last_error": h.last_error
                    }),
                    now_iso
                ))
            conn.commit()
            conn.close()
        except Exception as sync_exc:
            logger.warning(f"Failed to sync source health to DB '{target_path}': {sync_exc}")

    def fetch_phase2a_signals(
        self,
        query: str,
        geo: str = "IN",
        limit_per_source: int = 5
    ) -> Tuple[List[NormalizedEvidence], List[SourceConflict]]:
        """
        Phase 2A execution: Queries ONLY Google Trends and GDELT with strict isolation.
        Does NOT trigger the other 9 research adapters.
        """
        phase2a_adapters = [
            self._adapters.get("google_trends"),
            self._adapters.get("gdelt")
        ]
        all_evidence: List[NormalizedEvidence] = []
        seen_hashes: Set[str] = set()

        for adapter in phase2a_adapters:
            if adapter is None:
                continue
            try:
                records = adapter.fetch_signals(query, limit=limit_per_source, geo=geo)
                for rec in records:
                    if not ProvenanceTracker.check_duplicate(rec, seen_hashes):
                        all_evidence.append(rec)
            except Exception as e:
                # Isolate failure: one source failing never stops the other
                pass

        conflicts = EvidenceNormalizer.detect_conflicts(all_evidence)
        return all_evidence, conflicts

    def persist_evidence_to_db(
        self,
        evidence_list: List[NormalizedEvidence],
        product_id: str,
        db_path: Optional[str] = None
    ) -> List[int]:
        """
        Persists NormalizedEvidence into the SQLite intelligence_evidence table.
        Enforces idempotency: does not insert duplicates if already recorded for this product and signal.
        Preserves full provenance inside evidence_details_json.
        """
        if not evidence_list:
            return []

        target_path = db_path or os.getenv("APRS_DB_PATH") or "data/research_engine.db"
        inserted_ids: List[int] = []

        try:
            conn = sqlite3.connect(target_path, timeout=5.0)
            cursor = conn.cursor()

            for ev in evidence_list:
                # Format conclusion string
                if ev.signal_type == SignalType.DEMAND:
                    conclusion = f"Google Trends Interest Index: {ev.value}/100 in {ev.provenance.get('raw_payload', {}).get('geo', 'IN')}"
                elif ev.signal_type == SignalType.KEYWORD:
                    conclusion = f"Google Trends Breakout Query: '{ev.entity}' (+{ev.value}%)"
                elif ev.signal_type == SignalType.NEWS:
                    conclusion = f"GDELT Global News Intensity: {ev.value}% for '{ev.entity}'"
                else:
                    conclusion = f"{ev.source.upper()} {ev.signal_type.value}: {ev.entity} = {ev.value} ({ev.unit})"

                evidence_status = "VERIFIED" if ev.evidence_type == EvidenceType.OBSERVED_SIGNAL else "ESTIMATED"
                confidence_score = round(ev.confidence * 100, 1)

                # Provenance dictionary
                provenance_payload = {
                    "source": ev.source,
                    "evidence_type": ev.evidence_type.value,
                    "entity": ev.entity,
                    "unit": ev.unit,
                    "source_url": ev.source_url,
                    "retrieval_method": ev.provenance.get("retrieval_method"),
                    "tamper_sig": ev.provenance.get("tamper_sig"),
                    "payload_sha256": ev.provenance.get("payload_sha256"),
                    "dedup_hash": ev.generate_dedup_hash(),
                    "raw_payload": ev.provenance.get("raw_payload")
                }

                # Idempotency check: see if record already exists
                cursor.execute("""
                    SELECT evidence_id FROM intelligence_evidence
                    WHERE product_id = ? AND source = ? AND signal_type = ? AND conclusion = ?
                """, (product_id, ev.source, ev.signal_type.value, conclusion))
                existing = cursor.fetchone()

                if existing:
                    # Idempotent: record already persisted
                    inserted_ids.append(existing[0])
                else:
                    cursor.execute("""
                        INSERT INTO intelligence_evidence (
                            product_id, signal_type, conclusion, evidence_status,
                            evidence_details_json, confidence, source, source_timestamp
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))
                    """, (
                        product_id,
                        ev.signal_type.value,
                        conclusion,
                        evidence_status,
                        json.dumps(provenance_payload),
                        confidence_score,
                        ev.source,
                        ev.observed_at
                    ))
                    inserted_ids.append(cursor.lastrowid)

            conn.commit()
            conn.close()

            # Sync updated health to database
            self.sync_health_to_db(target_path)

        except Exception as e:
            logger.error(f"Failed to persist evidence to DB: {e}")

        return inserted_ids

    def execute_phase2a_run(
        self,
        query: str,
        product_id: Optional[str] = None,
        geo: str = "IN",
        limit_per_source: int = 5,
        db_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes a formal Phase 2A research cycle (Google Trends + GDELT)
        tracked within the existing research_runs lifecycle.
        """
        import time
        from core.database import start_research_run, complete_research_run

        t0 = time.time()
        target_path = db_path or os.getenv("APRS_DB_PATH") or "data/research_engine.db"
        run_id = start_research_run()

        evidence, conflicts = self.fetch_phase2a_signals(query=query, geo=geo, limit_per_source=limit_per_source)

        persisted_ids = []
        if product_id and evidence:
            persisted_ids = self.persist_evidence_to_db(evidence, product_id=product_id, db_path=target_path)

        duration_s = round(time.time() - t0, 2)
        errors = []
        for src_name in ["google_trends", "gdelt"]:
            adapter = self._adapters.get(src_name)
            if adapter and adapter.last_error:
                errors.append(f"{src_name}: {adapter.last_error}")

        summary = {
            "query": query,
            "geo": geo,
            "sources_attempted": ["google_trends", "gdelt"],
            "evidence_count": len(evidence),
            "conflicts_count": len(conflicts),
            "persisted_ids_count": len(persisted_ids),
            "duration_seconds": duration_s
        }

        status = "COMPLETED" if len(evidence) > 0 else ("PARTIAL" if len(errors) < 2 else "FAILED")
        complete_research_run(
            research_run_id=run_id,
            products_processed=1 if product_id else 0,
            sources_consulted_count=2,
            signals_generated_count=len(evidence),
            errors=errors,
            summary=summary,
            status=status
        )

        return {
            "run_id": run_id,
            "status": status,
            "evidence": evidence,
            "conflicts": conflicts,
            "persisted_ids": persisted_ids,
            "errors": errors,
            "duration_seconds": duration_s
        }

    def fetch_all_signals(
        self,
        query: str,
        signal_type: Optional[SignalType] = None,
        limit_per_source: int = 5,
        max_workers: int = 4
    ) -> Tuple[List[NormalizedEvidence], List[SourceConflict]]:
        """
        Queries all available adapters in parallel with strict exception isolation.
        A failure in any single external provider will never halt the overall pipeline.
        Deduplicates evidence and detects inter-source conflicts.
        """
        all_evidence: List[NormalizedEvidence] = []
        seen_hashes: Set[str] = set()

        def _fetch_safe(adapter: BaseResearchSourceAdapter) -> List[NormalizedEvidence]:
            try:
                return adapter.fetch_signals(query, limit=limit_per_source)
            except Exception:
                return []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_fetch_safe, a): a for a in self._adapters.values()}
            for future in as_completed(futures):
                try:
                    records = future.result()
                    for rec in records:
                        if signal_type and rec.signal_type != signal_type:
                            continue
                        if not ProvenanceTracker.check_duplicate(rec, seen_hashes):
                            all_evidence.append(rec)
                except Exception:
                    pass

        # Detect conflicts across gathered evidence
        conflicts = EvidenceNormalizer.detect_conflicts(all_evidence)
        return all_evidence, conflicts

    def execute_observation_pipeline(
        self,
        query: str,
        product_id: Optional[str] = None,
        sources: Optional[List[str]] = None,
        marketplace: str = "amazon.in",
        db_path: Optional[str] = None,
        run_diff: bool = True
    ) -> Dict[str, Any]:
        """
        Executes the Phase 6 Observation Pipeline:
        SOURCE -> FETCH -> VALIDATE -> NORMALIZE -> PROVENANCE -> DEDUPLICATE -> STORE -> DIFF
        
        Only invokes verified live-capable sources (default: google_trends, gdelt).
        Does NOT invoke unverified or unconfigured scrapers unless explicitly requested.
        """
        target_path = db_path or os.getenv("APRS_DB_PATH") or "data/research_engine.db"
        selected_sources = sources or ["google_trends", "gdelt"]
        ingestion_service = ObservationIngestionService()

        all_observations: List[CanonicalObservation] = []
        source_results: Dict[str, SourceExecutionResult] = {}
        ingestion_results: List[ObservationIngestionResult] = []
        diff_reports: List[ObservationDiffReport] = []

        for src_name in selected_sources:
            adapter = self._adapters.get(src_name)
            if not adapter and src_name == "amazon_scraper":
                adapter = AmazonResearchAdapter()
            if not adapter:
                source_results[src_name] = SourceExecutionResult(
                    source_id=src_name,
                    status=SourceStatus.UNCONFIGURED,
                    started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    duration_ms=0.0,
                    error_type="UNKNOWN_SOURCE",
                    error_message=f"Source adapter '{src_name}' is not registered."
                )
                continue

            # Execute fetch via canonical contract
            exec_res = adapter.fetch_canonical_observations(
                query=query,
                limit=5,
                product_id=product_id,
                marketplace=marketplace
            )
            source_results[src_name] = exec_res

            for obs in exec_res.observations:
                all_observations.append(obs)
                ing_res, diff_rep = ingestion_service.ingest_observation(
                    obs,
                    db_path=target_path,
                    run_diff=run_diff
                )
                ingestion_results.append(ing_res)
                if diff_rep:
                    diff_reports.append(diff_rep)

        # Check if any material change requires downstream intelligence refresh
        requires_refresh = any(r.requires_intelligence_refresh for r in diff_reports)

        # Sync truthful health state to database
        self.sync_health_to_db(target_path)

        return {
            "query": query,
            "product_id": product_id,
            "sources_attempted": selected_sources,
            "observations_count": len(all_observations),
            "ingestion_summary": {
                "accepted": sum(1 for r in ingestion_results if r.status == "ACCEPTED"),
                "duplicate": sum(1 for r in ingestion_results if r.status == "DUPLICATE"),
                "rejected": sum(1 for r in ingestion_results if r.status == "REJECTED"),
                "error": sum(1 for r in ingestion_results if r.status == "ERROR")
            },
            "source_results": {k: v.model_dump() for k, v in source_results.items()},
            "ingestion_results": [r.model_dump() for r in ingestion_results],
            "diff_reports": [d.model_dump() for d in diff_reports],
            "requires_intelligence_refresh": requires_refresh
        }

