# 06 / 07 — FORENSIC DATA INTEGRITY CHECK
**Date:** 2026-10-01  
**Target Database:** `d:\tools\APRS\data\research_engine.db` (Primary SSOT SQLite DB)  
**Schema Verification:** 37 active tables  

---

## 1. Executive Summary

A comprehensive, non-destructive audit of the APRS database was performed following the remediation of the product matcher tuple unpacking bug in `core/background_daemon.py` and `core/orchestrator.py`.

| Dimension | Checked Metric | Finding | Impact |
|---|---|---|---|
| **Products Volume** | `master_products` | 471 total products | Normal operating scale |
| **Duplicate Names** | Name clustering (`HAVING count > 1`) | 17 titles duplicated (38 rows) | **Direct artifact of Daemon Bug** |
| **Product ID Collisions**| `product_id` uniqueness | 0 duplicate IDs | Primary key constraint intact |
| **Intelligence Coverage** | `product_intelligence` | 394 evaluation dossiers | 0 duplicate dossiers |
| **Evidence Volume** | `intelligence_evidence` | 6,988 evidence records | Repeated scans inserted duplicate signals |
| **Orphaned Intelligence** | `product_id NOT IN master_products`| 0 orphans | Foreign key integrity maintained |
| **Orphaned Listings** | `multi_platform_listings` orphans | 0 orphans | Foreign key integrity maintained |
| **Orphaned Evidence** | `intelligence_evidence` orphans | 0 orphans | Foreign key integrity maintained |
| **Critical NULLs** | `name`, `planned_msrp`, `status` | 0 unexpected NULLs | Schema integrity maintained |

---

## 2. Root Cause Analysis of Duplicate Ingestion

Prior to the fix applied in `Fix 1A` and `Fix 1B`:
```python
match = matcher.evaluate_match_confidence(pname, ep.get("name", ""), ...)
if match.get("classification") == "EXACT_MATCH":  # Crashed with AttributeError
```
Because `evaluate_match_confidence()` returned a `Tuple[str, float]`, calling `.get()` raised an uncaught `AttributeError` inside the deduplication evaluation loop. Consequently:
1. The daemon aborted the deduplication check prematurely.
2. The product was never classified as `EXACT_MATCH`.
3. The candidate was ingested as a new unique product, generating duplicate rows for the same external product (e.g., *Amazon Basics Smart A19 LED Light Bulb* had 2 rows, *Govee Smart Light Bulbs* had 2 rows).
4. Subsequent scan cycles also inserted fresh `intelligence_evidence` rows for the same products.

---

## 3. Data Integrity & Safety Policy

In strict accordance with the Global Safety Rules:
- **No data was deleted.**
- **No destructive cleanup script was executed.**
- The fix in `core/background_daemon.py` ensures that all future background scan cycles unpack `classification, _confidence` correctly and accurately deduplicate existing products, stopping the generation of new duplicate rows.

---

## 4. Remediation Status

- **Defect:** Duplicate generation due to matcher exception
- **Status:** **RESOLVED AT ENGINE LEVEL**
- **Test Verification:** Covered by 15 regression tests in `tests/test_daemon_matcher_regression.py` ensuring zero `AttributeError` and exact match detection.
