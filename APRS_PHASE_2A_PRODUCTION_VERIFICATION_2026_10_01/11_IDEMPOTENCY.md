# 11 — IDEMPOTENCY & DUPLICATE OBSERVATION AUDIT

**Audit Date:** 2026-10-01  
**Phase:** APRS V8 — Phase 2A Production Readiness Verification  
**Auditor Roles:** Senior Software Architect + Forensic QA Lead + Production Integration Auditor  
**Scope:** Duplicate Prevention & Idempotent Persistence Verification  
**Verdict:** **STRICT IDEMPOTENCY VERIFIED**  

---

## 1. Executive Summary

The audit standard requires:
> "Run the same research operation twice.  
> Determine whether the existing architecture expects duplicate observations OR idempotent evidence.  
> Verify the implementation behaves according to the existing design.  
> Report:  
> FIRST RUN  
> SECOND RUN  
> NEW ROWS  
> DUPLICATES PREVENTED / ALLOWED  
> REASON"

---

## 2. Architectural Duplicate Policy

In APRS V8:
- Multiple observations of market reality over distinct time periods are permitted when timestamps or values change.
- However, inserting the exact same evidence record with the identical conclusion for the same product during repeated execution cycles must NOT inflate `intelligence_evidence` row count.
- In `core/research_sources/registry.py:persist_evidence_to_db()`:
  ```python
  cursor.execute("""
      SELECT evidence_id FROM intelligence_evidence
      WHERE product_id = ? AND source = ? AND signal_type = ? AND conclusion = ?
  """, (product_id, ev.source, ev.signal_type.value, conclusion))
  existing = cursor.fetchone()
  if existing:
      persisted_ids.append(existing[0])
      continue
  ```

---

## 3. Idempotency Test Execution Report

Executed via automated test in `tests/test_phase2a_real_sources.py:test_idempotency_prevents_duplicate_evidence_rows`:

- **Target Product:** `TEST_PROD_101` (`Smart Air Purifier`)
- **Evidence Signal:** Google Trends Demand Index = 65.0/100 (`SignalType.DEMAND`)

### Execution Trace:
- **FIRST RUN:**
  - Persisted evidence IDs returned: `[1]`
  - Table count in `intelligence_evidence`: `1`
  - **NEW ROWS:** `1`
- **SECOND RUN (Exact same product and evidence):**
  - Persisted evidence IDs returned: `[1]` (matches first run)
  - Table count in `intelligence_evidence`: `1`
  - **NEW ROWS:** `0`
- **DUPLICATES PREVENTED / ALLOWED:** **PREVENTED**
- **REASON:** The pre-insertion uniqueness query detected an identical tuple of `(product_id, source, signal_type, conclusion)`. Instead of inserting a duplicate row, the existing primary key `evidence_id = 1` was returned, maintaining database hygiene and preventing row inflation.

---

## 4. Forensic Verdict

Idempotency is strictly enforced by `ResearchSourceRegistry.persist_evidence_to_db()`. Re-running research operations on the same product produces zero duplicate rows.
