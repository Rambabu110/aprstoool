# 13 — DATA PROVENANCE & ANTI-HALLUCINATION AUDIT
**Date:** 2026-10-01  
**Target:** APRS V8 Evidence Layer  

---

## 1. Provenance Integrity Architecture

Every evidence record produced by any research source must pass through `ProvenanceTracker.create_provenance()` before entering the APRS decision pipeline.

### Required Provenance Metadata Stamped on Every Record:
1. `source`: Provider identifier (e.g. `google_trends`, `scavio_mcp`)
2. `retrieval_method`: Network mechanism (`MCP_JSONRPC`, `API_REST`, `SCRAPER_PROXY`, `PUBLIC_FEED_JSON`)
3. `source_url`: Canonical public URL of the source observation
4. `retrieved_at`: UTC timestamp of ingestion
5. `payload_sha256`: SHA-256 cryptographic digest of the raw response
6. `proxy_used`: Boolean indicating whether proxy routing was engaged
7. `adapter_version`: Version of the extracting adapter
8. `schema_version`: Data contract schema version
9. `tamper_sig`: 16-character cryptographic signature verifying that origin, method, and payload remain unmodified

---

## 2. Anti-Hallucination Boundaries Enforced

In strict accordance with the **Critical Anti-Hallucination Rule**:

```
OBSERVED SIGNAL  → External provider raw data (trend score, view count, review count)
      ↓
   ESTIMATE      → Derived calculation from a known heuristic/model
      ↓
  INFERENCE      → AI or rule-based synthesis across multiple observed signals
      ↓
  PREDICTION     → Forward-looking forecast (demand, seasonality)
      ↓
   DECISION      → Operational verdict (gate pass, kill-switch, RFQ launch)
```

### Prohibited Conversions Hard-Coded in `normalizer.py`:
- ❌ **Trend signals are NOT sales:** Google Trends or TrendsMCP scores cannot be written into sales columns.
- ❌ **Reddit complaints are NOT market demand:** Negative posts are categorized exclusively as `CUSTOMER_PAIN`.
- ❌ **YouTube views are NOT purchase intent:** View counts are categorized as `ENGAGEMENT`.
- ❌ **Amazon rank is NOT exact sales volume:** Rank is categorized as `COMPETITION` or `DEMAND` index.
- ❌ **Proxy data is NOT verified sales:** Decodo proxy is recorded strictly as transport infrastructure.
- ❌ **NIM text is NOT observed evidence:** NIM outputs are classified as `INFERENCE` or `ESTIMATE`, never external market evidence.

---

## 3. Provenance Verification Audit Results

- Tested via `tests/test_research_sources.py::TestNormalizationAndProvenance`
- Tamper detection test (`test_provenance_tamper_detection`): **PASS** (modifying source or payload invalidates record)
- Evidence classification downgrade test (`test_external_source_cannot_claim_decision_evidence_type`): **PASS** (illegal claim downgraded to ESTIMATE)
- Provenance completeness: **100% of generated records retain full audit metadata**
