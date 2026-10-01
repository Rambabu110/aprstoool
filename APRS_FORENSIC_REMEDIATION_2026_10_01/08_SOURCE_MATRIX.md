# 08 — RESEARCH SOURCE EVALUATION MATRIX
**Date:** 2026-10-01  
**Auditor:** Antigravity Data & Research Integration Engineer  
**System:** APRS V8 Universal Research Source Layer  

---

## 1. Comprehensive Source Evaluation Matrix

| # | Source Name | Signal Category | Protocol / Tech | Authentication | Rate / Free Limits | Output Evidence | Classification |
|---|---|---|---|---|---|---|---|
| 1 | **Trends-MCP** | `TREND`, `DEMAND` | MCP / JSON-RPC | `TRENDSMCP_API_KEY` (Bearer Token) | Free Tier (60 req/min) | Cross-platform search and trend velocity indices | **READY_WITH_CREDENTIAL** |
| 2 | **Amazon India** | `PRICE`, `COMPETITION` | Scraper / Decodo Proxy | `DECODO_AUTH` (HTTP Basic Proxy) | Proxy-budget bound (20 req/min) | Observed listing prices, ratings, review counts | **READY_WITH_CREDENTIAL** |
| 3 | **Google Trends** | `DEMAND`, `KEYWORD` | Public API / Pytrends | Public / None required | Soft IP throttling (25 req/min) | Search momentum (0–100 index), rising queries | **READY** |
| 4 | **Reddit** | `CUSTOMER_PAIN` | Public JSON Feed | Public / User-Agent | 30 req/min (Reddit API policy) | Customer defect complaints, negative sentiment | **READY** |
| 5 | **YouTube** | `ENGAGEMENT` | Google Data API v3 | `YOUTUBE_API_KEY` (Optional) | 10,000 units/day free tier | Creator coverage, video count, view velocity | **FREE_LIMITED** |
| 6 | **GDELT Project** | `NEWS`, `TREND` | GDELT 2.0 DOC API | Public / None required | Open access (30 req/min) | Global/national event frequency, news spikes | **READY** |
| 7 | **Scavio MCP** | `COMPETITION`, `PAIN` | MCP / REST API | `SCAVIO_API_KEY` (Bearer Token) | Free tier quota (30 req/min) | Competitor gap discovery, feature weaknesses | **READY_WITH_CREDENTIAL** |
| 8 | **TrendWatch** | `TREND` | Analytics Engine | Internal / Heuristic | Unlimited internal compute | Breakout acceleration, 7-day velocity delta | **READY** |
| 9 | **TikTok** | `ENGAGEMENT` | Creative Center API | Public / Optional token | Rate limited by endpoint | Hashtag view volume, viral momentum | **FREE_LIMITED** |
| 10 | **RivalSearch** | `COMPETITION` | SERP Aggregator | Multi-Engine Search | Search quota bound | Cross-channel rival product listings | **READY** |
| 11 | **TrendScope** | `TREND` (Composite) | Synthesizer | Multi-Adapter Feed | Internal orchestration | Synthesized cross-channel trend index | **READY** |

---

## 2. Classification Breakdown

- **READY (5 sources):** `Google Trends`, `Reddit`, `GDELT Project`, `TrendWatch`, `TrendScope` — fully operational with zero paid commercial blockers.
- **READY_WITH_CREDENTIAL (3 sources):** `Trends-MCP` (configured with live key), `Scavio MCP` (configured with live key), `Amazon India` (configured with Decodo proxy).
- **FREE_LIMITED (2 sources):** `YouTube` (Google Cloud quota bound), `TikTok` (public endpoint throttling).
- **DUPLICATE / REDUNDANT (0 sources):** Each adapter maps to a distinct vector in the Evidence Graph.
