# APRS — FULL FORENSIC END-TO-END AUDIT: PASSED CATALOG

**Total Passed Tests:** 45 Verified Passing Verifications  
- **Browser UI & Navigation Tests:** 23 Passing Verifications  
- **Deep Functional & Architectural Engine Tests:** 22 Passing Verifications (plus 2 Verified Expected Empty States)

---

## 1. Browser UI & Navigation Verifications (23 PASS)

All UI tests were executed using automated Chromium (`channel="chrome"`, headless) interacting with `http://localhost:8501`. Console logs were captured in `APRS_E2E_AUDIT/logs/chrome_console_audit.log` (0 unhandled exceptions). Screenshots are stored in `APRS_E2E_AUDIT/screenshots/passed/`.

| ID | Feature / Component | Location / Tab | Expected Behavior | Actual Observed Result | Evidence Screenshot |
|---|---|---|---|---|---|
| **PASS-001** | Dashboard Initial Load & Theme | Initial Page Load | Cyberpunk dark theme (#0e1117, neon accents) renders cleanly with live ticker and cards. | Loaded in 5.93s; title "APRS V6 — Autonomous E-Commerce Swarm" and branding rendered. | `PASS-001_initial_dashboard_load.png` |
| **PASS-002** | Sidebar Swarm Telemetry & DB Controls | Sidebar Global | Active Swarm Models, AI Supervisor status, and DB statistics display without error. | Models present, Supervisor active, DB Stats displayed cleanly. | `PASS-002_sidebar_controls_rendered.png` |
| **PASS-NAV-OPPS** | Opportunities Tab | Top Nav: `opps` | Opportunities dashboard renders product cards, metrics, filters, and gate progress bars. | Successfully rendered 29,484 characters of DOM; no layout collapse. | `PASS_nav_opps.png` |
| **PASS-NAV-INTELLIGENCE** | Product Intelligence Tab | Top Nav: `intelligence` | Intelligence dashboard renders summary statistics and subtab container. | Successfully rendered 31,349 characters of DOM; subtabs container ready. | `PASS_nav_intelligence.png` |
| **PASS-SUBTAB-T_OPPS** | Opportunities & Scorecards Subtab | Intelligence: Subtab 1 | 10-dimension scorecards, composite opportunity score breakdown, confidence bars render. | Successfully rendered scorecards and filterable product metrics. | `PASS_subtab_t_opps.png` |
| **PASS-SUBTAB-T_KILL** | Kill Switch & Evidence Trails Subtab | Intelligence: Subtab 2 | 6 Kill Switch domains, status pills (KILLED / SURVIVES), and evidence audit trail render. | Successfully displayed kill reasons, domain checks, and evidence timestamps. | `PASS_subtab_t_kill.png` |
| **PASS-SUBTAB-T_ECON** | Counterfactual Economics Subtab | Intelligence: Subtab 3 | Contribution margin sensitivity, CAC stress test, and breakeven volume simulations render. | Rendered sensitivity tables and counterfactual parameter sliders. | `PASS_subtab_t_econ.png` |
| **PASS-SUBTAB-T_PAIN** | Customer Pain Map Subtab | Intelligence: Subtab 4 | Defect clusters, return root causes, negative review sentiment distribution render. | Displayed defect clusters, pain severity ratings, and complaint frequencies. | `PASS_subtab_t_pain.png` |
| **PASS-SUBTAB-T_GAPS** | Competitor Gaps & Trends Subtab | Intelligence: Subtab 5 | Feature gaps, price comparison distributions, and trend velocity indicators render. | Rendered competitor feature matrices and pricing distribution charts. | `PASS_subtab_t_gaps.png` |
| **PASS-SUBTAB-T_ALERTS** | Alert Center & Conflicts Subtab | Intelligence: Subtab 6 | Opportunity alerts, cross-source price/rating conflicts, and resolution tools render. | Displayed unresolved data conflicts, supplier discrepancies, and alert feeds. | `PASS_subtab_t_alerts.png` |
| **PASS-SUBTAB-T_TIMELINE** | Watchlist & Timeline Subtab | Intelligence: Subtab 7 | Monitored products watchlist and chronological intelligence event timeline render. | Displayed tracked product timeline cards with timestamped event histories. | `PASS_subtab_t_timeline.png` |
| **PASS-SUBTAB-T_PVR** | Prediction vs Reality Subtab | Intelligence: Subtab 8 | V8 calibration summary cards, product dossiers, error distributions render (or clean empty state). | Displayed portfolio calibration KPIs and empty state handling without error. | `PASS_subtab_t_pvr.png` |
| **PASS-SUBTAB-T_LEARN** | Learning & Bias Engine Subtab | Intelligence: Subtab 9 | Systematic directional bias indicators, MBE/MAE/MAPE metrics, human recommendations render. | Displayed directional bias gauges, policy immutability badges, and review queues. | `PASS_subtab_t_learn.png` |
| **PASS-NAV-PRICE_COMPARE** | Price Comparison Tab | Top Nav: `price_compare` | Multi-platform price tracking, arbitrage margin calculator, and listing views render. | Rendered comparison tables, price spread analysis, and platform links. | `PASS_nav_price_compare.png` |
| **PASS-NAV-TRENDING** | Trending Tab | Top Nav: `trending` | Real-time trend signals, volume growth velocity, and emerging keyword tables render. | Displayed trending keyword velocity, social volume signals, and category badges. | `PASS_nav_trending.png` |
| **PASS-NAV-PREDICTIONS** | Predictions Tab | Top Nav: `predictions` | ML/AI price and demand forecasts, confidence intervals, and trend models render. | Forecast visualizations and predicted demand ranges rendered without failure. | `PASS_nav_predictions.png` |
| **PASS-NAV-LAUNCHPAD** | Launchpad Tab | Top Nav: `launchpad` | Gate 6 Launchpad readiness checklist, supplier MOQ, packaging, and go-to-market status render. | Displayed active launch candidates, procurement requirements, and launch checklists. | `PASS_nav_launchpad.png` |
| **PASS-NAV-MEETING** | Arbiter Meeting Room Tab | Top Nav: `meeting` | Gate 5 AI Multi-Agent Arbiter War Room, agent transcripts, and voting consensus render. | Displayed agent dialogue logs (Analyst, Risk Officer, Sourcing Expert) and consensus tallies. | `PASS_nav_meeting.png` |
| **PASS-NAV-KEEPA** | Keepa Analytics Tab | Top Nav: `keepa` | Historical BSR charts, buy box price fluctuations, and sales rank tracking render. | Rendered Keepa telemetry charts and sales rank velocity metrics. | `PASS_nav_keepa.png` |
| **PASS-NAV-SUPPLIER** | Supplier Intelligence Tab | Top Nav: `supplier` | Supplier verification metrics, Alibaba/IndiaMART lead times, and reliability ratings render. | Displayed verified supplier directories, lead-time distributions, and quotes. | `PASS_nav_supplier.png` |
| **PASS-NAV-ECON** | Economics & Unit Economics Tab | Top Nav: `econ` | Full 15-factor unit economics calculator, duty tariffs, landed COGS, and margin breakdown render. | Rendered 15-factor cost waterfall, margin sensitivity tables, and tariff calculators. | `PASS_nav_econ.png` |
| **PASS-NAV-DB_EXPLORER** | Database Explorer Tab | Top Nav: `db_explorer` | Raw SQLite table browser, schema viewer, and SQL query runner render without security issues. | Table schema inspector and paginated row browser displayed database tables cleanly. | `PASS_nav_db_explorer.png` |
| **PASS-NAV-ARCHIVE** | Archive Tab | Top Nav: `archive` | Rejected products archive, kill switch post-mortems, and historical run logs render. | Displayed archived products, disqualification rationale, and historical run logs. | `PASS_nav_archive.png` |

---

## 2. Deep Functional & Architectural Verifications (22 PASS)

All deep functional tests were executed in an isolated environment using temporary SQLite database copies to guarantee zero mutations to `data/research_engine.db`.

### A. V6 6-Stage Gate System (`core/database.py:can_enter_gate`)
- **PASS-GATE-001 (Gate 1 Entry Open):**  
  - *Location:* `core/database.py:can_enter_gate`  
  - *Expected:* Gate 1 (Discovery) is the pipeline entry point and must always return `(True, "Gate 1 always open")`.  
  - *Actual:* Returns `can_enter=True`, `reason="Gate 1 always open"`.  
- **PASS-GATE-002 (Gate 3 & 4 Blocked when Gate 2 Incomplete):**  
  - *Location:* `core/database.py:can_enter_gate`  
  - *Expected:* Gate 3 (Unit Economics) and Gate 4 (Supplier Verification) cannot be entered if Gate 2 (Deep Scrape) is not in `PASS` or `OVERRIDDEN` status.  
  - *Actual:* Blocked cleanly: `can_enter=False`, `reason="Gate 2 is PENDING (must be PASS or OVERRIDDEN)"`.  
- **PASS-GATE-003 (Gate 3 & 4 Open After Gate 2 PASS):**  
  - *Location:* `core/database.py:can_enter_gate`  
  - *Expected:* Once Gate 2 transitions to `PASS`, both parallel branches Gate 3 and Gate 4 allow entry.  
  - *Actual:* Returns `can_g3=True`, `can_g4=True`.  
- **PASS-GATE-004 (Gate 5 Dual Prerequisite Enforcement):**  
  - *Location:* `core/database.py:can_enter_gate`  
  - *Expected:* Gate 5 (Arbiter War Room) requires BOTH Gate 3 AND Gate 4 to be `PASS` or `OVERRIDDEN`. If either is `PENDING` or `FAILED`, entry is strictly blocked.  
  - *Actual:*  
    - Scenario A (G3 Pass, G4 Pending): Blocked (`False`).  
    - Scenario B (G3 Failed, G4 Pass): Blocked (`False`).  
    - Scenario C (G3 Pass, G4 Pass): Permitted (`True`).  
- **PASS-GATE-005 (Gate 6 Launchpad Dependency on Gate 5):**  
  - *Location:* `core/database.py:can_enter_gate`  
  - *Expected:* Gate 6 (Launchpad) requires Gate 5 (Arbiter consensus) to be `PASS` before candidate can enter launchpad.  
  - *Actual:* Pre-G5: Blocked (`False`); Post-G5: Permitted (`True`).

### B. V7 Autonomous Product Intelligence (`core/intelligence_engine.py`)
- **PASS-V7-001 (10-Dimension Scorecard Schema Completeness):**  
  - *Location:* `core/intelligence_engine.py:evaluate_scorecard`  
  - *Expected:* All 10 required opportunity dimensions must be computed and returned in the scorecard payload.  
  - *Actual:* All 10 dimensions present: `demand_strength`, `trend_strength`, `competition_pressure`, `customer_pain`, `economic_viability`, `sourcing_feasibility`, `operational_risk`, `market_saturation`, `evidence_quality`, `data_freshness`.  
- **PASS-V7-002 (Scorecard Dimension Weights Sum to Exactly 1.00):**  
  - *Location:* `core/intelligence_engine.py:372`  
  - *Expected:* The sum of weights across all 10 dimensions must equal exactly 1.00 ($0.18 + 0.12 + 0.10 + 0.15 + 0.18 + 0.10 + 0.05 + 0.05 + 0.04 + 0.03 = 1.00$).  
  - *Actual:* Mathematical sum equals exactly `1.0000`.  
- **PASS-V7-003 (Composite Opportunity Score Mathematical Accuracy):**  
  - *Location:* `core/intelligence_engine.py:385`  
  - *Expected:* Composite opportunity score matches $\sum (\text{score}_i \times \text{weight}_i)$. Tested with uniform 54.0 dimension scores.  
  - *Actual:* Output score equals `54.0` (exact arithmetic match).  
- **PASS-V7-004 (Kill Switch Disproves Unviable Economics):**  
  - *Location:* `core/intelligence_engine.py:evaluate_kill_switch`  
  - *Expected:* Negative contribution margin triggers `KILLED` verdict under Domain 2 (Economics Deficit).  
  - *Actual:* Returns `status="KILLED"`, reason: `['Economics Deficit: Base case contribution margin is negative (-350.00).']`.  
- **PASS-V7-005 (V7.2 Separation: High Score Does Not Prevent Kill Verdict):**  
  - *Location:* `core/intelligence_engine.py`  
  - *Expected:* A product with high demand or trend scores cannot bypass an economic kill trigger; score, confidence, and kill status remain completely independent.  
  - *Actual:* Opportunity with 90+ demand score was independently tagged with `kill_status="KILLED"`.

### C. V8 Decision Ledger Immutability (`data/research_engine.db:trg_decision_ledger_immutable`)
- **PASS-V8-001 (SQLite Immutability Trigger Enforcement):**  
  - *Location:* Database trigger `trg_decision_ledger_immutable`  
  - *Expected:* Any SQL `UPDATE` executed against `decision_ledger` raises an `ABORT` exception: `"decision_ledger records are immutable and cannot be updated"`.  
  - *Actual:* Executed `UPDATE decision_ledger SET frozen_score = 99.0 WHERE decision_id = 1;` $\rightarrow$ Rejected with `sqlite3.IntegrityError: decision_ledger records are immutable and cannot be updated`. Record remained unchanged.

### D. V8 Observation Scheduler (`core/observation_scheduler.py`)
- **PASS-SCHED-001 (Observation Window Boundary Computation):**  
  - *Location:* `core/observation_scheduler.py:compute_observation_windows`  
  - *Expected:* Window for `DAY_30` duration is 30 days, `period_start` = launch date, `period_end` = launch + 29 days, `due_date` = launch + 30 days.  
  - *Actual:* Returned exact dictionary: `{'period_type': 'DAY_30', 'period_start': '2026-08-01', 'period_end': '2026-08-30', 'due_date': '2026-08-31', 'duration_days': 30}`.  
- **PASS-SCHED-002 (Window Prior to Due Date -> NOT_DUE):**  
  - *Location:* `core/observation_scheduler.py:evaluate_window_maturity`  
  - *Expected:* If current date is prior to window `due_date`, maturity status must be `NOT_DUE`.  
  - *Actual:* For evaluation on `2026-08-15` (due `2026-08-31`), returned `status="NOT_DUE"`.  
- **PASS-SCHED-003 (Window Within 7-Day Grace Period -> DUE):**  
  - *Location:* `core/observation_scheduler.py:evaluate_window_maturity`  
  - *Expected:* If current date is within the 7-day grace period following `due_date` and outcome has not been ingested, status is `DUE`.  
  - *Actual:* For evaluation on `2026-09-02` (diff = 2 days $\le$ 7), returned `status="DUE"`.  
- **PASS-SCHED-004 (Window Past 7-Day Grace Period -> OVERDUE):**  
  - *Location:* `core/observation_scheduler.py:evaluate_window_maturity`  
  - *Expected:* If current date exceeds `due_date` + 7 days without observation, status transitions to `OVERDUE`.  
  - *Actual:* For evaluation on `2026-09-15` (diff = 15 days > 7), returned `status="OVERDUE"`.

### E. V8 Manual CSV Outcome Adapter (`core/outcome_adapters/manual_csv_adapter.py`)
- **PASS-CSV-001 (Manual CSV Valid Row Normalization):**  
  - *Location:* `core/outcome_adapters/manual_csv_adapter.py:ManualCsvOutcomeAdapter`  
  - *Expected:* Valid raw outcome dictionary normalizes into strongly-typed `NormalizedOutcomeRecord`.  
  - *Actual:* Normalized units: `350`, actual revenue: `874650.0`, landed COGS: `297500.0`.  
- **PASS-CSV-002 (Manual CSV Validation Rejection of Impossible Data):**  
  - *Location:* `core/outcome_adapters/manual_csv_adapter.py:validate_source_record`  
  - *Expected:* Rejects physically impossible data (negative units, negative revenue, returns > units).  
  - *Actual:* Rejected invalid record with: `["INVALID_NUMERIC_VALUE: Field 'units_sold' cannot be negative (-50)."]`.  
- **PASS-CSV-003 (ManualCsvOutcomeService File Validation & Safety Audit):**  
  - *Location:* `core/outcome_adapters/manual_csv_adapter.py:validate_file`  
  - *Expected:* Inspects file headers and contents, enforcing dry-run guarantees.  
  - *Actual:* Analyzed input file, flagged missing required columns cleanly, returned structured validation report.

### F. V8 Prediction vs Reality Reporting (`core/prediction_reality_report.py`)
- **PASS-V8-PVR-002 (Metric Formatter Handles None/Zero/Positive Gracefully):**  
  - *Location:* `core/prediction_reality_report.py:format_metric`  
  - *Expected:* Missing data returns `"Not observed"` (never crashes); zero formats as `"₹0"`; positive currency values format with commas (`"₹12,450"`).  
  - *Actual:* Formatted values: `None` $\rightarrow$ `"Not observed"`, `0.0` $\rightarrow$ `"₹0"`, `12450.5` $\rightarrow$ `"₹12,450"`.

### G. V8 Learning & Bias Engine (`core/learning_engine.py`)
- **PASS-V8-LEARN-002 (Learning Engine MBE Formula & Sign Convention):**  
  - *Location:* `core/learning_engine.py:calculate_aggregate_bias`  
  - *Expected:* Formula $MBE = \text{mean}(\text{actual} - \text{predicted})$. Given predicted = 500, actual = 300, $MBE = 300 - 500 = -200.0$. Negative MBE signifies that the model predicted too high, classifying correctly as `OVERPREDICTION_BIAS` with $MAE = 200.0$.  
  - *Actual:* Returns `directional_bias="OVERPREDICTION_BIAS"`, `mean_signed_error_mbe=-200.0`, `mean_absolute_error_mae=200.0`, `reliability_tier="PROVISIONAL_AGGREGATE"`.  
- **PASS-V8-LEARN-003 (Learning Engine Parameter Immutability):**  
  - *Location:* `core/learning_engine.py`  
  - *Expected:* The learning engine is strictly analytical/advisory and must NEVER mutate scoring weights, thresholds, or kill switch rules.  
  - *Actual:* Scoring weights and kill thresholds in `core/intelligence_engine.py` remained 100% frozen after full learning engine execution.

### H. 15-Factor Economics Engine (`core/economics_engine.py`)
- **PASS-ECON-001 (Economics Engine MSRP=0 Safe Rejection):**  
  - *Location:* `core/economics_engine.py:calculate_scenario`  
  - *Expected:* Setting MSRP to `0.0` fails cleanly without triggering `ZeroDivisionError`.  
  - *Actual:* Returns `status="FAIL"`, `contribution_margin=-277.23` without unhandled exception.  
- **PASS-ECON-003 (Economics Engine Handles 8-Figure Numbers Without Overflow):**  
  - *Location:* `core/economics_engine.py:calculate_scenario`  
  - *Expected:* Handles large enterprise wholesale price points (e.g., ₹10,000,000) without float overflow or precision degradation.  
  - *Actual:* Computed successfully: contribution margin = ₹3,375,690.99, net margin = 33.76%.
