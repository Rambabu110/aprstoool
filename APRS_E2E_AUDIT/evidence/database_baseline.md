# DATABASE FORENSIC BASELINE AUDIT

Database File: `D:\tools\APRS\data\research_engine.db`

File Size: 5496832 bytes

Total Tables Found: 37

## Table Inventory & Row Counts

| Table Name | Row Count | Primary Key | Column Count | Foreign Keys | Category / Purpose |
|---|---|---|---|---|---|
| `ai_supervisor_logs` | 5527 | `log_id` | 6 | None | System / Utility |
| `ai_task_improvements` | 0 | `improvement_id` | 11 | None | System / Utility |
| `arbiter_decision_log` | 0 | `decision_id` | 7 | 1 FK(s) | V6 Gated Research Pipeline |
| `daily_snapshots` | 210 | `snapshot_id` | 8 | 1 FK(s) | System / Utility |
| `data_conflicts` | 26 | `conflict_id` | 13 | 1 FK(s) | V7 Autonomous Intelligence |
| `decision_ledger` | 0 | `decision_id` | 18 | 2 FK(s) | V8 Outcome & Learning |
| `defect_clusters` | 8 | `cluster_id` | 13 | 1 FK(s) | V7 Autonomous Intelligence |
| `discovered_sources` | 58 | `source_id` | 14 | None | System / Utility |
| `dynamic_niches` | 106 | `niche_id` | 12 | None | V6 Gated Research Pipeline |
| `dynamic_seed_keywords` | 231 | `seed_id` | 10 | None | V6 Gated Research Pipeline |
| `economics_assessments` | 21 | `assessment_id` | 23 | 1 FK(s) | V6 Gated Research Pipeline |
| `intelligence_evidence` | 2041 | `evidence_id` | 10 | 1 FK(s) | V7 Autonomous Intelligence |
| `intelligence_timeline` | 552 | `timeline_id` | 7 | 1 FK(s) | V7 Autonomous Intelligence |
| `launchpad_items` | 7 | `item_id` | 14 | 1 FK(s) | V6 Gated Research Pipeline |
| `learning_bias_summaries` | 0 | `bias_summary_id` | 19 | None | V8 Outcome & Learning |
| `learning_recommendations` | 0 | `recommendation_id` | 16 | 1 FK(s) | V8 Outcome & Learning |
| `marketplace_config` | 6 | `config_id` | 31 | None | System / Utility |
| `master_products` | 225 | `product_id` | 42 | None | V6 Gated Research Pipeline |
| `meeting_audit_log` | 6 | `message_id` | 8 | None | System / Utility |
| `multi_platform_listings` | 65 | `listing_id` | 12 | 1 FK(s) | V6 Gated Research Pipeline |
| `negative_findings` | 0 | `finding_id` | 10 | None | System / Utility |
| `opportunity_alerts` | 81 | `alert_id` | 11 | 1 FK(s) | V7 Autonomous Intelligence |
| `outcome_corrections_log` | 0 | `correction_id` | 10 | 3 FK(s) | V8 Outcome & Learning |
| `prediction_calibrations` | 0 | `calibration_id` | 33 | 3 FK(s) | V8 Outcome & Learning |
| `product_gate_progress` | 1350 | `progress_id` | 9 | 1 FK(s) | V6 Gated Research Pipeline |
| `product_intelligence` | 59 | `intelligence_id` | 17 | 1 FK(s) | V7 Autonomous Intelligence |
| `product_outcomes` | 0 | `outcome_id` | 25 | 2 FK(s) | V8 Outcome & Learning |
| `product_suppliers` | 226 | `supplier_id` | 12 | 1 FK(s) | V6 Gated Research Pipeline |
| `product_watchlist` | 1 | `watchlist_id` | 7 | 1 FK(s) | V7 Autonomous Intelligence |
| `research_runs` | 2 | `research_run_id` | 11 | None | V7 Autonomous Intelligence |
| `scraped_listings` | 2227 | `listing_id` | 20 | 1 FK(s) | V6 Gated Research Pipeline |
| `scraper_validations` | 2 | `validation_id` | 14 | None | System / Utility |
| `source_health` | 11 | `source_id` | 9 | None | V7 Autonomous Intelligence |
| `sqlite_sequence` | 23 | `None` | 2 | None | System / Utility |
| `swarm_audit_log` | 0 | `audit_id` | 8 | None | System / Utility |
| `trend_signals` | 252 | `signal_id` | 11 | None | System / Utility |
| `users` | 0 | `user_id` | 10 | None | System / Utility |

## Foreign Key Check
`PRAGMA foreign_key_check;` returned: **0 violations**

## SQLite Integrity Check
`PRAGMA integrity_check;` returned: **ok**

## Database Triggers (1)

- **trg_decision_ledger_immutable** on table `decision_ledger`:
  ```sql
  CREATE TRIGGER trg_decision_ledger_immutable
        BEFORE UPDATE ON decision_ledger
        BEGIN
            SELECT RAISE(ABORT, 'decision_ledger records are immutable and cannot be updated');
        END
  ```
