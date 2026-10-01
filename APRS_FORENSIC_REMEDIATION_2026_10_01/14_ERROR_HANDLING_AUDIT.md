# 14 — ERROR HANDLING & RESILIENCE AUDIT
**Date:** 2026-10-01  
**Target:** APRS V8 Research Adapter Layer  

---

## 1. Provider Isolation & Failure Containment

A fundamental design requirement of the APRS Universal Research Source Layer is **Strict Failure Isolation**:
> *“Do not allow one external source failure to crash APRS.”*

### Containment Mechanisms Implemented:

1. **Adapter-Level Exception Quarantine:**
   - In `BaseResearchSourceAdapter.fetch_signals()`, every network interaction is wrapped in a strict `try...except` block.
   - Any network timeout, DNS resolution failure, SSL error, or malformed JSON payload increments the adapter's `consecutive_errors` counter and returns `[]`.
   - No exception is propagated to callers or web presentation threads.

2. **Registry Parallel Isolation:**
   - In `ResearchSourceRegistry.fetch_all_signals()`, adapters are dispatched via a `ThreadPoolExecutor`.
   - Each thread executes independently; if an individual worker raises a critical failure, the registry captures it, logs telemetry, and aggregates results from all surviving adapters.
   - Tested and verified via `test_registry_failure_isolation` in `tests/test_research_sources.py`.

---

## 2. Rate Limiting & Backoff Architecture

| Layer | Mechanism | Configuration | Behavior on Exceeded Quota |
|---|---|---|---|
| **Rate Limiter** | Token Bucket (`RateLimiter`) | Configurable per adapter (20–60 RPM) | Delays request execution to comply with rate limits |
| **Retry Policy** | Exponential Backoff (`RetryPolicy`) | Max 2 retries, base 1.5x, max 10.0s, jitter | Prevents thundering herd on transient upstream outages |
| **HTTP 429 Guard**| Status Code Detection | Catches 429 response | Triggers immediate circuit backoff and logs degraded status |
| **Health Telemetry**| `SourceHealth` Model | Consecutive error threshold: 5 | Flips adapter status from `ONLINE` to `DEGRADED` |

---

## 3. Resilience Test Results

| Test Case | Scenario | Expected Outcome | Verified Result |
|---|---|---|---|
| `test_timeout_isolated_without_crashing` | Upstream provider hangs > 10s | Returns `[]`, increments error counter, app survives | ✅ **PASS** |
| `test_rate_limit_429_handling` | Provider returns HTTP 429 | Returns `[]`, updates telemetry, no unhandled crash | ✅ **PASS** |
| `test_provider_server_error_500_handling` | Upstream provider returns HTTP 500 | Returns `[]`, marks health degraded | ✅ **PASS** |
| `test_malformed_response_handling` | Provider returns broken / unexpected JSON | Safely discards invalid items without crashing | ✅ **PASS** |
