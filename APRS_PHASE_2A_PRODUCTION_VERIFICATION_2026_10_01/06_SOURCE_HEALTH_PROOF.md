# 06 — SOURCE HEALTH PROOF REPORT

**Audit Date:** 2026-10-01  
**Phase:** APRS V8 — Phase 2A Production Readiness Verification  
**Auditor Roles:** Senior Software Architect + Forensic QA Lead + Production Integration Auditor  
**Scope:** Verification of Source Health Semantics and Failure State Integrity  
**Verdict:** **HEALTH STATE MACHINE VERIFIED / RUNTIME SYNC INACTIVE**  

---

## 1. Executive Summary

The audit standard requires:
> "Verify actual source health after the real runtime run.  
> Confirm: INITIALIZED ≠ ONLINE.  
> A successful real fetch should produce a legitimate success state.  
> A failed fetch must not produce ONLINE."

---

## 2. Health State Machine Verification

Testing across `core/research_sources/base.py` and `core/research_sources/registry.py` verified the following state transitions:

### State 1: `INITIALIZED (UNPROBED)`
- **Conditions:** Adapter newly instantiated (`total_calls == 0`, `last_successful_run is None`, `consecutive_errors == 0`).
- **Health Output:** `is_healthy = False`, `status_message = "INITIALIZED (UNPROBED)"`.
- **Database Mapping:** `freshness_status = "UNPROBED"`, `last_successful_fetch = NULL`.
- **Forensic Guarantee:** Eliminates the previous defect where unprobed adapters were stamped with a fake "current time" timestamp.

### State 2: `ONLINE`
- **Conditions:** Requires at least one verified live successful query (`last_successful_run is not None`) and `consecutive_errors == 0`.
- **Health Output:** `is_healthy = True`, `status_message = "ONLINE"`.
- **Database Mapping:** `freshness_status = "HEALTHY"`, `last_successful_fetch = <ISO8601 Timestamp>`.

### State 3: `RATE_LIMITED`
- **Conditions:** Query hits HTTP 429 or provider rate-limiting load-shedding text.
- **Health Output:** `is_healthy = False`, `status_message = "RATE_LIMITED"`.
- **Database Mapping:** `freshness_status = "DEGRADED"`, `consecutive_errors >= 1`.
- **Observed Live Probe:** When Google Trends hit `/sorry/index` and GDELT hit its 5s IP window, both adapters accurately transitioned to `is_healthy = False` and reported `RATE_LIMITED` / `DEGRADED`. Neither reported `ONLINE`.

### State 4: `TIMEOUT`
- **Conditions:** Request exceeds timeout threshold (15.0s).
- **Health Output:** `is_healthy = False`, `status_message = "TIMEOUT"`.
- **Database Mapping:** `freshness_status = "DEGRADED"`, `consecutive_errors >= 1`.

---

## 3. Current Production `source_health` Table State

An inspection of `data/research_engine.db` reveals:
```sql
SELECT source_name, freshness_status, last_successful_fetch, failure_count FROM source_health;
```

**Table Contents (11 rows):**
- Existing sources: `KeepaAPI`, `AmazonLiveScraper`, `ReviewMiner`, `SupplierCatalog`, `UniversalScraper`, `MarketplaceTelemetry`, `EconomicsEngine`, etc.
- Rows for `google_trends` or `gdelt` in production `source_health` table:
  - Total rows remained at 11 because `sync_health_to_db()` has not been invoked by `core/background_daemon.py` or `web/app.py`.

---

## 4. Forensic Verdict

The source health state machine in `core/research_sources/` correctly enforces `INITIALIZED ≠ ONLINE` and prevents failed fetches from reporting `ONLINE`. However, because the APRS runtime does not call `sync_health_to_db()`, production `source_health` telemetry for Google Trends and GDELT is not actively refreshed by the live runtime.
