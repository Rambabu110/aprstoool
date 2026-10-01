# 07 — PROVENANCE AUDIT & TRACEABILITY
**Date:** 2026-10-01  
**Auditor:** Antigravity Forensic QA Specialist  

---

## 1. Provenance Implementation Quality (In-Memory Layer)

In `core/research_sources/provenance.py`:
- `ProvenanceTracker.create_provenance()` successfully generates:
  - `source`: Provider identifier
  - `retrieval_method`: Network transport protocol
  - `source_url`: URL of the observation
  - `retrieved_at`: UTC timestamp
  - `payload_sha256`: SHA-256 digest of the raw response payload
  - `proxy_used`: Boolean tracking proxy transport
  - `adapter_version`: Hardcoded adapter version string
  - `schema_version`: Data contract version
  - `tamper_sig`: 16-character cryptographic hash protecting against field manipulation
- Verified in `tests/test_research_sources.py`:
  - `test_evidence_normalizer_generates_valid_record` ✅ PASS
  - `test_provenance_tamper_detection` ✅ PASS

---

## 2. Traceability Across Architectural Boundaries

| Pipeline Stage | Provenance Status | Forensic Evidence |
|---|---|---|
| **1. Source Adapter** | ✅ **PRESERVED** | Constructed in adapter methods |
| **2. Evidence Normalizer**| ✅ **PRESERVED** | Stamped onto `NormalizedEvidence` |
| **3. Memory Registry** | ✅ **PRESERVED** | Available on `NormalizedEvidence` instances |
| **4. Database Persistence**| ❌ **LOST / DISCONNECTED** | Zero code exists to translate `NormalizedEvidence` into the existing SQLite `intelligence_evidence` schema |
| **5. Evidence Graph** | ❌ **LOST / DISCONNECTED** | `core/intelligence_engine.py` queries SQLite directly, never receiving `NormalizedEvidence` |
| **6. Product Intelligence**| ❌ **LOST / DISCONNECTED** | UI displays legacy database records; new provenance metadata is unreachable |

---

## 3. Disconnection Point Diagnosis

The exact location where provenance is lost is between `ResearchSourceRegistry` and `core/database.py`:
- `core/research_sources/registry.py` defines `sync_health_to_db()` (which writes only health telemetry), but has **no method** to persist `NormalizedEvidence` into the `intelligence_evidence` table.
- Consequently, all provenance data exists solely in transient process memory and is discarded when the Python process exits.
