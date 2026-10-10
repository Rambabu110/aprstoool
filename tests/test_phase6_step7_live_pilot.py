"""
tests/test_phase6_step7_live_pilot.py — Verification of Pilot Isolation, Baseline Reconciliation, and Safety Controls.

Phase 6 Step 7 Test Requirements:
1. Baseline reconciliation verification: verifies authoritative SHA-256, page counts, and 22 source_health rows.
2. Production DB isolation: verifies ControlledPilotRunner fails closed on production paths.
3. Process-level environment isolation: verifies _isolation_context manages APRS_DB_PATH safely.
4. Dry-run zero-write guarantee: verifies dry-run mode performs zero SQLite writes and zero network calls.
5. Anti-hallucination / Anti-synthetic guard: verifies that unverified or fallback responses are rejected from LIVE_VERIFIED.
6. Provenance signature integrity: verifies tamper_sig is an unkeyed SHA-256 digest, not an authenticated HMAC.
"""

import os
import sys
import json
import sqlite3
import hashlib
import tempfile
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.research_sources.pilot import (
    ControlledPilotRunner,
    PilotConfig,
    PilotSourceApproval,
    PilotRunSummary
)
from core.research_sources.scheduler import ObservationJobScheduler, ensure_job_tables
from core.research_sources.provenance import ProvenanceTracker, ProvenanceType
from core.research_sources.base import NormalizedEvidence, SignalType, EvidenceType
from core.database import get_connection, init_db

PROD_DB_PATH = os.path.abspath("data/research_engine.db")
EXPECTED_SHA256 = "ff0bb8efcdbf113d10adecbac549329d7646fcfb54a0fad8f9555e2ff17e3833"


def test_baseline_reconciliation_integrity():
    """Verifies that the authoritative production database matches the reconciled Phase 6 baseline."""
    assert os.path.exists(PROD_DB_PATH), "Production database must exist"

    with open(PROD_DB_PATH, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    assert digest == EXPECTED_SHA256, f"Production DB hash mismatch: expected {EXPECTED_SHA256}, got {digest}"

    conn = sqlite3.connect(f"file:{PROD_DB_PATH}?mode=ro", uri=True)
    cur = conn.cursor()

    # Verify source_health has exactly 22 rows (11 legacy + 11 registered in Phase 5)
    cur.execute("SELECT count(*) FROM source_health")
    assert cur.fetchone()[0] == 22, "source_health must have exactly 22 rows"

    # Verify protected historical rows
    cur.execute("SELECT count(*) FROM decision_ledger WHERE product_id = 'US_B09ABC'")
    assert cur.fetchone()[0] == 1, "Historical decision US_B09ABC must be preserved"

    cur.execute("SELECT count(*) FROM intelligence_evidence WHERE evidence_id BETWEEN 16366 AND 16445")
    assert cur.fetchone()[0] == 80, "Historical evidence 16366-16445 must be preserved"

    cur.execute("SELECT count(*) FROM intelligence_timeline WHERE timeline_id BETWEEN 2600 AND 2615")
    assert cur.fetchone()[0] == 16, "Historical timeline 2600-2615 must be preserved"

    # Total row count
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [r[0] for r in cur.fetchall()]
    total_rows = 0
    for t in tables:
        cur.execute(f"SELECT count(*) FROM [{t}]")
        total_rows += cur.fetchone()[0]
    assert total_rows == 54881, f"Expected exactly 54,881 total rows, found {total_rows}"

    conn.close()


def test_pilot_fails_closed_on_production_path():
    """Proves ControlledPilotRunner strictly refuses to run on data/research_engine.db."""
    with pytest.raises(PermissionError, match="SAFETY HALT"):
        ControlledPilotRunner(PilotConfig(db_path=PROD_DB_PATH))

    with pytest.raises(PermissionError, match="SAFETY HALT"):
        ControlledPilotRunner(PilotConfig(db_path="data/research_engine.db"))

    with pytest.raises(PermissionError, match="SAFETY HALT"):
        ControlledPilotRunner(PilotConfig(db_path="C:/some/path/research_engine.db"))


def test_pilot_isolation_context_sets_and_restores_env():
    """Proves _isolation_context redirects APRS_DB_PATH and cleanly restores environment on exit."""
    temp_dir = tempfile.gettempdir()
    temp_db = os.path.abspath(os.path.join(temp_dir, f"test_iso_env_{int(time_ns := 12345)}.db"))
    
    orig_env = os.environ.get("APRS_DB_PATH")
    runner = ControlledPilotRunner(PilotConfig(db_path=temp_db))

    with runner._isolation_context():
        assert os.environ.get("APRS_DB_PATH") == temp_db
        # get_connection() without args must resolve to temp_db
        from core.database import get_db_path
        assert str(get_db_path()) == temp_db

    # Restored
    assert os.environ.get("APRS_DB_PATH") == orig_env


def test_dry_run_zero_writes_guarantee():
    """Proves that execute_dry_run() performs zero SQLite writes and zero external calls."""
    temp_dir = tempfile.gettempdir()
    temp_db = os.path.abspath(os.path.join(temp_dir, f"test_dry_run_zero_{os.getpid()}.db"))
    if os.path.exists(temp_db):
        os.remove(temp_db)

    runner = ControlledPilotRunner(PilotConfig(db_path=temp_db))
    res = runner.execute_dry_run()

    assert res["mode"] == "DRY_RUN"
    assert res["writes_performed"] == 0
    assert res["external_calls_performed"] == 0
    assert not os.path.exists(temp_db), "Dry-run on nonexistent DB must not create or write file"


def test_provenance_signature_is_unkeyed_digest():
    """
    Verifies that tamper_sig is an unkeyed SHA-256 digest over provenance fields,
    confirming it is a tamper-evident checksum and NOT an authenticated HMAC.
    """
    prov = ProvenanceTracker.create_provenance(
        source_name="google_trends",
        retrieval_method="PUBLIC_API_REST",
        source_url="https://trends.google.com",
        raw_payload={"query": "test"},
        provenance_type=ProvenanceType.UNVERIFIED.value
    )
    assert "tamper_sig" in prov
    assert len(prov["tamper_sig"]) == 16  # First 16 hex chars

    # Reconstruct manual sha256
    sig_data = f"{prov['source']}|{prov['retrieval_method']}|{prov['source_url']}|{prov['retrieved_at']}|{prov['payload_sha256']}|{prov['provenance_type']}"
    expected_hash = hashlib.sha256(sig_data.encode("utf-8")).hexdigest()[:16]
    assert prov["tamper_sig"] == expected_hash, "tamper_sig must match deterministic unkeyed SHA-256 checksum"


def test_unverified_fallback_cannot_be_marked_live():
    """Verifies that synthetic or mock retrieval methods are prohibited from claiming LIVE_VERIFIED."""
    prov = ProvenanceTracker.create_provenance(
        source_name="google_trends",
        retrieval_method="MOCK_FALLBACK",
        source_url="https://trends.google.com",
        provenance_type="LIVE_VERIFIED"
    )
    # create_provenance must demote to MOCK
    assert prov["provenance_type"] == "MOCK"
