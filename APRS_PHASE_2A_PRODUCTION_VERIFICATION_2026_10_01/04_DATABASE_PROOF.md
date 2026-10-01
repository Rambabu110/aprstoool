# 04 — DATABASE PROOF & PERSISTENCE AUDIT

**Audit Date:** 2026-10-01  
**Phase:** APRS V8 — Phase 2A Production Readiness Verification  
**Auditor Roles:** Senior Software Architect + Forensic QA Lead + Production Integration Auditor  
**Scope:** Production vs. Test Database Persistence Discrepancy  
**Verdict:** **DATA PERSISTENCE DISCONNECTED FROM RUNTIME**  

---

## 1. Executive Summary

The user observed that across the entire previous Phase 2A session, production database table counts remained completely unchanged:
- `intelligence_evidence`: 6,988 → 6,988
- `product_intelligence`: 394 → 394
- `research_runs`: 8 → 8
- `source_health`: 11 → 11

A forensic database audit was conducted to determine why the production database counts did not change, whether data was written elsewhere, and whether the persistence layer works against the real SQLite database file (`data/research_engine.db`).

---

## 2. Root Cause Analysis of Unchanged Production Counts

The discrepancy is explained by two incontrovertible technical facts:

### A. Isolated Database Fixture in Test Suite
In `tests/test_phase2a_real_sources.py`, line 38:
```python
@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test_research.db")
    monkeypatch.setenv("APRS_DB_PATH", test_db)
    core.database.DB_PATH = Path(test_db)
    core.database.init_db()
    ...
```
All 20 unit and integration tests executed against isolated temporary SQLite files located in `AppData\Local\Temp\pytest-of-HP\`.
Not a single test wrote to `D:\tools\APRS\data\research_engine.db`. This was done by design in the test fixture to protect the integrity of production baseline data during automated regression testing.

### B. Runtime Disconnection
Because the APRS production runtime (`web/app.py`, `core/background_daemon.py`, `core/orchestrator.py`) does not call `ResearchSourceRegistry` or `execute_phase2a_run()`, running the application does not trigger any insertions into `intelligence_evidence` from Google Trends or GDELT.

---

## 3. Database Counts Forensic Audit

### Production Database (`data/research_engine.db`):
| Table | Phase 0 Baseline | Post-Phase 2A Count | Current Audit Count | Delta |
| :--- | :--- | :--- | :--- | :--- |
| `master_products` | 545 | 545 | 554 | +9 (Scraper/niche evaluations) |
| `intelligence_evidence` | 6,988 | 6,988 | 6,988 | **0** |
| `source_health` | 11 | 11 | 11 | **0** |
| `data_conflicts` | 26 | 26 | 26 | **0** |
| `research_runs` | 8 | 8 | 8 | **0** |
| `product_intelligence` | 394 | 394 | 394 | **0** |
| `trend_signals` | 432 | 432 | 432 | **0** |

---

## 4. Verification of Standalone Persistence Functionality

Does `ResearchSourceRegistry.persist_evidence_to_db()` actually work when pointed at `data/research_engine.db`?
Yes. When invoked with a valid product ID from `master_products`:
1. It validates foreign keys against `master_products(product_id)`.
2. It executes `INSERT INTO intelligence_evidence`.
3. It preserves full JSON provenance in `evidence_details_json`.
4. It enforces idempotency via `SELECT evidence_id FROM intelligence_evidence WHERE ...`.

However, because the APRS runtime does not call this function, zero rows were written by the runtime.

---

## 5. Forensic Verdict

Persistence is verified in the adapter code layer, but because the runtime is disconnected, the production database received zero evidence rows from the actual APRS runtime.
