# 04 — FIXTURE VS. LIVE AUDIT
**Date:** 2026-10-01  
**Auditor:** Antigravity Forensic QA Team  

---

## 1. Dissecting the 21/21 Unit Test Pass

In the previous report, 21 tests were reported as passing in `tests/test_research_sources.py`. A forensic line-by-line inspection reveals the mechanism of these passes:

| Adapter | Test Method | Test Execution Mechanism | Live Network Call Made? |
|---|---|---|---|
| `trends_mcp` | `test_trends_mcp_successful_mock_response` | Passed `mock_response=[{...}]` in kwargs | ❌ NO (Bypassed via mock) |
| `scavio_mcp` | `test_scavio_mcp_successful_mock_response` | Passed `mock_response=[{...}]` in kwargs | ❌ NO (Bypassed via mock) |
| `amazon_india`| `test_amazon_india_decodo_proxy_config` | Validated string formatting of proxy dict | ❌ NO (No network call) |
| `google_trends`| `test_evidence_normalizer_generates_valid_record`| Directly tested normalizer with dummy dictionary | ❌ NO (Unit calculation only) |
| `reddit` | `test_idempotency_and_deduplication` | Tested normalizer hashing with static text | ❌ NO (Unit calculation only) |
| `gdelt` | `test_registry_failure_isolation` | Mocked `fetch_signals` with `MagicMock` | ❌ NO (Mocked) |
| `all_sources` | `test_health_sync_to_sqlite` | Used temporary SQLite file (`tmp_path`) | ❌ NO (Local temp DB) |

**Finding:** 100% of unit tests pass through deterministic in-memory fixtures and mocked responses. **Zero live HTTP calls were executed during the pytest run.**

---

## 2. Live Runtime Reproduction Results

When tested against live external endpoints without mocks, the reality diverged sharply from unit test assertions:

### 1. Reddit (`RedditResearchAdapter`):
- **Unit Test:** PASS
- **Live Call:** **FAILED (HTTP 403 Forbidden)**
- *Detail:* Reddit blocked unauthenticated requests from python-requests with a 403 Forbidden. The adapter failed to raise an error, caught nothing, and returned an empty list `[]`.

### 2. GDELT (`GDELTResearchAdapter`):
- **Unit Test:** PASS
- **Live Call:** **FAILED (HTTPS Read Timeout > 8.0s)**
- *Detail:* `api.gdeltproject.org` failed to respond within the 8.0s timeout window, returning 0 records.

### 3. Google Trends (`GoogleTrendsAdapter`):
- **Unit Test:** PASS
- **Live Call:** **FAILED (ImportError Fallback)**
- *Detail:* Tried to import non-existent function `get_realtime_trends` from `tools.google_trends_realtime`. Caught exception and silently emitted a hardcoded fallback estimate of `50.0`.

### 4. TikTok, TrendWatch, RivalSearch, TrendScope:
- **Unit Test:** PASS
- **Live Call:** **SYNTHETIC ONLY**
- *Detail:* Implementations contain internal mock/heuristic generators; they do not interact with live external platforms.

---

## 3. Honest Classification Summary

| Dimension | Result |
|---|---|
| **UNIT TEST RESULT** | ✅ **21 / 21 PASS (100% with fixtures & mocks)** |
| **LIVE SOURCE VERIFIED** | ❌ **0 / 11 VERIFIED LIVE IN PRODUCTION** |

> **Critical Forensic Conclusion:** A passing unit test suite with mock fixtures does NOT constitute a live integration. The claims of "all sources operational" were based entirely on unit test mocks.
