"""
tests/test_aprs_v7_intelligence.py — Comprehensive Test Suite for APRS V7.

Validates:
- Database schema migrations, foreign keys, indexes, and cascades.
- 10-dimension scorecard generation and explainability panel.
- Opportunity Kill Switch (Demand, Competition, Economics, Sourcing, Pain, Marketplace failure tests).
- Counterfactual Economics (Base, Downside, Severe Downside, Upside, and break-evens).
- Trend Early-Warning System (Accelerating, Early Rise, Stable, Declining, Collapsing).
- Customer Pain Map and honest defect percentage distributions.
- Competitor Gap Detection (Price, Feature, Complaint, Availability gaps).
- Data Freshness and trust degradation.
- Multi-Source Conflict Detection and resolution.
- Alert Center and local-first Watchlist CRUD.
- War Room 2.0 and Disagreement Engine.
"""

import unittest
import os
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.database import (
    init_db, get_connection, save_product_intelligence, get_product_intelligence,
    record_intelligence_evidence, get_intelligence_evidence, create_opportunity_alert,
    get_active_alerts, dismiss_alert, add_to_watchlist, remove_from_watchlist,
    get_watchlist, is_in_watchlist, record_timeline_event, get_product_timeline,
    record_data_conflict, get_data_conflicts, resolve_data_conflict,
    start_research_run, complete_research_run, get_research_runs,
    update_source_health, get_source_health_summary
)
from core.economics_engine import Comprehensive15FactorEconomics
from core.intelligence_engine import AutonomousIntelligenceEngine


