# 09 — API REQUIREMENTS & CREDENTIAL ARCHITECTURE
**Date:** 2026-10-01  
**Target:** APRS V8 Research Integrations  

---

## 1. Environment Variable Architecture

All sensitive API keys and proxy credentials are strictly isolated into the local `.env` configuration, referenced through `os.getenv()`, and never committed to version control.

| Environment Variable | Target Service | Auth Scheme | Default / Base URL | Required Headers |
|---|---|---|---|---|
| `TRENDSMCP_API_KEY` | Trends-MCP Server | Bearer Token | `https://api.trendsmcp.com/v1` | `Authorization: Bearer <key>` |
| `SCAVIO_API_KEY` | Scavio MCP | Bearer Token | `https://api.scavio.ai/v1` | `Authorization: Bearer <key>` |
| `DECODO_AUTH` | Decodo Residential Proxy | HTTP Basic Auth | `proxy.decodo.io:8080` | `Proxy-Authorization: Basic <b64>` |
| `YOUTUBE_API_KEY` | YouTube Data API v3 | Query Param Key | `https://www.googleapis.com/youtube/v3` | None (Key in query param) |
| `KEEPA_API_KEY` | Keepa API (Market data) | Query Param Key | `https://api.keepa.com` | None (Key in query param) |

---

## 2. Decodo Proxy Infrastructure Contract

In strict compliance with the **Global Data Provenance Rules**:
- **Proxy is Infrastructure, NOT Evidence:** The Decodo proxy provides network routing to prevent IP throttling and geo-blocking during Amazon.in listing inspection.
- Proxy presence is stamped into the provenance dictionary (`proxy_used: True`, `retrieval_method: SCRAPER_PROXY`).
- Scraped listing information (Price, Rating, Review Count) is labeled `EvidenceType.OBSERVED_SIGNAL` and never converted into speculative "verified sales."

---

## 3. Rate Limit & Throttling Parameters

| Source | Requests / Min | Timeout (s) | Max Retries | Backoff Strategy |
|---|---|---|---|---|
| `trends_mcp` | 60 | 8.0s | 2 | Exponential backoff (factor 1.5) with random jitter |
| `scavio_mcp` | 30 | 10.0s | 2 | Exponential backoff (factor 1.5) with random jitter |
| `amazon_india` | 20 | 12.0s | 2 | Decodo proxy rotation on 403/429 |
| `google_trends` | 25 | 10.0s | 2 | Progressive sleep delay on 429 |
| `reddit` | 30 | 8.0s | 2 | Respect standard User-Agent header rate limit |
| `gdelt` | 30 | 8.0s | 2 | Open public throttling |
