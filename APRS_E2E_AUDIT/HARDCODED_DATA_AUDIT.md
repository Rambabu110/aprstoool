# APRS — HARDCODED DATA, POLICIES & SIMULATION AUDIT

**Audit Date:** September 2026  
**Auditor:** Principal Code Quality & Data Integrity Auditor  
**System:** APRS — Autonomous Product Research System

---

## 1. Executive Summary: Classification Matrix

To maintain rigorous transparency, all static values and constants in the APRS codebase were audited and classified into three distinct categories:
1. **Category A: Intentional Domain Governance Policies & Mathematical Constants** (Authoritative, frozen, by-design parameters).
2. **Category B: Developer Seeder & Testing Fixtures** (Isolated scripts used exclusively for offline initialization).
3. **Category C: Defunct / Legacy Code Artifacts** (Inactive remnants of purged features).

**Critical Finding:** There is **ZERO dynamic fabrication** in production execution paths. When real-world data is absent (such as post-launch sales outcomes), the system cleanly returns structured empty states (`NO_OBSERVATION_DATA`, `EMPTY`) rather than injecting mock numbers.

---

## 2. Category A: Intentional Domain Policies & Constants

These constants represent deliberate e-commerce, mathematical, and regulatory business logic. They are hardcoded by architectural design to maintain reproducibility and deterministic behavior.

| File & Location | Constant / Parameter | Value | Architectural Purpose |
|---|---|---|---|
| [`core/intelligence_engine.py:372`](file:///d:/tools/APRS/core/intelligence_engine.py) | `dimension_weights` | Sum = 1.00 (Demand: 0.18, Econ: 0.18, Pain: 0.15, Trend: 0.12, Comp: 0.10, Sourcing: 0.10, Risk: 0.05, Saturation: 0.05, Evidence: 0.04, Freshness: 0.03) | Authoritative V7.2 opportunity scoring formula. Must never change without formal policy version bump. |
| [`core/intelligence_engine.py:65`](file:///d:/tools/APRS/core/intelligence_engine.py) | `KILL_RULES` (6 Domains) | Thresholds: Min CM ₹0.0, Max Stress Drawdown -20%, Min Pain 3, Min Trend 40 | Non-negotiable kill triggers that disallow unviable products from advancing to launch. |
| [`core/learning_engine.py:79`](file:///d:/tools/APRS/core/learning_engine.py) | `LEARNING_POLICY` | `minimum_sample_size: 5`, `demand_mbe_noise_threshold: 0.5`, `pct_point_noise_threshold_pp: 1.0` | Statistical safeguards preventing noisy, small-sample bias claims ($N < 5$ flagged as provisional). |
| [`core/observation_scheduler.py:45`](file:///d:/tools/APRS/core/observation_scheduler.py) | `DEFAULT_GRACE_PERIOD_DAYS` | 7 Days | Grace period allowing real-world sales batch reconciliation before an observation window is marked OVERDUE. |
| [`core/economics_engine.py:52`](file:///d:/tools/APRS/core/economics_engine.py) | Tax & Compliance Defaults | GST: 18%, Import Duty: 15%, Referral: 15% | Standard Indian e-commerce statutory rates used in baseline 15-factor waterfall. |
| [`core/calibration_engine.py:43`](file:///d:/tools/APRS/core/calibration_engine.py) | `V8_CALIBRATION_VERSION` | `"V8_CALIBRATION_V1"` | Immutability token attached to all calibration records for traceability. |

---

## 3. Category B: Developer Seeder & Testing Fixtures

These scripts contain sample data designed strictly for bootstrapping development environments and automated test suites:

1. **[`tools/seed_market_data.py`](file:///d:/tools/APRS/tools/seed_market_data.py):**  
   - *Purpose:* Seeds initial product keywords, synthetic supplier mock quotes, and test niches when spinning up a blank database.
   - *Isolation:* Explicitly isolated; not executed during runtime or by Streamlit application startup. Contains safety checks to prevent overwriting live database records.

2. **[`tools/browser_use_cloud.py`](file:///d:/tools/APRS/tools/browser_use_cloud.py):**  
   - *Line 42:* Contains a `use_mock=False` parameter. When set to `True` during offline unit testing without network, returns canned DOM responses. Default is live execution.

3. **`tests/fixtures/` and Test Data Generators:**  
   - Used exclusively by `pytest` test runners to validate edge-case mathematics (such as negative margins, division-by-zero, and trigger aborts).

---

## 4. Category C: Legacy / Defunct Code Artifacts

1. **[`core/subscription_service.py`](file:///d:/tools/APRS/core/subscription_service.py):**  
   - Contains hardcoded Razorpay subscription tier pricing (`"TIER_PRO": 4999`, `"TIER_ENTERPRISE": 14999`).
   - *Audit Finding:* This feature was deprecated and purged from the UI navigation. These values are dead code and do not affect research, gating, or intelligence calculations.

---

## 5. Dynamic Computation vs Hardcoding Verification

During the audit, every primary metric displayed on the UI was traced back to its database origin:
- **Opportunities Count (260 products):** Computed via `SELECT count(*) FROM master_products`.
- **Product Scorecard (e.g. 74.2/100):** Computed dynamically via $\sum (\text{dimension\_score} \times \text{weight})$.
- **Contribution Margin:** Computed dynamically via the 15-factor cost deduction waterfall.
- **Prediction vs Reality Summary:** Computed dynamically from `prediction_calibrations`; verified to return 0 when no rows exist.

**Conclusion:** The codebase displays high architectural hygiene, with clean separation between policy constants, mathematical engines, and dynamic telemetry.
