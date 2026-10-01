# 01 — RESEARCH SOURCE INVENTORY & CLASSIFICATION AUDIT
**Date:** 2026-10-01  
**Auditor:** Antigravity Forensic QA & Systems Architecture Team  
**Scope:** `core/research_sources/`  

---

## 1. Source-by-Source Technical Inventory

### 1. Trends-MCP
- **SOURCE:** `trends_mcp`
- **FILE:** `core/research_sources/trends_mcp.py`
- **CLASS:** `TrendsMCPAdapter`
- **STATUS:** `ONLINE` (Configured with credentials)
- **REAL NETWORK CALL:** Implemented (`requests.get` to `https://api.trendsmcp.com/v1/signals`)
- **AUTH REQUIRED:** YES (`TRENDSMCP_API_KEY`)
- **FREE/PUBLIC:** Free Tier / Commercial Token
- **FIXTURE ONLY:** Unit tests run via mock fixtures; live network call untested in production
- **UNIT TESTED:** YES (`test_research_sources.py` — 4 tests)
- **INTEGRATED INTO REGISTRY:** YES (`ResearchSourceRegistry`)
- **INTEGRATED INTO APPLICATION:** **NO** (Not imported or invoked by daemon, orchestrator, or UI)
- **INTEGRATED INTO EVIDENCE STORAGE:** **NO** (Zero rows in production SQLite database)
- **INTEGRATED INTO INTELLIGENCE:** **NO** (Does not feed into `ProductIntelligenceEngine`)
- **END-TO-END VERIFIED:** **NO** (Verified only at unit test / mock fixture level)
- **CLASSIFICATION:** **D. CONFIGURED BUT NOT VERIFIED LIVE**

---

### 2. Scavio MCP
- **SOURCE:** `scavio_mcp`
- **FILE:** `core/research_sources/scavio.py`
- **CLASS:** `ScavioMCPAdapter`
- **STATUS:** `ONLINE` (Configured with credentials)
- **REAL NETWORK CALL:** Implemented (`requests.post` to `https://api.scavio.ai/v1/research`)
- **AUTH REQUIRED:** YES (`SCAVIO_API_KEY`)
- **FREE/PUBLIC:** Free Tier Quota
- **FIXTURE ONLY:** Unit tests run via mock fixtures
- **UNIT TESTED:** YES (`test_research_sources.py` — 3 tests)
- **INTEGRATED INTO REGISTRY:** YES (`ResearchSourceRegistry`)
- **INTEGRATED INTO APPLICATION:** **NO**
- **INTEGRATED INTO EVIDENCE STORAGE:** **NO**
- **INTEGRATED INTO INTELLIGENCE:** **NO**
- **END-TO-END VERIFIED:** **NO**
- **CLASSIFICATION:** **D. CONFIGURED BUT NOT VERIFIED LIVE**

---

### 3. Amazon India
- **SOURCE:** `amazon_india`
- **FILE:** `core/research_sources/amazon_india.py`
- **CLASS:** `AmazonIndiaAdapter`
- **STATUS:** `ONLINE` (Configured with Decodo proxy credentials)
- **REAL NETWORK CALL:** Implemented (`requests.get` to `https://www.amazon.in/s?k=...` with BeautifulSoup)
- **AUTH REQUIRED:** YES for proxy (`DECODO_AUTH`), Public for Amazon.in HTML
- **FREE/PUBLIC:** Hybrid (Scraping infrastructure requires proxy budget)
- **FIXTURE ONLY:** Unit tests run via mock fixtures
- **UNIT TESTED:** YES (`test_research_sources.py` — 2 tests)
- **INTEGRATED INTO REGISTRY:** YES (`ResearchSourceRegistry`)
- **INTEGRATED INTO APPLICATION:** **NO**
- **INTEGRATED INTO EVIDENCE STORAGE:** **NO**
- **INTEGRATED INTO INTELLIGENCE:** **NO**
- **END-TO-END VERIFIED:** **NO**
- **CLASSIFICATION:** **D. CONFIGURED BUT NOT VERIFIED LIVE**

---

