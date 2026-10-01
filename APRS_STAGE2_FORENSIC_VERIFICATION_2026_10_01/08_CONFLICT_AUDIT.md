# 08 — CONFLICT RESOLUTION & NON-AVERAGING AUDIT
**Date:** 2026-10-01  
**Auditor:** Antigravity Conflict Engine Specialist  

---

## 1. Conflict Detection Architecture

In `core/research_sources/normalizer.py:detect_conflicts()`:
```python
def detect_conflicts(evidence_list: List[NormalizedEvidence], divergence_threshold: float = 0.35) -> List[SourceConflict]:
```

### Key Behavioral Rules Verified:
1. **Non-Blind Averaging:** When two sources report contradictory numbers (e.g., Google Trends = 95 vs. TrendsMCP = 20), the normalizer does **NOT** average them to 57.5.
2. **Dual-Sided Attribution:** Both `source_a`, `source_b`, their exact reported values (`value_a`, `value_b`), and respective observation timestamps (`timestamp_a`, `timestamp_b`) are preserved in full.
3. **Structured Classification:**
   - Divergence > 35% is tagged `MAGNITUDE_DIVERGENCE`.
   - Divergence > 60% is tagged `HIGH` severity.
   - Text/sentiment disagreements are tagged `QUALITATIVE_CONTRADICTION`.

---

## 2. In-Memory vs. Database Persistence

| Dimension | In-Memory (`normalizer.py`) | Production Database (`data_conflicts`) |
|---|---|---|
| **Conflict Structure** | Valid `SourceConflict` model | Pre-existing SQLite schema |
| **Field Mapping** | 100% compatible with `data_conflicts` | Zero conflicts written by new sources |
| **Active Ingestion** | Produces structured list | **DISCONNECTED** (Never written to DB) |

---

## 3. Test Verification

- `tests/test_research_sources.py::TestConflictDetection`:
  - `test_divergent_demand_signals_detected_as_conflict` ✅ PASS (Divergence detected, non-averaging verified)
  - `test_consistent_signals_do_not_produce_conflict` ✅ PASS (Low-variance signals pass without spurious alarms)
- **Status:** **LOGIC VERIFIED IN UNIT TESTS; DISCONNECTED FROM PRODUCTION DATABASE**
