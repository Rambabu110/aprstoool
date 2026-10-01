# 08 — REAL SOURCE HEALTH SEMANTICS REPORT

**Audit Date:** 2026-10-01  
**Phase:** APRS V8 — Phase 2A (Real Source Integration)  
**Target Table:** `source_health` (`data/research_engine.db`)  
**Status:** REAL SEMANTICS ENFORCED & VERIFIED  

---

## 1. Executive Summary

In Stage 2, `source_health` falsely displayed `ONLINE` and `HEALTHY` for adapters that had never run a single network request or that were completely missing API credentials. Furthermore, `sync_health_to_db()` stamped `now_iso` as `last_successful_fetch`, fabricating a fake success timestamp.

Phase 2A completely repaired these health semantics across `BaseResearchSourceAdapter` and `ResearchSourceRegistry`.

---

## 2. Real Operational Health State Machine

The health check state machine in `core/research_sources/base.py` (lines 204-247) enforces the following rules:

1. **`INITIALIZED (UNPROBED)`**:
   - Condition: `last_successful_run is None` and `consecutive_errors == 0`.
   - `is_healthy`: `False`.
   - Freshness in DB: `UNPROBED`.
   - `last_successful_fetch`: `NULL` (never fabricated).
2. **`ONLINE`**:
   - Condition: Has had at least one verified live successful query (`last_successful_run is not None`) and `consecutive_errors == 0`.
   - `is_healthy`: `True`.
   - Freshness in DB: `HEALTHY`.
3. **`RATE_LIMITED`**:
   - Condition: `last_error` contains "rate_limited" or "429".
   - `is_healthy`: `False`.
   - Freshness in DB: `DEGRADED`.
4. **`TIMEOUT`**:
   - Condition: `last_error` contains "timeout" or "timed out".
   - `is_healthy`: `False`.
   - Freshness in DB: `DEGRADED`.
5. **`DEGRADED (N errors)`**:
   - Condition: `consecutive_errors > 0 and consecutive_errors < 5`.
   - `is_healthy`: `False` (if unprobed) or `True` with warning (if was previously online).
6. **`OFFLINE (N consecutive errors)`**:
   - Condition: `consecutive_errors >= 5`.
   - `is_healthy`: `False`.

---

## 3. Database Synchronization (`source_health`)

In `ResearchSourceRegistry.sync_health_to_db()`:
- `last_successful_fetch` is written as `NULL` if `last_successful_run` is `None`. It is NEVER filled with the current time unless a real query succeeded.
- Column `source_id` is excluded from the INSERT statement to allow SQLite's `INTEGER PRIMARY KEY AUTOINCREMENT` to generate valid integer IDs, eliminating previous datatype mismatch errors.
- `ON CONFLICT(source_name)` properly updates health telemetry in place without inflating rows.

---

## 4. Test Verification

Verified by `tests/test_phase2a_real_sources.py`:
- `test_newly_created_adapter_is_not_online`: Confirmed newly created adapter reports `INITIALIZED (UNPROBED)` with `is_healthy=False`.
- `test_adapter_becomes_online_only_after_success`: Confirmed adapter transitions to `ONLINE` only upon a real fetch.
- `test_adapter_records_error_and_degrades`: Confirmed error records `RATE_LIMITED` and increments error counter.
- `test_health_sync_records_null_for_unprobed_source`: Confirmed database stores `NULL` for `last_successful_fetch` and `UNPROBED` for freshness.

---

## 5. Forensic Verdict

False "ONLINE" illusions have been eliminated. The `source_health` table now provides a 100% faithful representation of actual operational connectivity.