### 4. Google Trends
- **SOURCE:** `google_trends`
- **FILE:** `core/research_sources/google_trends.py`
- **CLASS:** `GoogleTrendsAdapter`
- **STATUS:** `DEGRADED_SILENT_FALLBACK`
- **REAL NETWORK CALL:** Attempted, but import statement `from tools.google_trends_realtime import get_realtime_trends` throws `ImportError` on live calls, triggering a silent fallback that emits a static `50.0` estimate
- **AUTH REQUIRED:** NO
- **FREE/PUBLIC:** YES (Public Google Trends)
- **FIXTURE ONLY:** Unit tests pass due to fixture bypass; live call triggers static fallback
- **UNIT TESTED:** YES (`test_research_sources.py` — 3 tests)
- **INTEGRATED INTO REGISTRY:** YES (`ResearchSourceRegistry`)
- **INTEGRATED INTO APPLICATION:** **NO**
- **INTEGRATED INTO EVIDENCE STORAGE:** **NO**
- **INTEGRATED INTO INTELLIGENCE:** **NO**
- **END-TO-END VERIFIED:** **NO**
- **CLASSIFICATION:** **F. STUB / BROKEN LIVE INTEGRATION**

---

### 5. Reddit
- **SOURCE:** `reddit`
- **FILE:** `core/research_sources/reddit.py`
- **CLASS:** `RedditResearchAdapter`
- **STATUS:** `BLOCKED_LIVE_403`
- **REAL NETWORK CALL:** Implemented (`requests.get` to `https://www.reddit.com/r/all/search.json`), but live requests return HTTP 403 Forbidden without OAuth credentials. Adapter silently drops non-200 responses and returns `[]`.
- **AUTH REQUIRED:** Publicly unauthenticated fails (requires Reddit OAuth)
- **FREE/PUBLIC:** Free API but requires registered script application
- **FIXTURE ONLY:** Unit tests pass with `mock_response`
- **UNIT TESTED:** YES (`test_research_sources.py` — 2 tests)
- **INTEGRATED INTO REGISTRY:** YES (`ResearchSourceRegistry`)
- **INTEGRATED INTO APPLICATION:** **NO**
- **INTEGRATED INTO EVIDENCE STORAGE:** **NO**
- **INTEGRATED INTO INTELLIGENCE:** **NO**
- **END-TO-END VERIFIED:** **NO**
- **CLASSIFICATION:** **E. BLOCKED (LIVE HTTP 403)**

---

### 6. YouTube
- **SOURCE:** `youtube`
- **FILE:** `core/research_sources/youtube.py`
- **CLASS:** `YouTubeResearchAdapter`
- **STATUS:** `ONLINE_MOCK_FALLBACK`
- **REAL NETWORK CALL:** Implemented (`requests.get` to Google API v3), but falls back to synthetic estimate when `YOUTUBE_API_KEY` is not present
- **AUTH REQUIRED:** YES for live (`YOUTUBE_API_KEY`), NO for synthetic fallback
- **FREE/PUBLIC:** 10,000 units/day free tier
- **FIXTURE ONLY:** Tested via mock payload
- **UNIT TESTED:** YES (`test_research_sources.py` — 2 tests)
- **INTEGRATED INTO REGISTRY:** YES (`ResearchSourceRegistry`)
- **INTEGRATED INTO APPLICATION:** **NO**
- **INTEGRATED INTO EVIDENCE STORAGE:** **NO**
- **INTEGRATED INTO INTELLIGENCE:** **NO**
- **END-TO-END VERIFIED:** **NO**
- **CLASSIFICATION:** **B. ADAPTER ONLY (SYNTHETIC FALLBACK ACTIVE)**

---

### 7. GDELT Project
- **SOURCE:** `gdelt`
- **FILE:** `core/research_sources/gdelt.py`
- **CLASS:** `GDELTResearchAdapter`
- **STATUS:** `LIVE_TIMEOUT`
- **REAL NETWORK CALL:** Implemented (`requests.get` to `api.gdeltproject.org`), but live requests timed out (>8.0s read timeout) from local execution environment
- **AUTH REQUIRED:** NO
- **FREE/PUBLIC:** YES (Public open data)
- **FIXTURE ONLY:** Unit tests pass with mock fixtures; live request timed out
- **UNIT TESTED:** YES (`test_research_sources.py` — 2 tests)
- **INTEGRATED INTO REGISTRY:** YES (`ResearchSourceRegistry`)
- **INTEGRATED INTO APPLICATION:** **NO**
- **INTEGRATED INTO EVIDENCE STORAGE:** **NO**
- **INTEGRATED INTO INTELLIGENCE:** **NO**
- **END-TO-END VERIFIED:** **NO**
- **CLASSIFICATION:** **B. ADAPTER ONLY (LIVE TIMEOUT OBSERVED)**

---

