# 10 — FREE & PUBLIC API MATRIX
**Date:** 2026-10-01  
**Target:** APRS Continuous Autonomous Research Swarm  

---

## 1. Zero-Cost / Free-Tier Provider Capabilities

| Provider | Free Tier Allowance | Refresh Frequency | Anti-Bot Sensitivity | Feasibility for Background Daemon |
|---|---|---|---|---|
| **Google Trends (Realtime)** | Unlimited (public rate limit) | Real-time / Hourly | Medium (requires IP backoff) | **HIGH** — Ideal for seed discovery & demand confirmation |
| **GDELT 2.0 DOC API** | Unlimited (public open access) | 15-minute rolling updates | Low (welcomes bots) | **VERY HIGH** — Perfect for news & macro sentiment monitoring |
| **Reddit JSON API** | Unlimited public read | Real-time discussions | Medium (enforces User-Agent) | **HIGH** — Best for customer pain & complaint harvesting |
| **YouTube Data v3** | 10,000 units/day (~100 searches) | Real-time | Low (API key bound) | **MEDIUM** — Use selectively on shortlisted products |
| **Trends-MCP** | 60 req/min free tier | Hourly aggregated | Low (API key authenticated) | **HIGH** — Comprehensive multi-channel trend validation |
| **Scavio MCP** | 30 req/min free tier | On-demand research | Low (API key authenticated) | **HIGH** — Deep competitor gap extraction |
| **TrendWatch** | Internal compute | Continuous / Instant | None | **MAXIMUM** — Velocity & early-warning detection |
| **TrendScope** | Internal compute | Continuous / Instant | None | **MAXIMUM** — Composite multi-channel synthesis |

---

## 2. Recommended Daemon Ingestion Cadence

To guarantee zero rate-limit lockouts:
1. **Tier 1 (Continuous Hourly):** Google Trends, GDELT, TrendWatch.
2. **Tier 2 (Batch Daily Scan):** Trends-MCP, Scavio MCP, Reddit.
3. **Tier 3 (On-Demand / Shortlist Triggered):** YouTube, Amazon India Deep Scrape.
