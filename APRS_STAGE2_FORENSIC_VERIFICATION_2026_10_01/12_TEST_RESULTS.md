# 12 — SEPARATED TEST RESULTS AUDIT
**Date:** 2026-10-01  
**Auditor:** Antigravity Forensic QA Team  

---

## 1. Category 1: UNIT TEST RESULTS

All unit tests execute within isolated test runners using deterministic mock fixtures and monkey-patched network calls:

| Suite | Tests | Result | Notes |
|---|---|---|---|
| `tests/test_research_sources.py` | 21 | ✅ **PASS** | Tests configuration, auth flags, normalizer, and provenance hashing using mocks |
| `tests/test_daemon_matcher_regression.py` | 15 | ✅ **PASS** | Contract tests verifying tuple unpacking and duplicate detection |
| Pre-Existing APRS Suite | 357 | ✅ **PASS** | V6 economics, V7 intelligence, V8 outcomes, calibration, and learning engines |
| **Total Full Test Suite** | **393** | ✅ **393 / 393 PASS (100%)** | Duration: 89.13s |

---

## 2. Category 2: LIVE INTEGRATION RESULTS

Individual probe of live external endpoints without mock fixtures:

| Source | Target Protocol / URL | Live Probe Result | Diagnosis |
|---|---|---|---|
| `reddit` | Public JSON (`reddit.com/r/all/search.json`) | ❌ **FAIL (HTTP 403)** | Blocked by Reddit anti-bot; requires OAuth app registration |
| `gdelt` | GDELT 2.0 DOC API (`api.gdeltproject.org`) | ❌ **FAIL (Timeout)** | Read timed out (>8.0s) |
| `google_trends` | Local engine bridge | ❌ **FAIL (ImportError)** | Broken import `get_realtime_trends`; fell back to static `50.0` |
| `youtube` | Google Data API v3 | ⚠️ **FALLBACK** | No key in `.env`; fell back to synthetic estimates |
| `trends_mcp` | Trends-MCP API | ⚠️ **UNPROBED** | Credential present; unprobed by background daemon |
| `scavio_mcp` | Scavio MCP API | ⚠️ **UNPROBED** | Credential present; unprobed by background daemon |
| `amazon_india` | Amazon.in via Decodo proxy | ⚠️ **UNPROBED** | Proxy configured; unprobed by background daemon |
| `trendwatch` | Internal compute | ℹ️ **SYNTHETIC** | Internal velocity heuristic only |
| `tiktok` | Simulated feed | ℹ️ **SYNTHETIC** | Synthetic mock generator only |
| `rivalsearch` | Simulated SERP | ℹ️ **SYNTHETIC** | Synthetic mock generator only |
| `trendscope` | Simulated composite | ℹ️ **SYNTHETIC** | Synthetic composite weighting only |

**Live Integration Status:** **0 / 11 SOURCES VERIFIED LIVE IN PRODUCTION**

---

## 3. Category 3: END-TO-END PIPELINE RESULTS

| Ingestion Step | Implementation Status | Verification Evidence |
|---|---|---|
| Source Network Call | ⚠️ Partial (Mocks in unit tests; live calls fail or unprobed) | Probes in Phase 6 |
| Evidence Normalization | ✅ Implemented in memory (`EvidenceNormalizer`) | Unit tests pass |
| Provenance Signature | ✅ Implemented in memory (`ProvenanceTracker`) | Unit tests pass |
| Database Persistence | ❌ **NOT IMPLEMENTED** | Zero rows written to `intelligence_evidence` |
| Evidence Graph Linking | ❌ **NOT IMPLEMENTED** | `core/intelligence_engine.py` receives zero data |
| Product Intelligence UI | ❌ **NOT IMPLEMENTED** | UI displays only pre-existing database records |
| Decision Ledger Audit | ❌ **NOT IMPLEMENTED** | Decisions remain untouched by new sources |

**End-to-End Pipeline Status:** **FAILED (DISCONNECTED AT DATABASE BOUNDARY)**
