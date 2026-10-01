# 02 — FIXES APPLIED

## Fix 1A: `core/background_daemon.py` — Tuple Unpacking

**File:** `core/background_daemon.py`  
**Lines:** 302–309  
**Date:** 2026-10-01

```diff
-                                    match = matcher.evaluate_match_confidence(
+                                    classification, _confidence = matcher.evaluate_match_confidence(
                                         pname, ep.get("name", ""),
                                         pprice, float(ep.get("planned_msrp") or 0)
                                     )
-                                    if match.get("classification") == "EXACT_MATCH":
+                                    if classification == "EXACT_MATCH":
```

**Rationale:** `evaluate_match_confidence()` returns `Tuple[str, float]`. The `_confidence` variable is intentionally ignored (prefixed `_`) since dedup only needs the classification. This matches the established contract in `test_aprs_v6_advanced.py` which uses `match_type, conf = ...` unpacking.

---

## Fix 1B: `core/orchestrator.py` — Tuple Unpacking

**File:** `core/orchestrator.py`  
**Lines:** 671–675  
**Date:** 2026-10-01

```diff
-                match = matcher.evaluate_match_confidence(
+                classification, _confidence = matcher.evaluate_match_confidence(
                     pname, cp.get("title", ""),
                     pprice, float(cp.get("price", 0))
                 )
-                if match.get("classification") == "EXACT_MATCH":
+                if classification == "EXACT_MATCH":
```

---

## New Regression Test: `tests/test_daemon_matcher_regression.py`

**15 tests added covering:**
1. `test_returns_tuple_not_dict` — Contract verification
2. `test_tuple_has_no_get_method` — Documents the original bug (asserts AttributeError)
3. `test_exact_match_classification` — Exact match pair
4. `test_unrelated_products` — Non-match pair
5. `test_extreme_price_deviation_forces_unrelated` — Price ratio guard
6. `test_probable_variant_classification` — Partial match
7. `test_all_valid_classifications_covered` — All 4 classes are valid
8. `test_confidence_always_float_in_range` — [0.0, 1.0] invariant
9. `test_empty_titles_return_unrelated` — Edge: empty string
10. `test_daemon_pattern_no_attribute_error` — Simulates fixed daemon pattern
11. `test_daemon_pattern_detects_true_duplicate` — No false negatives
12. `test_daemon_pattern_no_false_positive` — No false positives
13. `test_orchestrator_pattern_no_attribute_error` — Simulates fixed orchestrator
14. `test_identical_titles_high_confidence` — High confidence invariant
15. `test_zero_price_handled_gracefully` — Division-by-zero guard

**Result: 15/15 PASS**

---

## Changes NOT Made

- Did NOT change `evaluate_match_confidence()` return type (tuple is the correct contract)
- Did NOT add a dict wrapper
- Did NOT refactor the matcher class
- Did NOT modify any other files
- Did NOT commit or push
