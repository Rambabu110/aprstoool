# 02 — REAL DATA FLOW & CALL SITE TRACE
**Date:** 2026-10-01  
**Auditor:** Antigravity Forensic QA Team  
**Scope:** Repository-wide Code Search for Ingestion Call Sites  

---

## 1. Expected vs. Actual Data Flow

### Theoretical Target Architecture:
```
SOURCE
  ↓
ADAPTER (core/research_sources/*.py)
  ↓
NORMALIZER (core/research_sources/normalizer.py)
  ↓
PROVENANCE (core/research_sources/provenance.py)
  ↓
DATABASE (data/research_engine.db -> intelligence_evidence, source_health, data_conflicts)
  ↓
EVIDENCE GRAPH (core/intelligence_engine.py)
  ↓
PRODUCT INTELLIGENCE (web/app.py:tab_intelligence)
  ↓
UI / DECISION (Opportunity Scorecard, Kill Switch, Decision Ledger)
```

---

## 2. Repository-Wide Call-Site Search Results

A rigorous AST and text search was conducted across the entire repository for references to `core.research_sources` and its member classes (`ResearchSourceRegistry`, `TrendsMCPAdapter`, `EvidenceNormalizer`, etc.):

```powershell
ripgrep "core.research_sources" d:\tools\APRS
```

### Findings:
1. **`core/background_daemon.py`:** **ZERO REFERENCES**.
   - Background daemon imports `from tools.trend_scout.trend_aggregator import OpenWebTrendScout` (Line 127).
   - It does NOT call `ResearchSourceRegistry` or any new research source adapter.
2. **`core/orchestrator.py`:** **ZERO REFERENCES**.
3. **`core/intelligence_engine.py`:** **ZERO REFERENCES**.
   - Builds evidence graphs by querying `intelligence_evidence` populated by previous scraper runs, not from `core.research_sources`.
4. **`web/app.py`:** **ZERO REFERENCES**.
   - UI navigation and Product Intelligence subtabs query existing tables in SQLite, completely unaware of `core.research_sources`.
5. **`tests/test_research_sources.py`:** **ALL CALL SITES RESIDE HERE**.

---

## 3. Disconnection Point

```
SOURCE ──► ADAPTER ──► NORMALIZER ──► PROVENANCE ──► REGISTRY
                                                        │
                                    ┌───────────────────┴───────────────────┐
                                    │                                       │
                         [UNIT TESTS ONLY]                                  ▼
                         (PASS with mocks)                       [WALL: DISCONNECTED]
                                                                            │
                                                                            X
                                                                            ▼
                                                                        DATABASE
                                                                            │
                                                                            X
                                                                            ▼
                                                                     EVIDENCE GRAPH
                                                                            │
                                                                            X
                                                                            ▼
                                                                   PRODUCT INTELLIGENCE
```

### Conclusion:
The `core/research_sources/` subsystem is an **isolated adapter library**. It terminates at the registry level. No code in APRS's active runtime invokes it, feeds it live products, or persists its output to the production database.
