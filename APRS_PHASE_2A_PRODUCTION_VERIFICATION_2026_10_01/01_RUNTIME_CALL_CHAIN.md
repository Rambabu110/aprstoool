# 01 — RUNTIME CALL CHAIN AUDIT

**Audit Date:** 2026-10-01  
**Phase:** APRS V8 — Phase 2A Production Readiness Verification  
**Auditor Roles:** Senior Software Architect + Forensic QA Lead + Production Integration Auditor  
**Verdict:** **RUNTIME DISCONNECTED**  

---

## 1. Executive Summary

A forensic tracing of the actual APRS production runtime was conducted across:
- `web/app.py` (Streamlit Web Dashboard)
- `core/background_daemon.py` (Autonomous Background Research Loop)
- `core/orchestrator.py` (`AutonomousProductResearchOrchestrator`)
- `core/intelligence_engine.py` (`AutonomousIntelligenceEngine`)

The audit investigated whether a normal APRS research operation triggers `core.research_sources.registry` and specifically `GoogleTrendsAdapter` or `GDELTResearchAdapter`.

**Finding:**  
Neither `web/app.py`, `core/background_daemon.py`, `core/orchestrator.py`, nor `core/intelligence_engine.py` imports or invokes `ResearchSourceRegistry`, `GoogleTrendsAdapter`, or `GDELTResearchAdapter`.  
The newly created adapter subsystem in `core/research_sources/` exists as a self-contained module that is exercised solely by test suites (`tests/test_phase2a_real_sources.py` and `tests/test_research_sources.py`).

Per the explicit audit instruction:
> "If the runtime does NOT call these adapters, report: RUNTIME DISCONNECTED. Do not label the system END_TO_END."

**Official Designation:** **`RUNTIME DISCONNECTED`**

---

## 2. Actual Call Path Analysis

### A. Current APRS Autonomous Background Research Loop
Starting from `core/background_daemon.py`:

```
APR runtime entry: core/background_daemon.py:AutonomousDaemon.run()
→ _run_autonomous_loop()
  → _execute_research_cycle()
    → core.database.start_research_run()
    → orch.discover_and_evaluate_products(region, category)
      → AmazonLiveScraper.search() [via curl_cffi]
      → orch._run_gate_1_signal_discovery(asin) [via KeepaAPIClient]
      → ComprehensiveUnitEconomics.calculate_landed_economics()
      → record_product_evaluation()
      → init_product_gates()
      → update_gate_status()
    → universal_scraper.scrape_all_marketplaces()
    → AutonomousIntelligenceEngine.run_full_product_intelligence(pid)
      → get_product_raw_data()
      → evaluate_scorecard()
      → evaluate_kill_switch()
      → save_product_intelligence()
      → record_intelligence_evidence() [Hardcoded categories: DEMAND, TREND, DEFECTS, SOURCING, ECONOMICS]
    → core.database.complete_research_run()
```

**Connection to `core.research_sources.registry`:** **NONE.**

---

### B. Current APRS Web UI Evaluation Flow
Starting from `web/app.py`:

```
APR runtime entry: web/app.py:tab_intelligence (Action Bar Button: "⚡ Evaluate All Products")
→ AutonomousIntelligenceEngine.run_full_product_intelligence(pid)
  → get_product_raw_data(pid)
  → evaluate_scorecard()
  → evaluate_kill_switch()
  → calculate_counterfactual_economics()
  → save_product_intelligence()
  → record_intelligence_evidence(product_id, signal_type="DEMAND", source="Marketplace Telemetry")
  → record_intelligence_evidence(product_id, signal_type="TREND", source="Trend Scout / Scraper")
  → record_intelligence_evidence(product_id, signal_type="DEFECTS", source="Customer Review Mining")
  → record_intelligence_evidence(product_id, signal_type="SOURCING", source="Supplier Catalog / RFQ")
  → record_intelligence_evidence(product_id, signal_type="ECONOMICS", source="Comprehensive 15-Factor Economics")
  → run_war_room_2(pid, dossier)
```

**Connection to `core.research_sources.registry`:** **NONE.**

---

### C. Live Niche Scan in `web/app.py`
Starting from `web/app.py` line 1821 (`scan_query`):

```
APR runtime entry: web/app.py:tab_research ("Scan Niche")
→ tools.google_trends_realtime.get_trends_engine() [Direct legacy tool call, NOT through adapter]
  → _trends.analyze_product_trend(scan_query)
→ live_items = AmazonLiveScraper.search()
→ orch._run_gate_1_signal_discovery()
→ ComprehensiveUnitEconomics.calculate_landed_economics()
→ record_product_evaluation()
```

**Connection to `core.research_sources.registry`:** **NONE.**  
**Connection to `GoogleTrendsAdapter`:** **NONE.**  
**Connection to `GDELTResearchAdapter`:** **NONE.**

---

## 3. Required Call Chain Compliance

### Google Trends Required Chain:
```
APR runtime entry
→ function
→ function
→ function
→ research registry
→ Google Trends
→ normalization
→ persistence
```
**Actual Result:** **DISCONNECTED.** The runtime entry calls legacy tools or internal methods, completely bypassing `ResearchSourceRegistry`.

### GDELT Required Chain:
```
APR runtime entry
→ function
→ function
→ function
→ research registry
→ GDELT
→ normalization
→ persistence
```
**Actual Result:** **DISCONNECTED.** GDELT is nowhere referenced or called in any runtime entrypoint (`web/app.py`, `core/background_daemon.py`, `core/orchestrator.py`).

---

## 4. Architectural Summary

| Runtime Component | Calls `ResearchSourceRegistry`? | Calls `GoogleTrendsAdapter`? | Calls `GDELTResearchAdapter`? |
| :--- | :--- | :--- | :--- |
| `web/app.py` | **NO** | **NO** | **NO** |
| `core/background_daemon.py` | **NO** | **NO** | **NO** |
| `core/orchestrator.py` | **NO** | **NO** | **NO** |
| `core/intelligence_engine.py` | **NO** | **NO** | **NO** |
| `tests/test_phase2a_real_sources.py` | **YES** | **YES** | **YES** |
| `tests/test_research_sources.py` | **YES** | **YES** | **YES** |

The adapter subsystem in `core/research_sources/` was built as a clean isolated service layer, but was never wired into the host runtime's execution pipelines.
