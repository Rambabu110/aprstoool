# APRS — END-TO-END DATA FLOW & ARCHITECTURE AUDIT

**Audit Date:** September 2026  
**Auditor:** Principal Data & Architecture Auditor  
**System:** APRS — Autonomous Product Research System

---

## 1. Architectural Overview & System Flowchart

The APRS platform operates as a deterministic, multi-stage state machine backed by embedded SQLite tables. Data flows unidirectionally from external market signals through automated gating and intelligence synthesis, culminating in post-launch calibration and human-directed learning.

```
[External Market Signals]
  (Amazon BSR, Keepa API, IndiaMART, Alibaba)
         │
         ▼
[Stage 1: Discovery] ──────────► `dynamic_seed_keywords` / `scraped_listings`
         │
         ▼
[Stage 2: Deep Scrape] ────────► `master_products` (Status: DISCOVERED)
         │
         ├───────────────────────────────┐
         ▼                               ▼
[Stage 3: Economics]             [Stage 4: Sourcing]
   `economics_assessments`         `product_suppliers`
         │                               │
         └───────────────┬───────────────┘
                         ▼
             [Stage 5: Arbiter War Room]
                `meeting_audit_log`
                         │
                         ▼
             [Stage 6: Launchpad] ──────► `launchpad_items`
                         │
 ┌───────────────────────┴───────────────────────┐
 │                                               │
 ▼                                               ▼
[V7 Intelligence Synthesis]          [V8 Decision Snapshot]
  `product_intelligence`               `decision_ledger` (IMMUTABLE TRIGGER)
  `intelligence_evidence`                        │
  `intelligence_timeline`                        ▼
  `opportunity_alerts`               [Observation Scheduler]
                                       (30, 60, 90-Day Windows)
                                                 │
                                                 ▼
                                     [Outcome Ingestion Adapters]
                                       (Manual CSV, Shopify, SP-API)
                                                 │
                                                 ▼
                                       `product_outcomes`
                                                 │
                                                 ▼
                                     [Prediction Calibration]
                                       `prediction_calibrations`
                                                 │
                                                 ▼
                                       [Learning & Bias Engine]
                                       `learning_recommendations`
                                       (Advisory Human Review Queue)
```

---

## 2. Detailed Data Flow Stage-by-Stage

### Stage 1 & 2: Market Discovery & Product Ingestion
1. **Trigger:** User initiates research run or background daemon scans `dynamic_seed_keywords`.
2. **Ingestion:** Playwright scraper queries e-commerce platforms; Keepa API retrieves BSR historical curves.
3. **Database Mutation:**
   - Raw extracts saved into `scraped_listings`.
   - Unique products normalized and upserted into `master_products` with initial status `'DISCOVERED'`.
   - Gate progress record initialized in `product_gate_progress` for Gate 1 (`PASS`).

### Stage 3 & 4: Parallel Unit Economics & Sourcing Feasibility
1. **Unit Economics (Gate 3):**
   - Ingests product planned MSRP, estimated weight, category, and target sourcing country.
   - `core/economics_engine.py` applies the 15-factor waterfall (FOB price, freight, import duties, GST, packaging, warehousing, return provisions, payment gateway fee, CAC).
   - Writes assessment record to `economics_assessments`.
   - Gate 3 status set to `PASS` if net profit margin $\ge 15\%$ and stress-test margin $> 0\%$.
2. **Supplier Intelligence (Gate 4):**
   - Scrapes wholesale supplier quotes from IndiaMART and Alibaba.
   - Computes minimum order quantities (MOQ), sample availability, and supplier risk scores.
   - Writes record to `product_suppliers`. Gate 4 marked `PASS` if verified supplier found with acceptable lead time.

### Stage 5: Multi-Agent Arbiter War Room
1. **Input:** Candidate product must have BOTH Gate 3 and Gate 4 in `PASS` status.
2. **Execution:** Three specialized AI agent personas (Data Analyst, Risk Officer, Sourcing Expert) evaluate the product dossier via NVIDIA NIM LLM inference.
3. **Consensus:** Arbiter tallies votes. If consensus $\ge 2/3$, writes dialogue transcripts to `meeting_audit_log` and marks Gate 5 as `PASS`.

### Stage 6: Launchpad & Procurement Readiness
1. **Input:** Candidate passed Gate 5.
2. **Preparation:** Generates final procurement checklist, packaging specifications, barcode requirements, and listing copy.
3. **Database Write:** Record inserted into `launchpad_items`.

---

## 3. V7 Autonomous Intelligence Synthesis Flow

Operating concurrently with the gate pipeline, the V7 Intelligence Engine (`core/intelligence_engine.py`) performs holisitic analysis across all products:
1. **Scorecard Engine:** Aggregates metrics from `master_products`, `economics_assessments`, `scraped_listings`, and `product_suppliers`.
2. **Mathematical Normalization:** Calculates 10 dimension scores (0–100) and applies authoritative normalized weights (summing to 1.00) to yield `overall_score`.
3. **Kill Switch Evaluation:** Independently checks the 6 kill domains. If any critical flaw is detected (e.g., negative contribution margin or customer defect rate $> 8\%$), assigns status `'KILLED'`.
4. **Persistence:**
   - Writes scorecard and kill verdict to `product_intelligence`.
   - Writes individual audit data points to `intelligence_evidence`.
   - Writes timestamped milestone events to `intelligence_timeline`.
   - Generates high-priority notifications in `opportunity_alerts`.

---

## 4. V8 Post-Launch Outcome & Learning Loop

The V8 lifecycle closes the feedback loop between predictions made during research and actual e-commerce market results:

1. **Decision Snapshotting (`decision_ledger`):**  
   - When a product is approved for launch, an immutable snapshot of predictions (predicted daily units, predicted MSRP, planned CAC, frozen score) is saved to `decision_ledger`.
   - SQLite trigger `trg_decision_ledger_immutable` ensures this snapshot can NEVER be overwritten or retroactively altered.

2. **Observation Scheduling (`core/observation_scheduler.py`):**  
   - Computes 30-day, 60-day, and 90-day observation window boundaries relative to launch date.
   - Tracks maturity states: `NOT_DUE` $\rightarrow$ `DUE` (within 7-day grace window) $\rightarrow$ `OVERDUE`.

3. **Outcome Ingestion (`core/outcome_ingestion.py`):**  
   - External sales data is ingested via adapters (Manual CSV, Shopify API, Amazon SP-API).
   - Ingestion enforces dry-run validation, rejects invalid numbers, and normalizes rows into `product_outcomes`.

4. **Prediction Calibration (`core/calibration_engine.py`):**  
   - Links the outcome record with its corresponding authoritative decision snapshot enforcing temporal integrity.
   - Calculates signed error ($actual - predicted$), absolute error, and percentage error.
   - Persists calibration record to `prediction_calibrations`.

5. **Learning & Advisory Recommendation Engine (`core/learning_engine.py`):**  
   - Aggregates calibrations across products.
   - Enforces sample-size gating ($N \ge 5$).
   - Calculates Mean Bias Error ($MBE$) to identify systematic `OVERPREDICTION_BIAS` or `UNDERPREDICTION_BIAS`.
   - Generates human-auditable recommendations in `learning_recommendations`.
   - **Safety Invariant:** All recommendations have status `PROPOSED`. Zero autonomous modifications are made to scoring weights or kill switch thresholds.
