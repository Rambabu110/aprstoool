"""
scratch/test_phase2a_verification.py — Verification script for Phase 2A Real Source Integration.
"""
import os
import sys
import tempfile
import sqlite3
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import core.database
from core.research_sources.google_trends import GoogleTrendsAdapter
from core.research_sources.gdelt import GDELTResearchAdapter
from core.research_sources.registry import ResearchSourceRegistry
from core.research_sources.base import EvidenceType, SignalType

def run_verification():
    print("=== PHASE 2A REAL SOURCE INTEGRATION VERIFICATION ===")
    
    # 1. Setup isolated test database with APRS schema
    tmp_dir = tempfile.mkdtemp()
    test_db = os.path.join(tmp_dir, "test_phase2a.db")
    os.environ["APRS_DB_PATH"] = test_db
    core.database.DB_PATH = test_db
    core.database.init_db()
    
    # Create test product in master_products to satisfy Foreign Key
    conn = sqlite3.connect(test_db)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO master_products (product_id, name, category, region, planned_msrp)
        VALUES ('PROD_TEST_AIR', 'Air Purifier', 'Home Appliances', 'IN', 7999.0)
    """)
    conn.commit()
    conn.close()
    print("[OK] Isolated test database initialized with Foreign Key product 'PROD_TEST_AIR'")

    # 2. Test Google Trends live
    print("\n[1] Testing Google Trends Adapter...")
    gt_adapter = GoogleTrendsAdapter()
    gt_evs = gt_adapter.fetch_signals("air purifier", limit=3, geo="IN")
    print(f"  Google Trends returned {len(gt_evs)} evidence records.")
    for ev in gt_evs:
        print(f"    - [{ev.signal_type.value}] {ev.entity}: {ev.value} ({ev.unit}) | Type: {ev.evidence_type.value}")
        assert ev.evidence_type == EvidenceType.OBSERVED_SIGNAL
        assert ev.source == "google_trends"
        assert ev.provenance.get("payload_sha256") is not None
        assert ev.provenance.get("tamper_sig") is not None
        assert ev.value != 50.0 or ev.signal_type == SignalType.KEYWORD  # ensure no fake 50.0 demand fallback
    gt_health = gt_adapter.health_check()
    print(f"  Google Trends health: status={gt_health.status_message}, is_healthy={gt_health.is_healthy}")
    assert gt_health.is_healthy is True
    assert gt_health.last_successful_run is not None
    assert gt_health.status_message == "ONLINE"

    # 3. Test GDELT Adapter live
    print("\n[2] Testing GDELT Adapter...")
    gdelt_adapter = GDELTResearchAdapter()
    gdelt_evs = gdelt_adapter.fetch_signals("air purifier", limit=2)
    print(f"  GDELT returned {len(gdelt_evs)} evidence records.")
    gdelt_health = gdelt_adapter.health_check()
    print(f"  GDELT health: status={gdelt_health.status_message}, consecutive_errors={gdelt_health.consecutive_errors}, last_error={gdelt_health.last_error}")
    for ev in gdelt_evs:
        print(f"    - [{ev.signal_type.value}] {ev.entity}: {ev.value} ({ev.unit}) | Type: {ev.evidence_type.value}")
        assert ev.evidence_type == EvidenceType.OBSERVED_SIGNAL
        assert ev.source == "gdelt"

    # 4. Test Registry Integration and Persistence
    print("\n[3] Testing Registry Integration & Persistence...")
    reg = ResearchSourceRegistry.get_instance()
    
    # Persist the live observed evidence records from Google Trends
    persisted_ids_1 = reg.persist_evidence_to_db(
        gt_evs,
        product_id="PROD_TEST_AIR",
        db_path=test_db
    )
    print(f"  Persisted {len(persisted_ids_1)} live evidence records to intelligence_evidence: IDs={persisted_ids_1}")
    
    conn = sqlite3.connect(test_db)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM intelligence_evidence WHERE product_id = 'PROD_TEST_AIR'")
    count_run1 = cur.fetchone()[0]
    print(f"  Database intelligence_evidence count after Run 1: {count_run1}")
    assert count_run1 > 0
    assert count_run1 == len(persisted_ids_1)

    # 5. Idempotency Test (Run 2 with exact same product and evidence)
    print("\n[4] Testing Idempotency (Persisting same evidence again)...")
    persisted_ids_2 = reg.persist_evidence_to_db(
        gt_evs,
        product_id="PROD_TEST_AIR",
        db_path=test_db
    )
    cur.execute("SELECT COUNT(*) FROM intelligence_evidence WHERE product_id = 'PROD_TEST_AIR'")
    count_run2 = cur.fetchone()[0]
    print(f"  Database intelligence_evidence count after Run 2: {count_run2}")
    assert count_run2 == count_run1, f"Idempotency failed: count increased from {count_run1} to {count_run2}"
    assert persisted_ids_1 == persisted_ids_2
    print("  [OK] Idempotency verified: identical evidence signals were NOT duplicated in SQLite.")

    # 6. Check Provenance in DB
    print("\n[5] Verifying Provenance in SQLite...")
    cur.execute("SELECT signal_type, conclusion, evidence_status, evidence_details_json FROM intelligence_evidence WHERE product_id = 'PROD_TEST_AIR'")
    rows = cur.fetchall()
    for row in rows:
        st, concl, status, details_json = row
        print(f"    DB Record: [{st}] {concl} | Status: {status}")
        assert "payload_sha256" in details_json
        assert "tamper_sig" in details_json
        assert "dedup_hash" in details_json
        assert "retrieval_method" in details_json
    print("  [OK] Full provenance trail verified in SQLite evidence_details_json.")

    # 7. Check Research Runs in DB
    print("\n[6] Verifying Research Runs Table...")
    run_id = core.database.start_research_run()
    core.database.complete_research_run(
        research_run_id=run_id,
        products_processed=1,
        sources_consulted_count=2,
        signals_generated_count=len(gt_evs),
        status="COMPLETED"
    )
    cur.execute("SELECT research_run_id, run_status, sources_consulted_count, signals_generated_count FROM research_runs")
    runs = cur.fetchall()
    print(f"  Total research_runs in DB: {len(runs)}")
    for r in runs:
        print(f"    Run {r[0]}: status={r[1]}, sources_consulted={r[2]}, signals_generated={r[3]}")
    assert len(runs) >= 1

    # 8. Check Source Health Table
    print("\n[7] Verifying Source Health Table...")
    reg.sync_health_to_db(test_db)
    cur.execute("SELECT source_name, freshness_status, last_successful_fetch, failure_count FROM source_health")
    sh_rows = cur.fetchall()
    for sh in sh_rows:
        if sh[0] in ["google_trends", "gdelt"]:
            print(f"    Source {sh[0]}: freshness={sh[1]}, last_successful_fetch={sh[2]}, failures={sh[3]}")
    conn.close()

    print("\n=== ALL PHASE 2A INTEGRATION CHECKS PASSED SUCCESSFULLY ===")

if __name__ == "__main__":
    run_verification()
