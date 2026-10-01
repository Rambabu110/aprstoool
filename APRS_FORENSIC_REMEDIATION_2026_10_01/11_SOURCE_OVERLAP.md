# 11 — RESEARCH SOURCE OVERLAP & DEDUPLICATION AUDIT
**Date:** 2026-10-01  
**Target:** APRS V8 Research Pipeline  

---

## 1. Cross-Source Signal Overlap Analysis

| Research Vector | Overlapping Sources | Distinguishing Provenance / Value Add | Deduplication & Handling Policy |
|---|---|---|---|
| **Search Demand** | `google_trends` vs `trends_mcp_google` | `google_trends` provides direct geographic breakdown; `trends_mcp` provides cross-platform normalized score | Both stored as independent observations; conflicts flagged if divergence > 35%. |
| **Marketplace Listings** | `amazon_india` vs `trends_mcp_amazon` | `amazon_india` provides live scraped pricing and review counts via Decodo proxy; `trends_mcp` provides high-level category trend velocity | Price and review counts stored under `SignalType.PRICE` and `COMPETITION`; trend score stored under `TREND`. |
| **Customer Pain Points** | `reddit` vs `scavio_mcp` | `reddit` captures direct user complaints and defect discussions; `scavio_mcp` extracts structured competitor product flaws | Both feed into the Customer Pain Map and Kill Switch verification with separate source tags. |
| **Creator / Social Signals**| `youtube` vs `tiktok` | `youtube` measures long-form review depth; `tiktok` measures viral hashtag velocity | Distinct signal types: long-form review count vs short-form viral views. |

---

## 2. Idempotency & Deduplication Engine

The APRS Research Source Layer prevents evidence duplication through deterministic hashing in `core/research_sources/base.py`:
```python
def generate_dedup_hash(self) -> str:
    payload = f"{self.source}|{self.entity}|{self.signal_type}|{self.observed_at}|{self.value}"
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]
```
- `ProvenanceTracker.check_duplicate()` tracks seen hashes per ingestion batch.
- Repeated runs within the same observation window do not inflate evidence volume.
- Zero synthetic duplicate rows are inserted into the database.
