# 02 — GOOGLE TRENDS FORENSIC INTEGRATION REPORT

**Audit Date:** 2026-10-01  
**Phase:** APRS V8 — Phase 2A (Real Source Integration)  
**Target:** Google Trends Adapter (`core/research_sources/google_trends.py`)  
**Status:** FULLY INTEGRATED & FORENSICALLY HARDENED  

---

## 1. Executive Summary & Objective

In the previous Stage 2 audit, `core/research_sources/google_trends.py` was identified as having critical architectural defects:
1. Broken import path attempting to load `from tools.google_trends import ...` which did not exist.
2. Silent fallback to hardcoded `50.0` synthetic estimate on any error or 429 rate limit.
3. Lack of connection to real `pytrends` backend.
4. Total detachment from the real APRS data pipeline and SQLite storage.

Phase 2A completely overhauled this adapter to connect to the verified production `tools.google_trends_realtime.RealGoogleTrendsEngine`, enforce zero-synthetic emission, catch IP rate limiting honestly, and persist true observed evidence.

---

## 2. Forensic Code Inspection & Key Changes

### A. Real Backend Connection
- Replaced the non-existent import with `from tools.google_trends_realtime import get_trends_engine`.
- Implemented lazy loading in `_get_engine()` with defensive error classification:
  ```python
  def _get_engine(self):
      if self._engine is None:
          try:
              from tools.google_trends_realtime import get_trends_engine
              self._engine = get_trends_engine()
          except ImportError as ie:
              raise RuntimeError(f"DEPENDENCY_ERROR: pytrends or tools.google_trends_realtime unavailable: {ie}")
      return self._engine
  ```

### B. Elimination of Hardcoded 50.0 Fallback
- Completely eliminated any fallback assigning `50.0` or fabricating fake demand signals.
- If Google Trends fails, returns `[]` and records the exact network error, rate limit, or timeout.

### C. Synthetic Suggest Interception (Anti-Hallucination Gate)
The underlying `RealGoogleTrendsEngine` contains an internal mechanism (`_fallback_interest_from_suggest`) which generates synthetic sinusoidal curves when pytrends gets 429'd.
To enforce **CRITICAL OPERATING RULE 3 (Zero Synthetic Data)**, we added an explicit authenticity gate:
```python
source_engine = trend_data.get("source", "")
if source_engine != "pytrends_realtime":
    logger.warning(
        f"Google Trends direct call did not return real pytrends data (source={source_engine}). "
        "Rejecting synthetic estimate to preserve data integrity."
    )
    raise RuntimeError(f"UNAVAILABLE: Google Trends direct data unavailable (returned {source_engine})")
```
When pytrends gets rate-limited and falls back to suggest, our adapter detects `source == 'google_suggest_live'`, immediately rejects the synthetic data, marks health as `DEGRADED`, and returns `[]`.

### D. Multi-Signal Extraction
When genuine observed data is returned:
1. **Primary Demand Signal (`SignalType.DEMAND`)**:
   - Unit: `index_0_100` (e.g. 55.0/100).
   - Provenance: `PYTRENDS_REALTIME`, claimed type `OBSERVED_SIGNAL`.
   - Raw payload preserved: `current_interest`, `avg_interest_30d`, `velocity_pct`, `peak_interest`, `peak_date`.
2. **Breakout Keyword Queries (`SignalType.KEYWORD`)**:
   - Queries retrieved from `get_related_queries(query, geo=geo)`.
   - Unit: `breakout_pct`.
   - Confidence: 0.80.

---

## 3. Real Live Execution Verification

1. **Observed Live Call (Unconstrained query)**:
   - Query: `air purifier`, Geo: `IN`.
   - Observed Result: `current_interest = 55.0/100`, direction: `STABLE`.
   - Breakout keywords: `air purifier filter`, `philips air purifier`, `mi air purifier`.
2. **Observed Live 429 Handling**:
   - Query: `yoga mat` (when Google blocked IP with `/sorry/index` 429).
   - Interception: Rejected `google_suggest_live` sinusoidal 99.
   - Result: 0 records returned, error logged as `UNAVAILABLE: Google Trends direct data unavailable (returned google_suggest_live)`.
   - Adapter health status transitioned to `DEGRADED (1 errors)`, `is_healthy=False`.

---

## 4. Test Coverage

Tested across unit, integration, and negative test suites in `tests/test_phase2a_real_sources.py`:
- `test_google_trends_mock_mode`: PASSED
- `test_google_trends_empty_query_raises_value_error`: PASSED
- `test_google_trends_rejects_synthetic_suggest_fallback`: PASSED
- `test_google_trends_handles_rate_limit_429`: PASSED
- `test_google_trends_handles_timeout`: PASSED
- `test_google_trends_no_hardcoded_50_fallback`: PASSED

---

## 5. Forensic Verdict

**Classification:** `END_TO_END`  
Google Trends is fully integrated with verified live data retrieval, strict synthetic fallback rejection, error isolation, tamper-evident SHA-256 provenance generation, and SQLite persistence.
