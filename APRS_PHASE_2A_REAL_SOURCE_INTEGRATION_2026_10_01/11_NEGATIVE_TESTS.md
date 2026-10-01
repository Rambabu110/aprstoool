# 11 — NEGATIVE & ADVERSARIAL TESTING REPORT

**Audit Date:** 2026-10-01  
**Phase:** APRS V8 — Phase 2A (Real Source Integration)  
**Scope:** Edge Cases, Failures, Adversarial Inputs, Network Outages  
**Status:** 100% RESILIENT (ZERO CRASHES)  

---

## 1. Executive Summary

A core objective of Phase 2A is verifying that real network anomalies, rate limits, corrupt data, and adversarial inputs are safely absorbed by the adapter boundary without crashing the APRS runtime or contaminating the database with invalid records.

---

## 2. Test Scenarios & Results Matrix

| Test Case | Scenario / Vector | Expected Behavior | Actual Behavior | Result |
| :--- | :--- | :--- | :--- | :--- |
| **GT-NEG-01** | Empty / whitespace query string (`"   "`) | Raise `ValueError("INVALID_QUERY")`, return `[]`, increment error count | Returns `[]`, records `INVALID_QUERY`, `consecutive_errors >= 1` | **PASS** |
| **GT-NEG-02** | Google Trends HTTP 429 rate limit | Catch 429, raise `RATE_LIMITED`, return `[]`, update health to `RATE_LIMITED` | Returns `[]`, records `RATE_LIMITED`, health shows `is_healthy=False` | **PASS** |
| **GT-NEG-03** | Google Trends Timeout (>15s) | Catch timeout, raise `TIMEOUT`, return `[]`, update health to `TIMEOUT` | Returns `[]`, records `TIMEOUT`, health shows `is_healthy=False` | **PASS** |
| **GT-NEG-04** | Pytrends suggest fallback injection (`google_suggest_live`) | Intercept source tag, reject synthetic data, raise `UNAVAILABLE`, return `[]` | Returns `[]`, rejects synthetic data, health shows `DEGRADED` | **PASS** |
| **GT-NEG-05** | General network explosion / 500 error | Catch exception, record error, return `[]`, ensure NO hardcoded `50.0` is returned | Returns `[]`, 0 records emitted, NO `50.0` fallback | **PASS** |
| **GDELT-NEG-01** | Empty query string (`""`) | Raise `ValueError("INVALID_QUERY")`, return `[]`, increment error count | Returns `[]`, records `INVALID_QUERY`, `consecutive_errors >= 1` | **PASS** |
| **GDELT-NEG-02** | GDELT HTTP 429 text ("Please limit requests...") | Detect rate limit text, raise `RATE_LIMITED`, return `[]`, health shows `RATE_LIMITED` | Returns `[]`, records `RATE_LIMITED`, health shows `RATE_LIMITED` | **PASS** |
| **GDELT-NEG-03** | GDELT Timeout (>15s) | Catch socket/connect timeout, raise `TIMEOUT`, return `[]` | Returns `[]`, records `TIMEOUT`, health shows `TIMEOUT` | **PASS** |
| **GDELT-NEG-04** | GDELT 500/502/503 Gateway Error | Catch server error status code, raise `HTTP_ERROR`, return `[]` | Returns `[]`, records `HTTP_ERROR`, health shows `DEGRADED` | **PASS** |
| **REG-NEG-01** | Google Trends crashes while GDELT succeeds | Isolated failure: GDELT still delivers signals without crashing caller | GDELT delivers signals; pipeline finishes successfully | **PASS** |
| **REG-NEG-02** | GDELT crashes while Google Trends succeeds | Isolated failure: Google Trends delivers signals without crashing caller | Google Trends delivers signals; pipeline finishes successfully | **PASS** |
| **DB-NEG-01** | Attempt duplicate insertion of identical evidence | Idempotency guard triggers, returns existing IDs, row count unchanged | Count strictly maintained; duplicate rows blocked | **PASS** |

---

## 3. Forensic Conclusion

Every failure mode was tested under automated test fixtures in `tests/test_phase2a_real_sources.py`. The system demonstrated complete failure isolation, perfect rejection of synthetic fallbacks, and total immunity to cascade crashes.
