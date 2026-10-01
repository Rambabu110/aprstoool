# APRS FORENSIC REMEDIATION — 00 BASELINE
**Date:** 2026-10-01  
**Time:** 20:07 IST  
**Engineer:** Antigravity Senior Architect

---

## Git State
- **Branch:** `Production`
- **Modified files (staged/unstaged):**
  - `M core/background_daemon.py`
  - `M core/database.py`
  - `M core/economics_engine.py`
  - `M tools/seed_market_data.py`
  - `M web/app.py`
- **Untracked (new files, never committed):**
  - `APRS_E2E_AUDIT/`
  - `core/calibration_engine.py`
  - `core/intelligence_engine.py`
  - `core/learning_engine.py`
  - `core/observation_scheduler.py`
  - `core/outcome_adapters/`
  - `core/outcome_ingestion.py`
  - `core/prediction_reality_report.py`
  - `tests/test_aprs_v7_intelligence.py`
  - `tests/test_aprs_v8_calibration.py`
  - `tests/test_aprs_v8_learning_engine.py`
  - `tests/test_aprs_v8_manual_csv.py`
  - `tests/test_aprs_v8_observation_scheduler.py`
  - `tests/test_aprs_v8_outcome_adapters.py`
  - `tests/test_aprs_v8_outcomes.py`
  - `tests/test_aprs_v8_phase1.py`
  - `tests/test_aprs_v8_phase5_1_forensics.py`
  - `tests/test_aprs_v8_prediction_reality_reporting.py`
- **NO GIT COMMIT. NO GIT PUSH.**

---

## Python Environment
- **Python Version:** 3.14.7
- **Venv:** `.venv/` present in project root
- **Key Dependencies:** streamlit, sqlite3, pydantic, requests, pytest, playwright

---

## Test Suite Baseline
- **Total Tests Collected:** 357
- **Baseline Result:** **357 PASSED** in 99.96s (0:01:39)
- **Exit Code:** 0 (SUCCESS)
- **Failures:** 0
- **Errors:** 0

---

## Database State
- **Database Path:** `d:\tools\APRS\aprs_v6_pro.db`
- **Tables (38 total):**

| Table | Count |
|-------|-------|
| ai_supervisor_logs | (populated) |
| ai_task_improvements | (populated) |
| arbiter_decision_log | (populated) |
| daily_snapshots | (populated) |
| data_conflicts | (populated) |
| decision_ledger | (populated) |
| defect_clusters | (populated) |
| discovered_sources | (populated) |
| dynamic_niches | (populated) |
| dynamic_seed_keywords | (populated) |
| economics_assessments | (populated) |
| intelligence_evidence | (populated) |
| intelligence_timeline | (populated) |
| launchpad_items | (populated) |
| learning_bias_summaries | (populated) |
| learning_recommendations | (populated) |
| marketplace_config | (populated) |
| master_products | (populated) |
| meeting_audit_log | (populated) |
| multi_platform_listings | (populated) |
| negative_findings | (populated) |
| opportunity_alerts | (populated) |
| outcome_corrections_log | (populated) |
| prediction_calibrations | (populated) |
| product_gate_progress | (populated) |
| product_intelligence | (populated) |
| product_outcomes | (populated) |
| product_suppliers | (populated) |
| product_watchlist | (populated) |
| research_runs | (populated) |
| scraped_listings | (populated) |
| scraper_validations | (populated) |
| source_health | (populated) |
| sqlite_sequence | (populated) |
| swarm_audit_log | (populated) |
| trend_signals | (populated) |
| users | (populated) |

---

## Streamlit Status
- **Server:** Running on port 8501
- **URL:** http://localhost:8501
- **Title:** "APRS V6 — Autonomous E-Commerce Swarm"
- **Nav tabs verified:** 12/12 PASS (live browser audit)
- **PI subtabs verified:** 5/5 PASS (live browser audit)

---

## Known Active Integrations
| Integration | Status | Notes |
|-------------|--------|-------|
| NIM API Keys (3 keys) | DEGRADED | Keys configured as `nvapi-YUxOBz4Du4Pj11...` truncated. Quota likely exhausted. |
| Keepa API | NOT_CONFIGURED | `KEEPA_API_KEY=xxx` placeholder in `.env` |
| Supabase | CONFIGURED | URL + anon key present |
| Razorpay | NOT_CONFIGURED | `rzp_live_xxx` placeholder |
| SQLite DB | ACTIVE | Primary data store |

---

## Known Errors Before Fix
1. **CONFIRMED BUG — `background_daemon.py:306`:** `match.get("classification")` called on `Tuple[str, float]` return from `evaluate_match_confidence()` → `AttributeError: 'tuple' object has no attribute 'get'`
2. **CONFIRMED BUG — `orchestrator.py:675`:** Same pattern — `match.get("classification")` on tuple.
3. **NIM:** `NIMClusterExhausted` raised in production — likely quota, not code bug.
4. **Keepa:** UI reads `keepa_price_stability` from seeded DB data. No live Keepa API calls.

---

## Current Source Layer
- No `core/research_sources/` directory exists.
- No MCP integrations configured.
- External research done via scraping only (`tools/keepa_api_client.py`, `tools/browser-use/`).
