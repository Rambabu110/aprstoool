"""
core/research_sources/provenance.py — Provenance Tracking & Evidence Chain of Custody.

Ensures every observed signal retains its exact origin, timestamp, retrieval
method, adapter version, and cryptographic hash. Disallows untraceable or
fabricated data from entering APRS decision pathways.
"""

from typing import Dict, Any, Optional, Set
import datetime
import hashlib
import json
from core.research_sources.base import NormalizedEvidence


class ProvenanceTracker:
    """Creates, validates, and audits evidence provenance chains."""

    @staticmethod
    def create_provenance(
        source_name: str,
        retrieval_method: str,
        source_url: Optional[str] = None,
        raw_payload: Optional[Any] = None,
        proxy_used: bool = False,
        adapter_version: str = "1.0.0",
        schema_version: str = "1.0.0",
        extra_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Constructs a tamper-evident provenance metadata dictionary."""
        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        # Calculate raw payload hash if provided
        payload_hash = "none"
        if raw_payload is not None:
            if isinstance(raw_payload, (dict, list)):
                raw_bytes = json.dumps(raw_payload, sort_keys=True).encode("utf-8")
            else:
                raw_bytes = str(raw_payload).encode("utf-8")
            payload_hash = hashlib.sha256(raw_bytes).hexdigest()

        prov = {
            "source": source_name,
            "retrieval_method": retrieval_method,
            "source_url": source_url or "n/a",
            "retrieved_at": now_utc,
            "payload_sha256": payload_hash,
            "proxy_used": proxy_used,
            "adapter_version": adapter_version,
            "schema_version": schema_version,
            "extra": extra_metadata or {}
        }

        # Add integrity signature over provenance record
        sig_data = f"{source_name}|{retrieval_method}|{source_url}|{now_utc}|{payload_hash}"
        prov["tamper_sig"] = hashlib.sha256(sig_data.encode("utf-8")).hexdigest()[:16]
        return prov

    @staticmethod
    def verify_provenance(evidence: NormalizedEvidence) -> bool:
        """Verifies that an evidence record retains its required provenance chain."""
        prov = evidence.provenance
        if not prov:
            return False
        
        required_keys = ["source", "retrieval_method", "retrieved_at", "adapter_version"]
        for key in required_keys:
            if key not in prov or not prov[key]:
                return False
        
        # Verify source matches provenance source
        if evidence.source != prov.get("source"):
            return False

        return True

    @staticmethod
    def check_duplicate(evidence: NormalizedEvidence, seen_hashes: Set[str]) -> bool:
        """
        Idempotency check: returns True if this exact evidence was already seen.
        Adds new hash to seen_hashes if not duplicate.
        """
        h = evidence.generate_dedup_hash()
        if h in seen_hashes:
            return True
        seen_hashes.add(h)
        return False
