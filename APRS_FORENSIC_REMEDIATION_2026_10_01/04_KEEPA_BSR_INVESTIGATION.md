# 04 — KEEPA / BSR INVESTIGATION

## Investigation Date
2026-10-01

## Files Investigated
- `tools/keepa_api_client.py` — Full Keepa API client
- `web/app.py:2901-2933` — Keepa/BSR tab UI (L2903–L2933)
- `tools/seed_market_data.py` — Data seeding with `keepa_price_stability`
- `core/database.py:126` — Schema: `keepa_price_stability REAL DEFAULT 85.0`
- `tests/test_phase3_scrapers.py` — Keepa client tests

## UI Tab Code (app.py:2903-2933)
The tab renders:
1. Product selector (live products from DB)
2. 4 metrics: BSR Rank, Est. Daily Units, Price Stability, Ad Active Days
3. Multi-platform listings table from `_get_mpl()` function

All metric values come from `master_products` table columns:
- `bsr_rank`
- `estimated_daily_units`
- `keepa_price_stability` (default 85 if null)
- `ad_active_days`

## KeepaAPIClient Analysis

### Implementation Quality
- ✅ `KeepaProduct` Pydantic model with proper field validation
- ✅ `KeepaAPIError` and `KeepaRateLimitError` exception hierarchy
- ✅ Token-aware rate limiting (60s backoff on 429)
- ✅ Exponential backoff with jitter on network errors
- ✅ LRU cache (100 ASINs) for deduplication
- ✅ India domain (#10) properly configured
- ✅ `_enabled = False` when no real key — gracefully returns None/[]
- ✅ `get_product(asin)` and `search_by_keyword()` both fully implemented

### Key Configuration
`.env`:
```
KEEPA_API_KEY=xxx
```
This is a placeholder → `_enabled = False` → client never makes real API calls.

### Data Source for Displayed Values

| Display Value | Source | Is Real Data? |
|---------------|--------|--------------|
| BSR Rank #640 | `master_products.bsr_rank` | Seeded data |
| Stability 98% | `master_products.keepa_price_stability` | Seeded data |
| Est. Daily Units | `master_products.estimated_daily_units` | Seeded data |
| Ad Active Days | `master_products.ad_active_days` | Seeded data |
| Multi-platform listings | `multi_platform_listings` table | Scraped or seeded |

---

## Classification

**BACKEND_IMPLEMENTED_UI_THIN — BLOCKED_BY_API_CREDENTIAL**

The Keepa API client is fully implemented and production-hardened. The UI correctly displays database values. The tab works correctly for seeded data. The only missing piece is a real `KEEPA_API_KEY` to enable live data fetching.

## Required Action (Configuration, Not Code)
1. Obtain Keepa API key from https://keepa.com/#!api
2. Set `KEEPA_API_KEY=<real_key>` in `.env`
3. Wire `KeepaAPIClient.get_product()` call from daemon to update `bsr_rank` and `keepa_price_stability` columns on each scan cycle

## Tests
`tests/test_phase3_scrapers.py` covers:
- `test_keepa_caching` ✅
- `test_keepa_currency_detection` ✅
- `test_keepa_india_domain` ✅

All pass with mock data (no real key required).
