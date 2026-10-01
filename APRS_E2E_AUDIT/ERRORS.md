# APRS — FULL FORENSIC END-TO-END AUDIT: DEFECTS & ERRORS LOG

**Audit Date:** October 2026  
**Auditor Policy:** Strict Forensic Non-Destructive Audit. Zero Code Changes Applied.  
**Total Identified Defects:** 1 (Medium Severity)  
**Total Validated Expected Empty States:** 2 (Non-Defects)

---

# ERR-ECON-002 — Economics Engine Accepts Negative FOB Supply Cost Without Clamping or Error

## Severity
MEDIUM

## Classification
ERROR

## Exact Location
Page: Dashboard  
Tab: 📊 Economics (`econ`)  
Subtab: Main View & Backend Engine  
Component: `Comprehensive15FactorEconomics.calculate_scenario` & `evaluate_15_factor_economics`  
URL: `http://localhost:8501`

## Preconditions
1. Python virtual environment active (`.venv`).
2. Programmatic call to `Comprehensive15FactorEconomics.calculate_scenario` or `evaluate_15_factor_economics`.

## Exact Reproduction Steps
1. Import `Comprehensive15FactorEconomics` from `core.economics_engine`.
2. Instantiate calculator: `econ = Comprehensive15FactorEconomics()`.
3. Execute:
   ```python
   result = econ.calculate_scenario(
       fob_price=-200.0,
       target_msrp=999.0,
       category="Electronics",
       source_country="India"
   )
   ```
4. Inspect returned dictionary keys `contribution_margin`, `landed_cost`, and `net_margin_pct`.

## Expected Behavior
A negative FOB cost represents an impossible physical scenario. The function must either:
1. Raise `ValueError("fob_price must be non-negative")`, or
2. Clamp negative input to `0.0` with a validation warning.

## Actual Behavior
The calculation proceeds with `fob_price = -200.0`. The landed cost is computed with the negative value, resulting in mathematically nonsensical inflated contribution margins (>100% margin on retail sale).

## Evidence
- **Screenshot:** `APRS_E2E_AUDIT/screenshots/passed/PASS_nav_econ.png`
- **Log:** `APRS_E2E_AUDIT/evidence/deep_functional_audit_results.json` (`ERR-ECON-002`)
- **Console:** Verified in Python REPL.
- **Database:** No database mutation occurred.
- **Code Reference:** [`core/economics_engine.py:calculate_scenario`](file:///d:/tools/APRS/core/economics_engine.py)

## First Detected At
Initial deep functional boundary verification of 15-factor economics engine.

## Reproducibility
Always (100% deterministic).

## Data Impact
Possible (if upstream scrapers or manual import files supply un-validated negative quotes, distorted margins could influence opportunity scoring).

## User Impact
In the web UI form (`web/app.py:3030`), Streamlit's `st.number_input` sets `min_value=0.5`, which prevents human users from entering negative values via the web form stepper. However, automated scrapers, background daemons, or API integrations bypassing the UI form can supply negative floats to the backend engine without rejection.

## Root-Cause Evidence
In `core/economics_engine.py`, while `target_msrp` has guard logic preventing zero-division errors, `fob_price` lacks an explicit boundary assertion `if fob_price < 0:` at the entry point of `calculate_landed_cost` and `calculate_scenario`.

## External Dependency
None (Pure local Python logic).

## Required Resource
Standard Python arithmetic library.

## Free Alternative
N/A (Built-in code validation).

## Paid Alternative
N/A.

## Suggested Investigation
DO NOT FIX NOW. In future maintenance phase, inspect `core/economics_engine.py` line 120 and add defensive validation:
```python
fob_price = max(0.0, float(fob_price))
```
or raise an explicit `ValueError`.

## Screenshot
`PASS_nav_econ.png`

## Status
OPEN

---

# 2. Validated Expected Empty States (NOT Defects)

### EMPTY-V8-PVR-001 — Production Prediction vs Reality Empty State

## Severity
INFORMATIONAL (NON-DEFECT)

## Classification
EXPECTED EMPTY

## Exact Location
Page: Dashboard  
Tab: 🎯 Product Intelligence (`intelligence`)  
Subtab: Prediction vs Reality (`t_pvr`)  
Component: `PredictionRealityReportService.get_portfolio_summary`  
URL: `http://localhost:8501`

## Preconditions
Production database `data/research_engine.db` with 0 post-launch outcome records.

## Exact Reproduction Steps
1. Navigate to 🎯 Product Intelligence tab.
2. Click Subtab 8: Prediction vs Reality.
3. Observe summary metric cards and dossier table.

## Expected Behavior
Because APRS V8 outcome tracking is a post-launch observation system and no physical products have matured through their 30/60/90-day post-launch sales window, the system must display an informative "Awaiting real-world outcome observations" state without inventing or fabricating numbers.

## Actual Behavior
The UI renders cleanly with 0 locked decisions, 0 outcomes, and 0 calibrations, displaying the honest informative banner.

## Evidence
- **Screenshot:** `APRS_E2E_AUDIT/screenshots/passed/PASS_subtab_t_pvr.png`
- **Database:** `SELECT count(*) FROM product_outcomes;` returns `0`.

## Status
VERIFIED_EXPECTED_EMPTY

---

### EMPTY-V8-LEARN-001 — Production Learning Engine Empty State

## Severity
INFORMATIONAL (NON-DEFECT)

## Classification
EXPECTED EMPTY

## Exact Location
Page: Dashboard  
Tab: 🎯 Product Intelligence (`intelligence`)  
Subtab: Learning & Bias (`t_learn`)  
Component: `LearningEngine.get_portfolio_learning_summary`  
URL: `http://localhost:8501`

## Preconditions
Production database `data/research_engine.db` with 0 calibration records.

## Exact Reproduction Steps
1. Navigate to 🎯 Product Intelligence tab.
2. Click Subtab 9: Learning & Bias.
3. Observe portfolio learning status badge and recommendation list.

## Expected Behavior
Under `LEARNING_POLICY`, a minimum sample size of $N \ge 5$ observations is required before aggregate directional bias claims are made. When $N = 0$, the engine must return `evidence_status = "NO_OBSERVATION_DATA"` without generating speculative bias recommendations.

## Actual Behavior
The engine returns `NO_OBSERVATION_DATA` and the UI displays the status badge "Awaiting Real Observations" with an empty recommendation review queue.

## Evidence
- **Screenshot:** `APRS_E2E_AUDIT/screenshots/passed/PASS_subtab_t_learn.png`
- **Database:** `SELECT count(*) FROM prediction_calibrations;` returns `0`.

## Status
VERIFIED_EXPECTED_EMPTY
