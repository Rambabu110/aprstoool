# APRS — EXTERNAL API & INTEGRATION AUDIT

**Audit Date:** September 2026  
**Auditor:** Principal API & Security Auditor  
**System:** APRS — Autonomous Product Research System

---

## 1. External API Inventory & Endpoint Analysis

The APRS system interacts with the following external APIs and remote services:

| Service / API | Base URL / Endpoint | Protocol & Client | Auth Mechanism | Purpose in APRS |
|---|---|---|---|---|
| **NVIDIA NIM API** | `https://integrate.api.nvidia.com/v1/chat/completions` | HTTPS POST (`openai` / `requests`) | Bearer Token (`NIM_API_KEY_1..3`) | Arbiter multi-agent voting, sentiment analysis, intelligence reasoning |
| **Keepa API** | `https://api.keepa.com/product` | HTTPS GET (`requests`) | Query Param `key=KEEPA_API_KEY` | Historical BSR, buy box price fluctuations, sales velocity |
| **Amazon E-Commerce** | `https://www.amazon.in/dp/{asin}` | HTTPS via Playwright Chromium | Session Cookies / User-Agent | Live price, review count, rating, customer review text |
| **IndiaMART Sourcing** | `https://dir.indiamart.com/` | HTTPS via Playwright Chromium | Headless browser session | Domestic wholesale FOB pricing, supplier contact data |
| **Alibaba Sourcing** | `https://www.alibaba.com/trade/search` | HTTPS via Playwright Chromium | Headless browser session | Global supplier FOB pricing, MOQ tiers, manufacturer badges |
| **Shopify Admin (V8)** | `https://{shop}.myshopify.com/admin/api/2024-01/orders.json` | HTTPS GET (`requests`) | Access Token `X-Shopify-Access-Token` | V8 Real-world post-launch sales outcomes ingestion |
| **Amazon SP-API (V8)** | `https://sellingpartnerapi-eu.amazon.com/reports/2021-06-30/reports` | HTTPS POST/GET (`requests`) | LWA Access Token & AWS IAM SigV4 | V8 Amazon Seller Central settlement & orders ingestion |

---

## 2. API Key Management & Security Review

A thorough static and dynamic credential audit was performed across the codebase:

1. **Zero Hardcoded Secrets in Source Code:**  
   - Scanned all `.py` files in `core/`, `web/`, `tools/`, and `tests/`.  
   - Zero production API keys, bearer tokens, or private secrets were found hardcoded in source code.
   - All keys are loaded strictly via `os.getenv()` or `python-dotenv` from `.env`.

2. **UI & Telemetry Redaction:**  
   - The Streamlit UI sidebar and settings tabs display masked credentials (e.g., `nvapi-***...` or `keepa-***...`).
   - Browser console logs and server stdout logs do not print raw authorization headers or query parameters containing keys.

3. **Key Rotation & Multi-Key Support:**  
   - `core/supervisor.py` and `core/intelligence_engine.py` implement round-robin key rotation across `NIM_API_KEY_1`, `NIM_API_KEY_2`, and `NIM_API_KEY_3`.
   - When a 429 (Rate Limit Exceeded) error occurs on one NIM key, the client automatically fails over to the next key.

---

## 3. Resilience, Caching & Failure Handling

| Service | Timeout Config | Retry / Fallback Strategy | Caching Layer |
|---|---|---|---|
| **NVIDIA NIM** | 30s timeout | 3 retries with exponential backoff; automatic key rotation on 429; deterministic fallback heuristics if all keys fail. | In-memory cache for repeated prompts within single research run. |
| **Keepa API** | 15s timeout | Token bucket throttling check before request; falls back to cached SQLite Keepa records if tokens exhausted. | `daily_snapshots` and `scraped_listings` tables cache historical curves. |
| **Playwright Web Scraping** | 20s page timeout | Headless retry with random user-agent rotation; DOM waiting for specific selectors before scrape failure. | Raw HTML extracts cached in `data/` scratch directory. |
| **V8 Outcome Adapters** | 45s API timeout | Validation pass before normalization; fails gracefully to manual CSV import if external credentials invalid. | Idempotent storage in `product_outcomes` with `source_record_id` uniqueness. |

---

## 4. API Governance & Recommendations

1. **Keepa Token Monitoring:** The Keepa client should continue enforcing token conservation to avoid unexpected throttling during large multi-product batch runs.
2. **Local LLM Drop-in Support:** Because the LLM client utilizes the standard OpenAI interface, developers can seamlessly redirect `base_url` to `http://localhost:11434/v1` (Ollama) without modifying business logic.
3. **Outcome Ingestion Sandboxing:** The V8 `dry_run=True` parameter in all outcome adapters successfully prevents write side-effects until human verification is complete.
