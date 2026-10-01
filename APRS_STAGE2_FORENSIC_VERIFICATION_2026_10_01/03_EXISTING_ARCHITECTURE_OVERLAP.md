# 03 — EXISTING RESEARCH ARCHITECTURE & OVERLAP AUDIT
**Date:** 2026-10-01  
**Auditor:** Antigravity Architecture Review  

---

## 1. Existing Pre-Stage-2 Research Subsystems in APRS

Before the creation of `core/research_sources/`, APRS possessed an existing, active research infrastructure:

| Component | File Path | Class / Interface | Target Storage Table | Invoked By |
|---|---|---|---|---|
| **Trend Scout** | `tools/trend_scout/trend_aggregator.py` | `OpenWebTrendScout` | `trend_signals`, `discovered_sources` | `core/background_daemon.py:127` |
| **Realtime Google Trends** | `tools/google_trends_realtime.py` | `RealGoogleTrendsEngine` | In-memory / Streamlit UI | `web/app.py:tab_trending` |
| **Pytrends Engine** | `tools/google_trends_engine.py` | `GoogleTrendsEngine` | In-memory / Discovery engine | `tools/discovery_engine.py` |
| **AI Discovery Engine** | `tools/ai_discovery_engine.py` | `AIDiscoveryEngine` | `master_products`, `discovered_sources` | Daemon scan loops |
| **Legacy Adapter Contract** | `tools/adapters/base_adapter.py` | `BaseSourceAdapter`, `SourceHealth` | Telemetry logs | `tools/trend_scout/trend_aggregator.py` |

---

## 2. Architectural Duality & Overlap Analysis

The newly created `core/research_sources/` introduces a parallel abstraction layer rather than extending the existing one:

### 1. Dual `SourceHealth` Models:
- **Existing:** `tools/adapters/base_adapter.py:SourceHealth` (Pydantic model used by `OpenWebTrendScout`)
- **New:** `core/research_sources/base.py:SourceHealth` (Pydantic model used by `ResearchSourceRegistry`)
- *Overlap:* Two distinct Pydantic models with overlapping telemetry fields representing the same conceptual entity.

### 2. Dual Base Adapter Contracts:
- **Existing:** `tools/adapters/base_adapter.py:BaseSourceAdapter` (methods: `record_success`, `record_error`, `health_check`)
- **New:** `core/research_sources/base.py:BaseResearchSourceAdapter` (methods: `fetch_signals`, `health_check`, `record_success`, `record_error`)

### 3. Dual Trend Scanners:
- **Existing:** `OpenWebTrendScout` scans Reddit, Google Trends, and Meta Ads, persisting directly to `trend_signals` table via `core.database.record_trend_signal`.
- **New:** `core/research_sources/` has standalone `RedditResearchAdapter`, `GoogleTrendsAdapter`, and `TrendsMCPAdapter`, none of which write to `trend_signals` or `intelligence_evidence`.

---

## 3. Forensic Evaluation

- **Status:** **PARALLEL / UNINTEGRATED SUBSYSTEM**
- The new `core/research_sources/` does not replace, inherit from, or delegate to the existing `tools/trend_scout` or `tools/adapters` modules.
- It exists side-by-side as a disconnected secondary library.
- In strict adherence to the **STOP ALL NEW FEATURE IMPLEMENTATION** rule, no consolidation, deletion, or refactoring will be performed during this audit.