### 8. TrendWatch
- **SOURCE:** `trendwatch`
- **FILE:** `core/research_sources/trendwatch.py`
- **CLASS:** `TrendWatchAdapter`
- **STATUS:** `INTERNAL_HEURISTIC`
- **REAL NETWORK CALL:** NO (Internal velocity calculation / simulation)
- **AUTH REQUIRED:** NO
- **FREE/PUBLIC:** YES (Internal compute)
- **FIXTURE ONLY:** Generates synthetic acceleration vectors
- **UNIT TESTED:** YES (`test_research_sources.py` — 2 tests)
- **INTEGRATED INTO REGISTRY:** YES (`ResearchSourceRegistry`)
- **INTEGRATED INTO APPLICATION:** **NO**
- **INTEGRATED INTO EVIDENCE STORAGE:** **NO**
- **INTEGRATED INTO INTELLIGENCE:** **NO**
- **END-TO-END VERIFIED:** **NO**
- **CLASSIFICATION:** **F. STUB / INTERNAL HEURISTIC**

---

### 9. TikTok
- **SOURCE:** `tiktok`
- **FILE:** `core/research_sources/tiktok.py`
- **CLASS:** `TikTokResearchAdapter`
- **STATUS:** `INTERNAL_HEURISTIC`
- **REAL NETWORK CALL:** NO (Emits simulated Creative Center payload)
- **AUTH REQUIRED:** NO
- **FREE/PUBLIC:** Simulated public feed
- **FIXTURE ONLY:** Generates synthetic hashtag view counts
- **UNIT TESTED:** YES (`test_research_sources.py` — 2 tests)
- **INTEGRATED INTO REGISTRY:** YES (`ResearchSourceRegistry`)
- **INTEGRATED INTO APPLICATION:** **NO**
- **INTEGRATED INTO EVIDENCE STORAGE:** **NO**
- **INTEGRATED INTO INTELLIGENCE:** **NO**
- **END-TO-END VERIFIED:** **NO**
- **CLASSIFICATION:** **F. STUB / HEURISTIC**

---

### 10. RivalSearch
- **SOURCE:** `rivalsearch`
- **FILE:** `core/research_sources/rivalsearch.py`
- **CLASS:** `RivalSearchAdapter`
- **STATUS:** `INTERNAL_HEURISTIC`
- **REAL NETWORK CALL:** NO (Emits simulated competitor listings)
- **AUTH REQUIRED:** NO
- **FREE/PUBLIC:** Simulated SERP
- **FIXTURE ONLY:** Generates mock competitor records
- **UNIT TESTED:** YES (`test_research_sources.py` — 2 tests)
- **INTEGRATED INTO REGISTRY:** YES (`ResearchSourceRegistry`)
- **INTEGRATED INTO APPLICATION:** **NO**
- **INTEGRATED INTO EVIDENCE STORAGE:** **NO**
- **INTEGRATED INTO INTELLIGENCE:** **NO**
- **END-TO-END VERIFIED:** **NO**
- **CLASSIFICATION:** **F. STUB / HEURISTIC**

---

### 11. TrendScope
- **SOURCE:** `trendscope`
- **FILE:** `core/research_sources/trendscope.py`
- **CLASS:** `TrendScopeAdapter`
- **STATUS:** `INTERNAL_HEURISTIC`
- **REAL NETWORK CALL:** NO (Composite weighting heuristic)
- **AUTH REQUIRED:** NO
- **FREE/PUBLIC:** YES (Internal compute)
- **FIXTURE ONLY:** Generates synthetic composite indices
- **UNIT TESTED:** YES (`test_research_sources.py` — 2 tests)
- **INTEGRATED INTO REGISTRY:** YES (`ResearchSourceRegistry`)
- **INTEGRATED INTO APPLICATION:** **NO**
- **INTEGRATED INTO EVIDENCE STORAGE:** **NO**
- **INTEGRATED INTO INTELLIGENCE:** **NO**
- **END-TO-END VERIFIED:** **NO**
- **CLASSIFICATION:** **F. STUB / HEURISTIC**

---

## 2. Summary Classification Distribution

| Classification | Count | Sources |
|---|---|---|
| **A. FULLY END-TO-END** | **0** | None |
| **B. ADAPTER ONLY** | **2** | `youtube`, `gdelt` |
| **C. UNIT-TEST ONLY** | **0** | (All adapters belong to B, D, E, or F) |
| **D. CONFIGURED BUT NOT VERIFIED LIVE** | **3** | `trends_mcp`, `scavio_mcp`, `amazon_india` |
| **E. BLOCKED** | **1** | `reddit` (Live HTTP 403 Forbidden without OAuth) |
| **F. STUB / HEURISTIC** | **5** | `google_trends` (broken import fallback), `trendwatch`, `tiktok`, `rivalsearch`, `trendscope` |
| **G. DUPLICATE** | **0** | Distinct adapter files, but conceptually overlaps with `trend_aggregator.py` |
| **H. NOT ACTUALLY IMPLEMENTED** | **0** | Code files exist and pass unit tests |
