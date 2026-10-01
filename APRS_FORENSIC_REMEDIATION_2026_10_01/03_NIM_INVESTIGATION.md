# 03 — NIM CLUSTER INVESTIGATION

## Investigation Date
2026-10-01

## File Locations
- `models/nim_cluster.py` — SupremeNIMCluster, key rotation, fallback
- `models/nim_swarm_orchestrator.py` — (not separately investigated, uses cluster)
- `tools/ai_supervisor.py` — calls cluster
- `config/settings.py` — NIM_API_KEYS, NIM_BASE_URL, NIM_MODELS
- `.env` — actual key values

## .env Key Status
```
NIM_API_KEY_1=nvapi-YUxOBz4Du4Pj11...   ← truncated with "..."
NIM_API_KEY_2=nvapi-O3RgvFCETTumh1...   ← truncated with "..."
NIM_API_KEY_3=nvapi-JYLtvY2ZU-SuOZ...   ← truncated with "..."
```
> **Note:** The `...` is literally in the file — these appear to be placeholder/truncated keys. Real `nvapi-` keys are 64+ characters. These are broken.

## Code Logic Analysis

### Key Pool Loading (nim_cluster.py:72-76)
```python
self.keys = [k for k in [
    os.getenv(f"NIM_API_KEY_{i}", "") for i in range(1, 11)
] if k and k.strip()] or [k for k in NIM_API_KEYS if k.strip()]
```
✅ Logic is correct — loads up to 10 keys, falls back to config.

### Pytest Safety (nim_cluster.py:75-76)
```python
if not self.keys and ("PYTEST_CURRENT_TEST" in os.environ or "pytest" in sys.modules):
    self.keys = ["mock-nim-key-1", "mock-nim-key-2", "mock-nim-key-3"]
```
✅ Tests use mock keys — correct behavior.

### Retry/Failover (nim_cluster.py:126-170)
- Iterates through all keys in order
- HTTP errors → logs `last_error`, continues to next key
- Network exceptions → caught, continues to next key
- ✅ No resource leak, no unhandled exception

### Exhaustion Behavior (nim_cluster.py:172-177)
```python
raise NIMClusterExhausted(
    f"All NIM API keys exhausted. Last error: {last_error}. "
    f"Check key validity at console.api.nvidia.com"
)
```
✅ Raises clearly, never silently fabricates.

### Fallback in multi_agent_peer_review (nim_cluster.py:236-250)
If NIMClusterExhausted is caught by caller, a deterministic heuristic fallback is used.
✅ Heuristic is label-preserving and not fabricated as AI output.

### Cooldown / Backoff
- No per-key cooldown beyond Python exception handling
- Once all 3 keys fail, no exponential retry at cluster level
- This is acceptable — caller decides retry policy

---

## Classification

| Aspect | Finding |
|--------|---------|
| Code correctness | ✅ CORRECT |
| Key pool loading | ✅ CORRECT |
| Failover logic | ✅ CORRECT |
| Test isolation | ✅ CORRECT |
| Fallback on exhaustion | ✅ CORRECT |
| Actual key values | ❌ BROKEN — `.env` contains truncated/placeholder keys |
| Rate limiting | ⚠️ None at cluster level — ok for low volume |

## Verdict
**CREDENTIAL/QUOTA ISSUE — Not a software defect.**

The NIMClusterExhausted error in production is caused by invalid/truncated API keys in `.env`, not by a code bug. The key rotation, retry, and fallback logic is correctly implemented.

## Required Action (Configuration, Not Code)
Replace `.env` NIM keys with valid nvapi-* keys from https://console.api.nvidia.com
No code changes required.

## Regression Tests
Existing tests in `tests/test_phase4_nim.py` cover:
- `test_all_keys_exhausted_raises` ✅
- `test_fallback_caching` ✅
- `test_fallback_is_cached` ✅
- `test_model_name_validation` ✅
- `test_arbiter_prompt_no_example` ✅
