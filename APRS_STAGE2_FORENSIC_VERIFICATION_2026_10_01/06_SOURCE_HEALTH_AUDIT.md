# 06 — SOURCE HEALTH AUDIT: REAL VS. INSTANTIATION-DERIVED
**Date:** 2026-10-01  
**Auditor:** Antigravity Telemetry Specialist  

---

## 1. Source Health Calculation Mechanism

In `core/research_sources/base.py:health_check()`:
```python
def health_check(self) -> SourceHealth:
    with self._lock:
        avg_lat = (self.total_latency_ms / max(1, self.total_calls))
        is_healthy = self.consecutive_errors < 5 and self.is_available()
        status_msg = "ONLINE" if is_healthy else (
            f"UNAVAILABLE (Missing Credential)" if not self.is_available() else f"DEGRADED ({self.consecutive_errors} errors)"
        )
        return SourceHealth(...)
```

---

## 2. Forensic Flaws in the Health Implementation

A forensic examination of the health logic reveals that the "ONLINE" status reported in Stage 2 is **INSTANTIATION-DERIVED**, rather than probe-verified:

1. **Zero-Call False "ONLINE":**
   - When an adapter is instantiated with a valid/non-empty environment variable (e.g. `TrendsMCPAdapter`), `is_available()` returns `True`.
   - `consecutive_errors` starts at `0`.
   - Therefore, `health_check()` reports `ONLINE` immediately **without ever sending a packet to the provider's server**.
   - An unreachable or offline provider with a configured credential is reported as `ONLINE`.

2. **Silent Failure Immunity (Reddit):**
   - In `core/research_sources/reddit.py`, the network response code is checked via `if resp.status_code == 200:`.
   - When Reddit returns HTTP 403 Forbidden, no exception is raised, and `record_error()` is never invoked.
   - `consecutive_errors` remains `0`.
   - The adapter continues to report `ONLINE` while actively blocked by Reddit.

3. **High Error Tolerance Threshold (GDELT):**
   - The threshold for flipping from `ONLINE` to `DEGRADED` is `consecutive_errors >= 5`.
   - When GDELT timed out on a live request, `consecutive_errors` became `1`.
   - Because `1 < 5`, `health_check()` continued to report `ONLINE`.

---

## 3. Classification of Source Health

| Adapter | Reported Status | Actual State | True Health Classification |
|---|---|---|---|
| `trends_mcp` | `ONLINE` | Credential present; unprobed | **UNPROBED (Instantiation-Derived)** |
| `scavio_mcp` | `ONLINE` | Credential present; unprobed | **UNPROBED (Instantiation-Derived)** |
| `amazon_india` | `ONLINE` | Proxy configured; unprobed | **UNPROBED (Instantiation-Derived)** |
| `google_trends`| `ONLINE` | Throws `ImportError` on live call | **BROKEN / SILENT_FALLBACK** |
| `reddit` | `ONLINE` | Blocked with HTTP 403 Forbidden | **BLOCKED (False ONLINE)** |
| `gdelt` | `ONLINE` | HTTPS Read Timeout (>8s) | **DEGRADED (False ONLINE)** |
| `youtube` | `ONLINE` | Synthetic estimate fallback | **SYNTHETIC ONLY** |
| `tiktok` | `ONLINE` | Synthetic hashtag estimate | **SYNTHETIC ONLY** |
| `trendwatch` | `ONLINE` | Internal velocity calculation | **INTERNAL ONLY** |
| `rivalsearch` | `ONLINE` | Simulated SERP | **SYNTHETIC ONLY** |
| `trendscope` | `ONLINE` | Internal composite weighting | **INTERNAL ONLY** |

> **Conclusion:** None of the 11 adapters have genuine, probe-verified active health monitors. The "11/11 sources online" finding was an artifact of constructor defaults.
