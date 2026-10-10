"""
core/research_sources/provenance.py — Provenance Tracking & Evidence Chain of Custody.

Ensures every observed signal retains its exact origin, timestamp, retrieval
method, adapter version, and cryptographic hash. Disallows untraceable or
fabricated data from entering APRS decision pathways.
"""

from typing import Dict, Any, Optional, Set
from enum import Enum
import datetime
import hashlib
import json
from core.research_sources.base import NormalizedEvidence


class ProvenanceType(str, Enum):
    """
    Truthful provenance classification for observations and evidence.
    CRITICAL: Never label data as LIVE_VERIFIED without proof of genuine external response.
    """
    LIVE_VERIFIED = "LIVE_VERIFIED"
    CACHED = "CACHED"
    MOCK = "MOCK"
    TEST = "TEST"
    UNVERIFIED = "UNVERIFIED"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    FAILED = "FAILED"


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
        extra_metadata: Optional[Dict[str, Any]] = None,
        provenance_type: str = ProvenanceType.UNVERIFIED.value,
        execution_status: str = "SUCCESS",
        validation_result: str = "VALID",
        dedup_id: Optional[str] = None
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

        # Enforce safety rule: Cannot be LIVE_VERIFIED if retrieval_method is synthetic or mock
        clean_prov_type = str(provenance_type).upper()
        if "MOCK" in retrieval_method.upper() or "SYNTHETIC" in retrieval_method.upper() or "ESTIMATE" in retrieval_method.upper():
            if clean_prov_type == ProvenanceType.LIVE_VERIFIED.value:
                clean_prov_type = ProvenanceType.MOCK.value

        clean_url = source_url or "n/a"
        prov = {
            "source": source_name,
            "retrieval_method": retrieval_method,
            "source_url": clean_url,
            "retrieved_at": now_utc,
            "payload_sha256": payload_hash,
            "proxy_used": proxy_used,
            "adapter_version": adapter_version,
            "schema_version": schema_version,
            "provenance_type": clean_prov_type,
            "execution_status": execution_status,
            "validation_result": validation_result,
            "dedup_id": dedup_id or f"{source_name}_{payload_hash[:16]}",
            "extra": extra_metadata or {}
        }

        # Add integrity signature over provenance record
        sig_data = f"{source_name}|{retrieval_method}|{clean_url}|{now_utc}|{payload_hash}|{clean_prov_type}"
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

        # Records asserting LIVE_VERIFIED must possess an authentic tamper signature
        p_type = prov.get("provenance_type", "")
        if p_type == ProvenanceType.LIVE_VERIFIED.value and not prov.get("tamper_sig"):
            return False

        # Verify tamper signature if present
        if "tamper_sig" in prov:
            src = prov.get("source", "")
            method = prov.get("retrieval_method", "")
            url = prov.get("source_url") or "n/a"
            r_at = prov.get("retrieved_at", "")
            p_hash = prov.get("payload_sha256", "none")
            p_type = prov.get("provenance_type", "")
            sigs_to_check = [
                hashlib.sha256(f"{src}|{method}|{url}|{r_at}|{p_hash}|{p_type}".encode("utf-8")).hexdigest()[:16],
                hashlib.sha256(f"{src}|{method}|{url}|{r_at}|{p_hash}".encode("utf-8")).hexdigest()[:16],
                hashlib.sha256(f"{src}|{method}|None|{r_at}|{p_hash}|{p_type}".encode("utf-8")).hexdigest()[:16],
                hashlib.sha256(f"{src}|{method}|None|{r_at}|{p_hash}".encode("utf-8")).hexdigest()[:16],
            ]
            if prov["tamper_sig"] not in sigs_to_check:
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