class TestAPRSV7Intelligence(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_v7_engine.db"
        os.environ["APRS_DB_PATH"] = str(self.db_path)
        init_db()
        self.conn = get_connection()

        # Insert a sample master product for foreign key relations
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO master_products (
                product_id, name, category, region, planned_msrp, landed_cogs,
                gross_margin_pct, estimated_cac, net_profit_pct, worst_case_stress_margin_pct,
                status, overall_score, consensus_status, first_discovered_date,
                last_evaluated_date, sourcing_cluster, bsr_rank, estimated_daily_units,
                trend_source, trend_confidence_score, factory_cogs
            ) VALUES (
                'TEST_V7_001', 'Ergonomic Desk Wedge Pillow', 'Office Wellness', 'India',
                1299.0, 380.0, 70.7, 180.0, 22.5, 14.0,
                'PASS', 86.5, 'CONSENSUS_PASS', date('now'),
                date('now'), 'Bhiwandi / Surat Hub', 1850, 35,
                'Google Trends & Amazon Movers', 88.0, 260.0
            )
        """)
        # Insert supplier
        cur.execute("""
            INSERT INTO product_suppliers (
                product_id, factory_name, fob_unit_price, moq_units
            ) VALUES ('TEST_V7_001', 'ComfortFoam Innovations', '₹260', 300)
        """)
        # Insert defect cluster
        cur.execute("""
            INSERT INTO defect_clusters (
                product_id, defect_category, defect_description, frequency_count, severity
            ) VALUES ('TEST_V7_001', 'Zipper Breakage', 'Zippers split after second wash', 28, 'HIGH')
        """)
        # Insert multi-platform listing
        cur.execute("""
            INSERT INTO multi_platform_listings (
                product_id, platform, title, price, rating, review_count, listing_url
            ) VALUES ('TEST_V7_001', 'amazon_in', 'Ergonomic Desk Wedge', 1299.0, 4.3, 450, 'https://amazon.in/dp/test')
        """)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    # ─────────────────────────────────────────────────────────────────────────
    # 1. DATABASE SCHEMA & INTEGRITY TESTS
    # ─────────────────────────────────────────────────────────────────────────

    def test_v7_tables_exist(self):
        cur = self.conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cur.fetchall()}
        required_v7 = {
            "product_intelligence", "intelligence_evidence", "opportunity_alerts",
            "product_watchlist", "research_runs", "source_health",
            "data_conflicts", "intelligence_timeline"
        }
        self.assertTrue(required_v7.issubset(tables), f"Missing tables: {required_v7 - tables}")

    def test_v7_foreign_keys_and_cascade(self):
        cur = self.conn.cursor()
        # Verify FK violations is 0
        cur.execute("PRAGMA foreign_key_check")
        self.assertEqual(len(cur.fetchall()), 0)

        # Verify cascade: deleting master product cleans product_intelligence
        save_product_intelligence(
            product_id="TEST_V7_001",
            opportunity_score=85.0,
            kill_status="SURVIVES"
        )
        cur.execute("SELECT COUNT(*) FROM product_intelligence WHERE product_id='TEST_V7_001'")
        self.assertEqual(cur.fetchone()[0], 1)

        # Delete product
        cur.execute("DELETE FROM master_products WHERE product_id='TEST_V7_001'")
        self.conn.commit()

        # Child record should be deleted via ON DELETE CASCADE
        cur.execute("SELECT COUNT(*) FROM product_intelligence WHERE product_id='TEST_V7_001'")
        self.assertEqual(cur.fetchone()[0], 0)

        # Ensure no FK violations remaining
        cur.execute("PRAGMA foreign_key_check")
        self.assertEqual(len(cur.fetchall()), 0)

    # ─────────────────────────────────────────────────────────────────────────
    # 2. OPPORTUNITY SCORECARD & INTELLIGENCE TESTS
    # ─────────────────────────────────────────────────────────────────────────

    def test_scorecard_generation_10_dimensions(self):
        dossier = AutonomousIntelligenceEngine.run_full_product_intelligence("TEST_V7_001")
        self.assertNotIn("error", dossier)
        scorecard = dossier.get("scorecard", {})

        # Must have composite score and confidence
        self.assertGreater(scorecard.get("composite_score", 0), 0)
        self.assertGreater(scorecard.get("overall_confidence", 0), 0)

        dims = scorecard.get("dimensions", {})
        expected_dims = {
            "demand_strength", "trend_strength", "competition_pressure",
            "customer_pain", "economic_viability", "sourcing_feasibility",
            "operational_risk", "market_saturation", "evidence_quality",
            "data_freshness"
        }
        self.assertEqual(set(dims.keys()), expected_dims)

        for dim_key, d in dims.items():
            self.assertIn("score", d)
            self.assertIn("confidence", d)
            self.assertIn("evidence_count", d)
            self.assertIn("freshness", d)
            self.assertIn("risk_flags", d)

    def test_evidence_tracking_and_missing_evidence(self):
        record_intelligence_evidence(
            product_id="TEST_V7_001",
            signal_type="demand",
            conclusion="Sales velocity verified at 35 units/day",
            evidence_status="VERIFIED",
            evidence_details=["BSR #1850 maintained for 30 consecutive days"],
            confidence=88.0,
            source="Amazon India Keepa"
        )
        ev_list = get_intelligence_evidence("TEST_V7_001", signal_type="demand")
        self.assertEqual(len(ev_list), 1)
        self.assertEqual(ev_list[0]["evidence_status"], "VERIFIED")
        self.assertEqual(ev_list[0]["confidence"], 88.0)

        # Test explainability missing evidence
        dossier = AutonomousIntelligenceEngine.run_full_product_intelligence("TEST_V7_001")
        exp = dossier.get("explainability", {})
        self.assertIn("positive_signals", exp)
        self.assertIn("negative_signals", exp)
        self.assertIn("missing_evidence", exp)

    # ─────────────────────────────────────────────────────────────────────────
    # 3. OPPORTUNITY KILL SWITCH TESTS
    # ─────────────────────────────────────────────────────────────────────────

    def test_kill_switch_survives_viable_product(self):
        dossier = AutonomousIntelligenceEngine.run_full_product_intelligence("TEST_V7_001")
        kill_res = dossier.get("kill_switch", {})
        self.assertEqual(kill_res.get("status"), "SURVIVES")
        self.assertEqual(len(kill_res.get("kill_reasons", [])), 0)

    def test_kill_switch_demand_failure(self):
        # Product with high BSR and 0 units
        bad_prod = {
            "product_id": "BAD_DEMAND_001",
            "bsr_rank": 45000,
            "estimated_daily_units": 0,
            "trend_confidence_score": 15.0,
            "planned_msrp": 500.0,
            "region": "India",
            "category": "General"
        }
        econ = Comprehensive15FactorEconomics.calculate_counterfactual_scenarios(fob_price=100.0, planned_msrp=500.0)
        res = AutonomousIntelligenceEngine.evaluate_kill_switch(bad_prod, [], [], [], econ)
        self.assertEqual(res["status"], "KILLED")
        self.assertTrue(any("Demand Collapse" in r or "Trend Decay" in r for r in res["kill_reasons"]))

    def test_kill_switch_economics_failure(self):
        # Product with negative contribution margin
        bad_econ = {
            "base_case": {"contribution_margin": -45.0, "contribution_margin_pct": -5.0},
            "downside_case": {"contribution_margin": -80.0}
        }
        res = AutonomousIntelligenceEngine.evaluate_kill_switch(
            {"product_id": "BAD_ECON_001", "planned_msrp": 500.0, "estimated_daily_units": 20},
            [], [{"frequency_count": 5}], [{"moq_units": 100}], bad_econ
        )
        self.assertEqual(res["status"], "KILLED")
        self.assertTrue(any("Economics Deficit" in r for r in res["kill_reasons"]))

    def test_kill_switch_insufficient_evidence(self):
        # Product with zero data points and healthy economics (or missing economics)
        empty_prod = {"product_id": "EMPTY_001", "planned_msrp": 800.0}
        econ = Comprehensive15FactorEconomics.calculate_counterfactual_scenarios(fob_price=50.0, planned_msrp=800.0)
        res = AutonomousIntelligenceEngine.evaluate_kill_switch(empty_prod, [], [], [], econ)
        self.assertEqual(res["status"], "INSUFFICIENT_EVIDENCE")
        self.assertGreaterEqual(len(res["missing_evidence"]), 2)

        # Also test with completely empty economics
        res_empty = AutonomousIntelligenceEngine.evaluate_kill_switch(empty_prod, [], [], [], {})
        self.assertEqual(res_empty["status"], "INSUFFICIENT_EVIDENCE")
        self.assertTrue(any("economics" in m.lower() for m in res_empty["missing_evidence"]))

    # ─────────────────────────────────────────────────────────────────────────
    # 4. COUNTERFACTUAL ECONOMICS TESTS
    # ─────────────────────────────────────────────────────────────────────────

    def test_counterfactual_economics_scenarios_and_breakevens(self):
        econ = Comprehensive15FactorEconomics.calculate_counterfactual_scenarios(
            fob_price=260.0,
            planned_msrp=1299.0,
            region="India",
            category="Office Wellness"
        )
        self.assertIn("base_case", econ)
        self.assertIn("downside_case", econ)
        self.assertIn("severe_downside_case", econ)
        self.assertIn("upside_case", econ)
        self.assertIn("break_evens", econ)

        base = econ["base_case"]
        down = econ["downside_case"]
        severe = econ["severe_downside_case"]
        up = econ["upside_case"]

        # Base case should be more profitable than downside
        self.assertGreater(base["contribution_margin"], down["contribution_margin"])
        self.assertGreater(down["contribution_margin"], severe["contribution_margin"])
        self.assertGreater(up["contribution_margin"], base["contribution_margin"])

        # Break-even values must be positive and realistic
        be = econ["break_evens"]
        self.assertGreater(be["break_even_selling_price"], 0)
        self.assertLess(be["break_even_selling_price"], 1299.0)
        self.assertGreater(be["break_even_cogs"], 260.0)
        self.assertGreater(be["maximum_acceptable_cac"], 0)
        self.assertGreater(be["maximum_acceptable_rto_pct"], 0)
        self.assertGreater(be["maximum_acceptable_return_rate_pct"], 0)

    # ─────────────────────────────────────────────────────────────────────────
    # 5. TREND & GAP DETECTION TESTS
    # ─────────────────────────────────────────────────────────────────────────

    def test_trend_early_warning_stages(self):
        # 1. Accelerating
        prod_accel = {"trend_confidence_score": 90.0, "ad_active_days": 15, "estimated_daily_units": 40}
        res_accel = AutonomousIntelligenceEngine.evaluate_trend_early_warning(prod_accel)
        self.assertEqual(res_accel["stage"], "ACCELERATING")
        self.assertGreater(res_accel["velocity"], 1.0)

        # 2. Declining
        prod_dec = {"trend_confidence_score": 35.0, "ad_active_days": 90, "estimated_daily_units": 5}
        res_dec = AutonomousIntelligenceEngine.evaluate_trend_early_warning(prod_dec)
        self.assertEqual(res_dec["stage"], "DECLINING")
        self.assertLess(res_dec["velocity"], 1.0)

    def test_customer_pain_map_no_fabrication(self):
        # When defect list is empty, states INSUFFICIENT_DATA
        empty_map = AutonomousIntelligenceEngine.generate_pain_map([])
        self.assertEqual(empty_map["status"], "INSUFFICIENT_DATA")
        self.assertEqual(empty_map["total_complaints"], 0)

        # With real defect records
        defects = [
            {"defect_category": "Zipper Breakage", "frequency_count": 30, "severity": "HIGH"},
            {"defect_category": "Foam Flattening", "frequency_count": 10, "severity": "MEDIUM"}
        ]
        pmap = AutonomousIntelligenceEngine.generate_pain_map(defects)
        self.assertEqual(pmap["status"], "VERIFIED")
        self.assertEqual(pmap["total_complaints"], 40)
        self.assertEqual(pmap["categories"][0]["category"], "Zipper Breakage")
        self.assertEqual(pmap["categories"][0]["percentage"], 75.0)
        self.assertEqual(pmap["categories"][1]["percentage"], 25.0)

    def test_competitor_gaps_hypothesis_labeling(self):
        listings = [
            {"platform": "flipkart", "price": 1499.0, "rating": 4.1, "listing_url": "http://flipkart.com"},
            {"platform": "meesho", "price": 999.0, "rating": 3.9, "listing_url": "http://meesho.com"}
        ]
        prod = {"planned_msrp": 1299.0, "region": "India"}
        defects = [{"defect_category": "Zipper Failure"}]
        gaps = AutonomousIntelligenceEngine.detect_competitor_gaps(prod, listings, defects)
        self.assertGreaterEqual(len(gaps), 1)
        for g in gaps:
            self.assertIn("hypothesis", g)
            self.assertIn("evidence_status", g)

    # ─────────────────────────────────────────────────────────────────────────
    # 6. WATCHLIST, ALERTS & CONFLICT TESTS
    # ─────────────────────────────────────────────────────────────────────────

    def test_watchlist_crud(self):
        self.assertFalse(is_in_watchlist("TEST_V7_001"))
        add_to_watchlist("TEST_V7_001", priority_status="HIGH_PRIORITY", notes="Q4 top candidate")
        self.assertTrue(is_in_watchlist("TEST_V7_001"))

        w_items = get_watchlist()
        self.assertEqual(len(w_items), 1)
        self.assertEqual(w_items[0]["priority_status"], "HIGH_PRIORITY")
        self.assertEqual(w_items[0]["name"], "Ergonomic Desk Wedge Pillow")

        remove_from_watchlist("TEST_V7_001")
        self.assertFalse(is_in_watchlist("TEST_V7_001"))

    def test_opportunity_alerts_and_dismissal(self):
        aid = create_opportunity_alert(
            product_id="TEST_V7_001",
            alert_type="NEW_OPPORTUNITY",
            title="High Potential Opportunity",
            what_happened="Score reached 86.5/100",
            why_it_matters="Passes all gates",
            recommended_action="Contact factory",
            severity="INFO"
        )
        self.assertGreater(aid, 0)
        alerts = get_active_alerts("TEST_V7_001")
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["title"], "High Potential Opportunity")

        dismiss_alert(aid)
        alerts_after = get_active_alerts("TEST_V7_001")
        self.assertEqual(len(alerts_after), 0)

    def test_data_conflict_detection_and_resolution(self):
        # Two listings with > 25% price difference
        listings = [
            {"platform": "amazon_in", "price": 1299.0},
            {"platform": "meesho", "price": 899.0}
        ]
        conflicts = AutonomousIntelligenceEngine.detect_and_record_conflicts("TEST_V7_001", listings)
        self.assertEqual(len(conflicts), 1)
        cid = conflicts[0]["conflict_id"]

        unresolved = get_data_conflicts("TEST_V7_001", unresolved_only=True)
        self.assertEqual(len(unresolved), 1)

        resolve_data_conflict(cid, resolution_status="RESOLVED", explanation="Verified price tier variance.")
        unresolved_after = get_data_conflicts("TEST_V7_001", unresolved_only=True)
        self.assertEqual(len(unresolved_after), 0)

    # ─────────────────────────────────────────────────────────────────────────
    # 7. WAR ROOM 2.0 & DISAGREEMENT ENGINE TESTS
    # ─────────────────────────────────────────────────────────────────────────

    def test_war_room_2_packets_and_consensus(self):
        dossier = AutonomousIntelligenceEngine.run_full_product_intelligence("TEST_V7_001")
        wr = dossier.get("war_room_2", {})
        self.assertIn("decision_type", wr)
        self.assertIn("summary", wr)
        self.assertIn("agent_packets", wr)

        # 4 specialist agents
        agent_names = [p["agent"] for p in wr["agent_packets"]]
        self.assertIn("Trend Scout", agent_names)
        self.assertIn("Defect Analyst", agent_names)
        self.assertIn("Economics Auditor", agent_names)
        self.assertIn("Marketplace Harvester", agent_names)

        for p in wr["agent_packets"]:
            self.assertIn("finding", p)
            self.assertIn("confidence", p)
            self.assertIn("evidence", p)
            self.assertIn("risks", p)
            self.assertIn("missing_data", p)
            self.assertIn("recommendation", p)

    def test_war_room_disagreement_detection(self):
        # Create a mock dossier where trend is strong but economics fails
        mock_dossier = {
            "product": {"planned_msrp": 500.0, "landed_cogs": 450.0},
            "scorecard": {
                "dimensions": {
                    "trend_strength": {"score": 85.0, "confidence": 90.0, "risk_flags": []},
                    "customer_pain": {"score": 75.0, "confidence": 85.0, "risk_flags": []},
                    "economic_viability": {"score": 30.0, "confidence": 90.0, "risk_flags": ["Margin Deficit"]},
                    "competition_pressure": {"score": 70.0, "confidence": 80.0, "risk_flags": []}
                }
            },
            "kill_switch": {"status": "SURVIVES", "kill_reasons": []},
            "counterfactual_economics": {
                "base_case": {"contribution_margin": -15.0},
                "downside_case": {"contribution_margin": -45.0}
            }
        }
        res = AutonomousIntelligenceEngine.run_war_room_2("MOCK_001", mock_dossier)
        self.assertEqual(res["decision_type"], "DISAGREEMENT")
        self.assertGreater(len(res["disagreements"]), 0)
        self.assertTrue(any("rejected the opportunity while" in d for d in res["disagreements"]))

    # ─────────────────────────────────────────────────────────────────────────
    # 8. AUTONOMOUS RESEARCH RUNS & SOURCE HEALTH
    # ─────────────────────────────────────────────────────────────────────────

    def test_research_run_lifecycle(self):
        run_id = start_research_run()
        self.assertTrue(run_id.startswith("run_"))

        ok = complete_research_run(
            research_run_id=run_id,
            products_processed=5,
            sources_consulted_count=3,
            signals_generated_count=15,
            alerts_generated_count=2,
            gate_transitions_count=4,
            status="COMPLETED"
        )
        self.assertTrue(ok)

        runs = get_research_runs(limit=5)
        self.assertGreaterEqual(len(runs), 1)
        self.assertEqual(runs[0]["research_run_id"], run_id)
        self.assertEqual(runs[0]["run_status"], "COMPLETED")
        self.assertEqual(runs[0]["products_processed"], 5)

    def test_alert_and_conflict_deduplication(self):
        # 1. Alert deduplication
        id1 = create_opportunity_alert(
            product_id="TEST_V7_001", alert_type="KILL_TRIGGER",
            title="Test Alert", what_happened="Fails test", why_it_matters="Risk"
        )
        id2 = create_opportunity_alert(
            product_id="TEST_V7_001", alert_type="KILL_TRIGGER",
            title="Test Alert Duplicate", what_happened="Fails test duplicate", why_it_matters="Risk duplicate"
        )
        self.assertEqual(id1, id2)
        alerts = get_active_alerts("TEST_V7_001")
        self.assertEqual(len([a for a in alerts if a["alert_type"] == "KILL_TRIGGER"]), 1)

        # 2. Conflict deduplication
        c1 = record_data_conflict("TEST_V7_001", "price", "amazon", "100", "flipkart", "200")
        c2 = record_data_conflict("TEST_V7_001", "price", "amazon", "100", "flipkart", "200")
        self.assertEqual(c1, c2)
        conflicts = get_data_conflicts("TEST_V7_001")
        self.assertEqual(len(conflicts), 1)

    def test_evidence_populated_on_full_intelligence_run(self):
        # Run full intelligence on seed product
        res = AutonomousIntelligenceEngine.run_full_product_intelligence("TEST_V7_001")
        self.assertNotIn("error", res)

        # Verify intelligence_evidence now has discrete records
        evidence_records = get_intelligence_evidence("TEST_V7_001")
        self.assertGreaterEqual(len(evidence_records), 3)
        types = {r["signal_type"] for r in evidence_records}
        self.assertIn("DEMAND", types)
        self.assertIn("TREND", types)
        self.assertIn("ECONOMICS", types)

    def test_trend_peaking_stage(self):
        # Product with high confidence but active > 45 days should be PEAKING
        peaking_prod = {
            "trend_confidence_score": 88.0,
            "ad_active_days": 60,
            "estimated_daily_units": 40,
            "trend_source": "Google Trends & Social"
        }
        res = AutonomousIntelligenceEngine.evaluate_trend_early_warning(peaking_prod)
        self.assertEqual(res["stage"], "PEAKING")
        self.assertLess(res["acceleration"], 0)
        self.assertGreater(res["velocity"], 1.0)

    # ─────────────────────────────────────────────────────────────────────────
    # 9. APRS V7.1 DECISION ENGINE HARDENING REGRESSION TESTS
    # ─────────────────────────────────────────────────────────────────────────

    def test_kill_switch_weak_customer_pain_differentiation_only(self):
        """Phase 3: Proves weak customer pain does NOT kill product if economically viable."""
        viable_prod = {
            "product_id": "PAIN_TEST_001",
            "bsr_rank": 2000,
            "estimated_daily_units": 30,
            "trend_confidence_score": 75.0,
            "planned_msrp": 1299.0,
            "region": "India",
            "category": "General"
        }
        # Only 1 minor defect report
        weak_defects = [
            {"defect_category": "Minor Packaging Dent", "frequency_count": 1, "severity": "LOW"}
        ]
        econ = Comprehensive15FactorEconomics.calculate_counterfactual_scenarios(
            fob_price=200.0, planned_msrp=1299.0
        )
        res = AutonomousIntelligenceEngine.evaluate_kill_switch(
            viable_prod,
            listings=[{"platform": "amazon_in", "price": 1299.0}],
            defects=weak_defects,
            suppliers=[{"moq_units": 200}],
            econ=econ
        )
        # MUST survive! (Not killed)
        self.assertEqual(res["status"], "SURVIVES")
        self.assertEqual(len(res["kill_reasons"]), 0)
        # Recorded as low differentiation evidence
        self.assertIn("differentiation_opportunity", res["kill_evidence"])
        self.assertEqual(
            res["kill_evidence"]["differentiation_opportunity"]["status"],
            "LOW_DIFFERENTIATION_EVIDENCE"
        )

    def test_kill_switch_customer_pain_spectrum(self):
        """Phase 3: Validates defect spectrum across 0, 1 minor, multiple minor, and recurring."""
        prod = {
            "product_id": "SPECTRUM_001",
            "bsr_rank": 3000,
            "estimated_daily_units": 25,
            "trend_confidence_score": 70.0,
            "planned_msrp": 999.0,
            "region": "India"
        }
        econ = Comprehensive15FactorEconomics.calculate_counterfactual_scenarios(fob_price=150.0, planned_msrp=999.0)
        supplier = [{"moq_units": 300}]

        # 1. Zero defects: missing evidence recorded, not falsely killed
        res_zero = AutonomousIntelligenceEngine.evaluate_kill_switch(prod, [], [], supplier, econ)
        self.assertTrue(any("customer review defect" in m.lower() for m in res_zero["missing_evidence"]))

        # 2. One minor defect: survives with differentiation warning
        d_one = [{"defect_category": "Minor Scratch", "frequency_count": 1, "severity": "LOW"}]
        res_one = AutonomousIntelligenceEngine.evaluate_kill_switch(prod, [], d_one, supplier, econ)
        self.assertEqual(res_one["status"], "SURVIVES")
        self.assertEqual(res_one["kill_evidence"]["differentiation_opportunity"]["status"], "LOW_DIFFERENTIATION_EVIDENCE")

        # 3. Multiple minor defects (freq = 2): survives with differentiation warning
        d_multi = [
            {"defect_category": "Slight Color Variation", "frequency_count": 1, "severity": "LOW"},
            {"defect_category": "Loose Tape", "frequency_count": 1, "severity": "LOW"}
        ]
        res_multi = AutonomousIntelligenceEngine.evaluate_kill_switch(prod, [], d_multi, supplier, econ)
        self.assertEqual(res_multi["status"], "SURVIVES")
        self.assertEqual(res_multi["kill_evidence"]["differentiation_opportunity"]["status"], "LOW_DIFFERENTIATION_EVIDENCE")

        # 4. High-severity recurring defects: viable differentiation, no differentiation warning
        d_high = [{"defect_category": "Motor Burnout", "frequency_count": 45, "severity": "CRITICAL"}]
        res_high = AutonomousIntelligenceEngine.evaluate_kill_switch(prod, [], d_high, supplier, econ)
        self.assertEqual(res_high["status"], "SURVIVES")
        self.assertNotIn("differentiation_opportunity", res_high["kill_evidence"])

    def test_kill_switch_competition_contextual_warning(self):
        """Phase 4: 12+ competitors alone does not kill if product has viable economics & differentiation."""
        prod = {
            "product_id": "COMP_12_001",
            "bsr_rank": 1200,
            "estimated_daily_units": 45,
            "trend_confidence_score": 85.0,
            "planned_msrp": 799.0,  # Below market competitors
            "region": "India"
        }
        # 14 listings with price 999
        listings = [{"platform": f"plat_{i}", "price": 999.0, "rating": 4.1} for i in range(14)]
        # Strong defect cluster to fix
        defects = [{"defect_category": "Broken Handle", "frequency_count": 35, "severity": "HIGH"}]
        econ = Comprehensive15FactorEconomics.calculate_counterfactual_scenarios(fob_price=120.0, planned_msrp=799.0)

        res = AutonomousIntelligenceEngine.evaluate_kill_switch(prod, listings, defects, [{"moq_units": 500}], econ)
        # Must survive with competition warning instead of being killed
        self.assertEqual(res["status"], "SURVIVES")
        self.assertIn("competition_warning", res["kill_evidence"])
        self.assertEqual(res["kill_evidence"]["competition_warning"]["status"], "HIGH_COMPETITION_SATURATION_WARNING")

        # Conversely, if market is impenetrable (all 4.8★, no defects, no price gap, thin margin), it hard-kills
        bad_listings = [{"platform": f"plat_{i}", "price": 499.0, "rating": 4.8} for i in range(14)]
        thin_econ = {"base_case": {"contribution_margin": 10.0, "contribution_margin_pct": 5.0}, "downside_case": {"contribution_margin": -5.0}}
        res_kill = AutonomousIntelligenceEngine.evaluate_kill_switch(
            {"planned_msrp": 550.0, "estimated_daily_units": 20},
            bad_listings,
            [],
            [{"moq_units": 200}],
            thin_econ
        )
        self.assertEqual(res_kill["status"], "KILLED")
        self.assertTrue(any("Saturated Monopolized Market" in r for r in res_kill["kill_reasons"]))

    def test_scorecard_missing_competition_evidence_not_positive(self):
        """Phase 5 & 6: 0 competitor listings results in neutral score (50.0) and low confidence (20.0%), NOT 82.0."""
        prod = {"bsr_rank": 2000, "estimated_daily_units": 30, "planned_msrp": 999.0}
        econ = Comprehensive15FactorEconomics.calculate_counterfactual_scenarios(fob_price=150.0, planned_msrp=999.0)
        freshness = {"overall_status": "FRESH"}

        card = AutonomousIntelligenceEngine.evaluate_scorecard(prod, [], [], [], econ, freshness)
        comp_dim = card["dimensions"]["competition_pressure"]
        # Must NOT be falsely positive (e.g. 82.0)
        self.assertEqual(comp_dim["score"], 50.0)
        self.assertEqual(comp_dim["confidence"], 20.0)
        self.assertTrue(any("UNKNOWN_COMPETITION" in f for f in comp_dim["risk_flags"]))

    def test_scorecard_score_vs_confidence_separation(self):
        """Phase 6: High economic score with missing telemetry decouples high score from low overall confidence."""
        empty_telemetry_prod = {"planned_msrp": 1299.0}
        econ = Comprehensive15FactorEconomics.calculate_counterfactual_scenarios(fob_price=150.0, planned_msrp=1299.0)
        card = AutonomousIntelligenceEngine.evaluate_scorecard(empty_telemetry_prod, [], [], [], econ, {"overall_status": "FRESH"})

        # Economics is strong, but demand/trend/competition/sourcing are missing
        self.assertGreaterEqual(card["dimensions"]["economic_viability"]["score"], 70.0)
        self.assertEqual(card["dimensions"]["demand_strength"]["confidence"], 25.0)
        self.assertEqual(card["dimensions"]["trend_strength"]["confidence"], 25.0)
        self.assertEqual(card["dimensions"]["competition_pressure"]["confidence"], 20.0)
        # Overall confidence is dampened
        self.assertLess(card["overall_confidence"], 55.0)

    def test_data_freshness_per_source_policy(self):
        """Phase 7: Validates differentiated expiration policies across diverse source types."""
        import datetime
        now = datetime.datetime.now()

        # Supplier quote 45 days old -> AGING (policy: 30d/60d)
        supplier_aging = [{"created_at": (now - datetime.timedelta(days=45)).isoformat()}]
        # Defect 15 days old -> FRESH (policy: 30d/90d)
        defect_fresh = [{"created_at": (now - datetime.timedelta(days=15)).isoformat()}]
        # Listing 20 days old -> STALE (policy: 3d/14d)
        listing_stale = [{"created_at": (now - datetime.timedelta(days=20)).isoformat()}]

        fresh_info = AutonomousIntelligenceEngine.evaluate_data_freshness(
            prod={"last_evaluated_date": now.isoformat(), "trend_source": "Google Trends"},
            listings=listing_stale,
            defects=defect_fresh,
            suppliers=supplier_aging
        )
        self.assertEqual(fresh_info["sourcing_freshness"], "AGING")
        self.assertEqual(fresh_info["defects_freshness"], "FRESH")
        self.assertEqual(fresh_info["listings_freshness"], "STALE")

    def test_potential_price_conflict_classification(self):
        """Phase 8: Conflict detection classifies price dispersion as POTENTIAL_PRICE_CONFLICT."""
        listings = [
            {"platform": "amazon_in", "price": 1499.0},
            {"platform": "meesho", "price": 799.0}
        ]
        conflicts = AutonomousIntelligenceEngine.detect_and_record_conflicts("CONFLICT_TEST_001", listings)
        self.assertEqual(len(conflicts), 1)
        self.assertIn("POTENTIAL_PRICE_CONFLICT", conflicts[0]["explanation"])

    def test_trend_heuristic_label_and_insufficient_history(self):
        """Phase 9: Trend model returns HEURISTIC_TREND_MODEL and marks INSUFFICIENT_HISTORY when telemetry missing."""
        # 1. Zero confidence / no source
        res_empty = AutonomousIntelligenceEngine.evaluate_trend_early_warning({})
        self.assertEqual(res_empty["model_type"], "HEURISTIC_TREND_MODEL")
        self.assertEqual(res_empty["stage"], "INSUFFICIENT_HISTORY")
        self.assertEqual(res_empty["velocity"], 0.0)

        # 2. Collapsing trend
        res_collapse = AutonomousIntelligenceEngine.evaluate_trend_early_warning({"trend_confidence_score": 15.0, "trend_source": "Telemetry"})
        self.assertEqual(res_collapse["model_type"], "HEURISTIC_TREND_MODEL")
        self.assertEqual(res_collapse["stage"], "COLLAPSING")

    def test_counterfactual_economics_extreme_values(self):
        """Phase 14: Verifies zero/negative MSRP and extreme COGS do not crash or invert binary search intervals."""
        # 1. Zero MSRP
        res_zero = Comprehensive15FactorEconomics.calculate_counterfactual_scenarios(fob_price=100.0, planned_msrp=0.0)
        be_zero = res_zero["break_evens"]
        self.assertGreater(be_zero["break_even_selling_price"], 0)
        self.assertGreaterEqual(be_zero["break_even_cogs"], 0)

        # 2. Extreme COGS > MSRP
        res_high_cogs = Comprehensive15FactorEconomics.calculate_counterfactual_scenarios(fob_price=5000.0, planned_msrp=1000.0)
        be_high = res_high_cogs["break_evens"]
        self.assertGreater(be_high["break_even_selling_price"], 1000.0)

        # 3. Negative MSRP input
        res_neg = Comprehensive15FactorEconomics.calculate_counterfactual_scenarios(fob_price=100.0, planned_msrp=-500.0)
        self.assertGreater(res_neg["break_evens"]["break_even_selling_price"], 0)

    def test_alert_dismissal_preserves_new_evidence_reappearance(self):
        """Phase 11: Dismissed alerts cannot be resurrected by identical cycles, but reappear on new evidence."""
        # 1. Create alert using valid existing product TEST_V7_001
        aid1 = create_opportunity_alert(
            product_id="TEST_V7_001",
            alert_type="TREND_DECAY",
            title="Trend Dropped",
            what_happened="Velocity dropped 30%",
            why_it_matters="Decay",
            recommended_action="Review"
        )
        self.assertGreater(aid1, 0)

        # 2. Dismiss it
        self.assertTrue(dismiss_alert(aid1))

        # 3. Identical cycle with same what_happened does NOT create duplicate
        aid2 = create_opportunity_alert(
            product_id="TEST_V7_001",
            alert_type="TREND_DECAY",
            title="Trend Dropped",
            what_happened="Velocity dropped 30%",
            why_it_matters="Decay",
            recommended_action="Review"
        )
        self.assertEqual(aid1, aid2)
        active_alerts = get_active_alerts("TEST_V7_001")
        # Should not have active TREND_DECAY alert
        self.assertEqual(len([a for a in active_alerts if a["alert_type"] == "TREND_DECAY"]), 0)

        # 4. Genuinely new evidence allows new alert
        aid3 = create_opportunity_alert(
            product_id="TEST_V7_001",
            alert_type="TREND_DECAY",
            title="Trend Dropped Severe",
            what_happened="Velocity dropped 70% critically",
            why_it_matters="Severe Decay",
            recommended_action="Kill"
        )
        self.assertNotEqual(aid1, aid3)
        active_alerts_after = get_active_alerts("TEST_V7_001")
        decay_alerts = [a for a in active_alerts_after if a["alert_type"] == "TREND_DECAY"]
        self.assertEqual(len(decay_alerts), 1)

    # ─────────────────────────────────────────────────────────────────────────
    # 7. V7.2 REALITY CHECK & PRODUCTION READINESS AUDIT TESTS
    # ─────────────────────────────────────────────────────────────────────────

    def test_research_runs_and_source_health_persisted(self):
        """V7.2 Reality Check: Verifies research_runs and source_health are populated and retrievable."""
        # 1. Update source health
        update_source_health("TestAmazonScraper", True, 142.5)
        update_source_health("TestFlipkartScraper", False, 0.0)
        health_summary = get_source_health_summary()
        self.assertGreaterEqual(len(health_summary), 2)
        names = [h["source_name"] for h in health_summary]
        self.assertIn("TestAmazonScraper", names)
        self.assertIn("TestFlipkartScraper", names)

        # 2. Record full research run lifecycle
        run_id = start_research_run()
        self.assertTrue(run_id.startswith("run_"))
        ok = complete_research_run(
            research_run_id=run_id,
            products_processed=10,
            sources_consulted_count=4,
            signals_generated_count=32,
            alerts_generated_count=3,
            status="COMPLETED"
        )
        self.assertTrue(ok)
        runs = get_research_runs(limit=10)
        self.assertTrue(any(r["research_run_id"] == run_id and r["run_status"] == "COMPLETED" for r in runs))

    def test_alert_dismissal_with_evidence_summary_fingerprint(self):
        """V7.2 Reality Check: Verifies alert dismissal compares evidence_summary fingerprint."""
        aid1 = create_opportunity_alert(
            product_id="TEST_V7_001",
            alert_type="MARGIN_COMPRESSION",
            title="Margin Warning",
            what_happened="Margin dropped",
            why_it_matters="Economics",
            evidence_summary='{"base_cm": 25.0, "cm_pct": 10.5}'
        )
        self.assertTrue(dismiss_alert(aid1))

        # Identical what_happened and evidence_summary -> stays dismissed
        aid2 = create_opportunity_alert(
            product_id="TEST_V7_001",
            alert_type="MARGIN_COMPRESSION",
            title="Margin Warning",
            what_happened="Margin dropped",
            why_it_matters="Economics",
            evidence_summary='{"base_cm": 25.0, "cm_pct": 10.5}'
        )
        self.assertEqual(aid1, aid2)
        self.assertEqual(len(get_active_alerts("TEST_V7_001")), 0)

        # Changed evidence_summary (new margin telemetry) -> triggers new alert
        aid3 = create_opportunity_alert(
            product_id="TEST_V7_001",
            alert_type="MARGIN_COMPRESSION",
            title="Margin Warning Critical",
            what_happened="Margin dropped",
            why_it_matters="Economics",
            evidence_summary='{"base_cm": 5.0, "cm_pct": 2.1}'
        )
        self.assertNotEqual(aid1, aid3)
        self.assertEqual(len(get_active_alerts("TEST_V7_001")), 1)

    def test_kill_switch_insufficient_evidence_when_missing_competitors_and_defects(self):
        """V7.2 Reality Check: Product with no competitor listings and no defects must return INSUFFICIENT_EVIDENCE."""
        prod = {
            "product_id": "PARTIAL_001",
            "bsr_rank": 1200,
            "estimated_daily_units": 25,
            "trend_confidence_score": 80.0,
            "planned_msrp": 999.0
        }
        econ = Comprehensive15FactorEconomics.calculate_counterfactual_scenarios(fob_price=150.0, planned_msrp=999.0)
        # Empty listings and empty defects
        res = AutonomousIntelligenceEngine.evaluate_kill_switch(prod, [], [], [{"moq_units": 100}], econ)
        self.assertEqual(res["status"], "INSUFFICIENT_EVIDENCE")
        self.assertTrue(any("competitor listings" in m.lower() for m in res["missing_evidence"]))
        self.assertTrue(any("defect" in m.lower() for m in res["missing_evidence"]))

    def test_opportunity_alert_suppressed_when_confidence_low(self):
        """V7.2 Reality Check: Score >= 80 does NOT trigger NEW_OPPORTUNITY alert if confidence < 70%."""
        # Insert high-scoring product with zero competitor listings and zero defects (low confidence)
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO master_products (
                product_id, name, category, region, planned_msrp, landed_cogs,
                gross_margin_pct, estimated_cac, net_profit_pct, worst_case_stress_margin_pct,
                status, overall_score, consensus_status, first_discovered_date,
                last_evaluated_date, sourcing_cluster, bsr_rank, estimated_daily_units,
                trend_source, trend_confidence_score, factory_cogs
            ) VALUES (
                'LOW_CONF_001', 'High Theoretical Margin Pillow', 'Wellness', 'India',
                2999.0, 400.0, 85.0, 200.0, 35.0, 25.0,
                'PASS', 90.0, 'CONSENSUS_PASS', date('now'),
                date('now'), 'Surat Hub', 500, 80,
                'Internal Telemetry', 92.0, 300.0
            )
        """)
        self.conn.commit()

        dossier = AutonomousIntelligenceEngine.run_full_product_intelligence("LOW_CONF_001")
        alerts = get_active_alerts("LOW_CONF_001")
        # Should NOT have NEW_OPPORTUNITY alert because confidence is below 70% due to missing listings & defects
        new_opp_alerts = [a for a in alerts if a["alert_type"] == "NEW_OPPORTUNITY"]
        self.assertEqual(len(new_opp_alerts), 0)

    def test_multi_product_reality_check_simulation(self):
        """V7.2 Reality Check: Simulates 10 distinct product archetypes to verify decision engine robustness."""
        archetypes = [
            # 1. Healthy Winner: High units, good margin, moderate competition, high pain to fix
            {
                "id": "ARCH_WINNER", "bsr": 1500, "units": 45, "msrp": 999.0, "fob": 180.0,
                "listings": [{"rating": 4.1, "price": 999.0}], "defects": [{"frequency_count": 25, "severity": "HIGH"}],
                "expected_kill": "SURVIVES"
            },
            # 2. Deficit Economics: High COGS relative to MSRP
            {
                "id": "ARCH_DEFICIT", "bsr": 2000, "units": 30, "msrp": 499.0, "fob": 450.0,
                "listings": [{"rating": 4.2, "price": 499.0}], "defects": [{"frequency_count": 10, "severity": "MEDIUM"}],
                "expected_kill": "KILLED"
            },
            # 3. Dead Demand: BSR > 35k and < 3 units
            {
                "id": "ARCH_DEAD_DEMAND", "bsr": 65000, "units": 1, "msrp": 899.0, "fob": 150.0,
                "listings": [{"rating": 4.0, "price": 899.0}], "defects": [{"frequency_count": 5, "severity": "LOW"}],
                "expected_kill": "KILLED"
            },
            # 4. Monopolized Saturated Market: 15 competitors, 4.8 avg rating, thin margin, no pain
            {
                "id": "ARCH_MONOPOLY", "bsr": 1000, "units": 50, "msrp": 399.0, "fob": 250.0,
                "listings": [{"rating": 4.8, "price": 380.0} for _ in range(15)],
                "defects": [{"frequency_count": 1, "severity": "LOW"}],
                "expected_kill": "KILLED"
            },
            # 5. Saturated Market with Opportunity: 14 competitors but low ratings & high defect complaints
            {
                "id": "ARCH_SATURATED_OPP", "bsr": 1200, "units": 40, "msrp": 1299.0, "fob": 200.0,
                "listings": [{"rating": 3.6, "price": 1499.0} for _ in range(14)],
                "defects": [{"frequency_count": 45, "severity": "HIGH"}],
                "expected_kill": "SURVIVES"
            },
            # 6. Unresearched Niche: missing listings & missing defects
            {
                "id": "ARCH_UNRESEARCHED", "bsr": 2500, "units": 20, "msrp": 1499.0, "fob": 250.0,
                "listings": [], "defects": [],
                "expected_kill": "INSUFFICIENT_EVIDENCE"
            },
            # 7. Sourcing MOQ Trap: MOQ 5000 units with 5 daily units (1000 days runway)
            {
                "id": "ARCH_MOQ_TRAP", "bsr": 15000, "units": 5, "msrp": 1999.0, "fob": 300.0,
                "suppliers": [{"moq_units": 5000}], "listings": [{"rating": 4.2, "price": 1999.0}],
                "defects": [{"frequency_count": 10, "severity": "MEDIUM"}],
                "expected_kill": "KILLED"
            },
            # 8. Zero MSRP (Invalid Listing)
            {
                "id": "ARCH_ZERO_MSRP", "bsr": 2000, "units": 25, "msrp": 0.0, "fob": 100.0,
                "listings": [{"rating": 4.0, "price": 500.0}], "defects": [{"frequency_count": 5, "severity": "MEDIUM"}],
                "expected_kill": "KILLED"
            },
            # 9. Low Customer Pain (Viability Preserved, Differentiation Low)
            {
                "id": "ARCH_LOW_PAIN", "bsr": 1800, "units": 35, "msrp": 999.0, "fob": 180.0,
                "listings": [{"rating": 4.4, "price": 999.0}], "defects": [{"frequency_count": 1, "severity": "LOW"}],
                "expected_kill": "SURVIVES"
            },
            # 10. Severe Downside Deficit (Fails stress test at high returns/RTO)
            {
                "id": "ARCH_DOWNSIDE_DEFICIT", "bsr": 3000, "units": 20, "msrp": 699.0, "fob": 350.0,
                "listings": [{"rating": 4.1, "price": 699.0}], "defects": [{"frequency_count": 8, "severity": "MEDIUM"}],
                "expected_kill": "KILLED"
            }
        ]

        for arch in archetypes:
            prod = {
                "product_id": arch["id"],
                "bsr_rank": arch.get("bsr", 2000),
                "estimated_daily_units": arch.get("units", 20),
                "trend_confidence_score": 85.0,
                "planned_msrp": arch["msrp"],
                "region": "India"
            }
            econ = Comprehensive15FactorEconomics.calculate_counterfactual_scenarios(
                fob_price=arch["fob"],
                planned_msrp=arch["msrp"]
            )
            suppliers = arch.get("suppliers", [{"moq_units": 200}])
            listings = arch.get("listings", [])
            defects = arch.get("defects", [])
            res = AutonomousIntelligenceEngine.evaluate_kill_switch(prod, listings, defects, suppliers, econ)
            self.assertEqual(
                res["status"], arch["expected_kill"],
                f"Archetype {arch['id']} expected {arch['expected_kill']} but got {res['status']}. Reasons: {res.get('kill_reasons')} Missing: {res.get('missing_evidence')}"
            )


if __name__ == "__main__":
    unittest.main()

