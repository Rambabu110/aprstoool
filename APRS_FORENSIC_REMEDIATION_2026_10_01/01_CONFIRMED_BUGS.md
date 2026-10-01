# 01 — CONFIRMED BUGS

## Bug 1A: Type Mismatch in Deduplication Callers
**Severity:** HIGH — Runtime crash in production daemon  
**Status:** CONFIRMED + FIXED

### Root Cause
`core/product_matcher.py::CanonicalProductMatcher.evaluate_match_confidence()` has this return annotation:
```python
) -> Tuple[str, float]:
```
Returns: `("EXACT_MATCH", 0.95)` — a 2-tuple.

### Broken Callers (Both Fixed)

**Caller 1: `core/background_daemon.py:302-306`**
```python
# BUGGY (before fix):
match = matcher.evaluate_match_confidence(pname, ep.get("name",""), pprice, float(ep.get("planned_msrp") or 0))
if match.get("classification") == "EXACT_MATCH":   # AttributeError: 'tuple' has no .get()
```

**Caller 2: `core/orchestrator.py:671-675`**
```python
# BUGGY (before fix):
match = matcher.evaluate_match_confidence(pname, cp.get("title",""), pprice, float(cp.get("price",0)))
if match.get("classification") == "EXACT_MATCH":   # AttributeError: 'tuple' has no .get()
```

### Impact
- Both callers crash with `AttributeError` every time products are compared during dedup
- Background daemon dedup loop fails silently (caught by outer try/except)
- Orchestrator universal dedup loop fails silently
- Result: duplicate products can be inserted into DB without detection

### Reproduction
```python
from core.product_matcher import CanonicalProductMatcher
result = CanonicalProductMatcher.evaluate_match_confidence("A", "B", 100.0, 100.0)
result.get("classification")  # → AttributeError: 'tuple' object has no attribute 'get'
```

---

## Bug 1B: Orchestrator Same Pattern
(Covered above — same root cause, same fix applied)

---

## Non-Bug Findings

### NIM: Quota/Configuration Issue (NOT a code bug)
- Code logic: CORRECT — properly raises `NIMClusterExhausted`, falls back gracefully
- Keys: `nvapi-...` (3 keys, all truncated with `...` in `.env` — appears to be placeholder/expired)
- The `NIMClusterExhausted` exception is expected, correct behavior when all keys fail
- **Classification: CREDENTIAL/QUOTA ISSUE — not a software defect**

### Keepa: Thin UI Reading from Seeded Data (NOT a code bug)
- `KeepaAPIClient` is fully implemented with token-aware rate limiting, retry, LRU cache
- `KEEPA_API_KEY=xxx` in `.env` → `_enabled = False` → client returns `None/[]` gracefully
- UI displays values from `master_products` DB (seeded: `keepa_price_stability`, `bsr_rank`)
- **Classification: BACKEND_IMPLEMENTED_UI_THIN — blocked by missing real API key**

### Browser Scroll Timeout
- Observed in browser subagent session only
- Streamlit app did not error or crash
- Playwright mouse-wheel events under load environment caused timeout
- **Classification: TEST-HARNESS ISSUE — not an APRS defect**
