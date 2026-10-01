# 08 — PRODUCT INTELLIGENCE PROOF REPORT

**Audit Date:** 2026-10-01  
**Phase:** APRS V8 — Phase 2A Production Readiness Verification  
**Auditor Roles:** Senior Software Architect + Forensic QA Lead + Production Integration Auditor  
**Scope:** Verification of Evidence Flow into Product Intelligence & Evidence Graph  
**Verdict:** **INTELLIGENCE DISCONNECTED**  

---

## 1. Executive Summary

The audit standard requires:
> "This is critical. Trace whether the newly generated evidence reaches Product Intelligence.  
> Determine whether: LIVE GOOGLE TRENDS evidence and LIVE GDELT evidence are actually available to: product_intelligence or its evidence graph / intelligence calculation pipeline.  
> Do NOT merely inspect that the code CAN theoretically consume the evidence. Prove that the actual run did.  
> If Product Intelligence did NOT consume the new evidence, report: INTELLIGENCE DISCONNECTED and do not claim END_TO_END."

---

## 2. Ingestion Path Investigation

### A. How `product_intelligence` is Generated
In `core/intelligence_engine.py`:
`AutonomousIntelligenceEngine.run_full_product_intelligence(product_id)` is the canonical entrypoint. It reads:
1. `master_products` (BSR, planned MSRP, daily units, category, region)
2. `multi_platform_listings`
3. `defect_clusters`
4. `product_suppliers`

It computes:
- 10-dimension scorecard (`composite_score`)
- 6-rule kill switch
- Counterfactual economics
- Customer pain map
- Trend early warning

And saves the resulting dossier into SQLite `product_intelligence` via `save_product_intelligence()`.

### B. Does It Query `intelligence_evidence` or `ResearchSourceRegistry`?
An AST and line-by-line inspection of `core/intelligence_engine.py` proves:
1. `AutonomousIntelligenceEngine` **does NOT query `intelligence_evidence`** when calculating `product_intelligence` scores, scorecard dimensions, or kill-switch triggers.
2. `AutonomousIntelligenceEngine` **only WRITES** to `intelligence_evidence` (lines 1265–1301) to log its own internally computed conclusions (from BSR, review defects, and supplier quotes).
3. `AutonomousIntelligenceEngine` **never calls `ResearchSourceRegistry`**, `GoogleTrendsAdapter`, or `GDELTResearchAdapter`.
4. Therefore, even if Google Trends or GDELT signals are persisted into `intelligence_evidence`, the intelligence calculation pipeline does not ingest or factor them into `product_intelligence`.

### C. Evidence Graph Rendering in Web UI (`web/app.py`)
In `web/app.py` lines 926–943 ("Deep Evidence Trail for Product"):
```python
sel_ev_pid = st.selectbox("Select Product to View Evidence Trail:", ...)
if sel_ev_pid:
    ev_list = get_intelligence_evidence(sel_ev_pid)
```
- The Streamlit UI queries `SELECT * FROM intelligence_evidence WHERE product_id = ?`.
- It renders whatever rows exist in `intelligence_evidence`.
- If rows from `google_trends` or `gdelt` are in that table, the UI displays them.
- However, because normal runtime operations do not insert Google Trends or GDELT rows, the live Evidence Trail for products only displays the standard legacy telemetry rows (`Marketplace Telemetry`, `Trend Scout / Scraper`, `Customer Review Mining`, `Supplier Catalog / RFQ`, `Comprehensive 15-Factor Economics`).

---

## 3. Forensic Verdict

Per the explicit audit mandate:
> "If Product Intelligence did NOT consume the new evidence, report: INTELLIGENCE DISCONNECTED and do not claim END_TO_END."

**Official Designation:** **`INTELLIGENCE DISCONNECTED`**

The Product Intelligence calculation pipeline operates independently of `core/research_sources/` and did not consume Google Trends or GDELT evidence during actual APRS runtime operations.
