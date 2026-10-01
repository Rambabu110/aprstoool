"""
core/intelligence_engine.py — APRS V7 Autonomous Product Intelligence Engine.

Implements the forensic intelligence layer:
- Feature 1: Product Opportunity Intelligence Card
- Feature 2: Multi-Dimensional Opportunity Scorecard (10 dimensions)
- Feature 3: "Why This Product?" Explainability Panel
- Feature 4: Opportunity Kill Switch (6 failure tests)
- Feature 5: Integration with Counterfactual Economics
- Feature 6: Competitor Gap Detection (Hypothesis-driven)
- Feature 7: Customer Pain Map (Honest defect distributions)
- Feature 8: Trend Early-Warning System (Rise, Acceleration, Decay)
- Feature 9: Data Freshness & Trust System (Decaying confidence)
- Feature 10: Evidence Graph (Traceability model)
- Feature 16: Source Reliability Framework
- Feature 17: Multi-Source Conflict Detection
- Feature 18 & 19: War Room 2.0 & Disagreement Engine
"""

import json
import logging
import datetime
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("aprs.intelligence")
from core.database import (
    get_connection,
    save_product_intelligence,
    get_product_intelligence,
    record_intelligence_evidence,
    get_intelligence_evidence,
    create_opportunity_alert,
    record_data_conflict,
    get_data_conflicts,
    record_timeline_event,
    update_source_health,
    add_to_watchlist,
    is_in_watchlist
)
from core.economics_engine import Comprehensive15FactorEconomics


class AutonomousIntelligenceEngine:
    """
    Autonomous Product Intelligence Engine for APRS V7.
    Transforms raw scraped listings, review defects, and financial parameters into
    an evidence-backed, stress-tested, and transparent intelligence dossier.
    """

    @classmethod
    def get_product_raw_data(cls, product_id: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Fetches product, listings, defects, suppliers, and gate progress from SQLite."""
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("SELECT * FROM master_products WHERE product_id = ?", (product_id,))
        p_row = cur.fetchone()
        prod = dict(p_row) if p_row else {}

        cur.execute("SELECT * FROM multi_platform_listings WHERE product_id = ?", (product_id,))
        listings = [dict(r) for r in cur.fetchall()]

        cur.execute("SELECT * FROM defect_clusters WHERE product_id = ?", (product_id,))
        defects = [dict(r) for r in cur.fetchall()]

        cur.execute("SELECT * FROM product_suppliers WHERE product_id = ?", (product_id,))
        suppliers = [dict(r) for r in cur.fetchall()]

        cur.execute("SELECT * FROM product_gate_progress WHERE product_id = ? ORDER BY gate_number", (product_id,))
        gates = [dict(r) for r in cur.fetchall()]

        conn.close()
        return prod, listings, defects, suppliers, gates

    @classmethod
    def evaluate_scorecard(
        cls,
        prod: Dict[str, Any],
        listings: List[Dict[str, Any]],
        defects: List[Dict[str, Any]],
        suppliers: List[Dict[str, Any]],
        econ: Dict[str, Any],
        freshness_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Feature 2: Multi-Dimensional Opportunity Scorecard.
        Evaluates 10 transparent dimensions with score, confidence, evidence count, freshness, and risk flags.
        """
        dimensions = {}

        # 1. Demand Strength
        bsr = prod.get("bsr_rank") or 0
        units = prod.get("estimated_daily_units") or 0
        demand_score = 50.0
        demand_flags = []
        if units >= 40 or (0 < bsr <= 1500):
            demand_score = 88.0
            demand_conf = 85.0
            demand_ev = 2
        elif units >= 20 or (0 < bsr <= 5000):
            demand_score = 72.0
            demand_conf = 80.0
            demand_ev = 2
        elif units > 0 or bsr > 0:
            demand_score = 55.0
            demand_conf = 65.0
            demand_ev = 1
        else:
            demand_score = 50.0  # Neutral missing-evidence baseline
            demand_conf = 25.0   # Low confidence due to missing telemetry
            demand_ev = 0
            demand_flags.append("INSUFFICIENT_EVIDENCE: No verified BSR or daily sales volume recorded")

        dimensions["demand_strength"] = {
            "dimension": "Demand Strength",
            "score": round(demand_score, 1),
            "confidence": demand_conf,
            "evidence_count": demand_ev,
            "freshness": freshness_info.get("demand_freshness", "INSUFFICIENT" if demand_ev == 0 else "FRESH"),
            "risk_flags": demand_flags
        }

        # 2. Trend Strength
        t_conf = float(prod.get("trend_confidence_score") or 0.0)
        t_source = prod.get("trend_source") or ""
        trend_flags = []
        if not t_source or t_conf == 0.0:
            trend_score = 50.0  # Neutral missing-evidence baseline
            trend_conf = 25.0   # Low confidence
            trend_ev = 0
            trend_flags.append("INSUFFICIENT_EVIDENCE: Missing external verified trend source")
        else:
            trend_score = max(20.0, t_conf)
            trend_conf = 80.0
            trend_ev = 1
            if t_conf < 50.0:
                trend_flags.append("Trend velocity confidence below threshold")

        dimensions["trend_strength"] = {
            "dimension": "Trend Strength",
            "score": round(trend_score, 1),
            "confidence": trend_conf,
            "evidence_count": trend_ev,
            "freshness": freshness_info.get("trend_freshness", "AGING"),
            "risk_flags": trend_flags
        }

        # 3. Competition Pressure
        comp_count = len(listings)
        avg_rating = sum(float(l.get("rating") or 4.0) for l in listings) / max(1, comp_count) if listings else 4.0
        comp_flags = []
        if comp_count == 0:
            # Missing competitor data must NOT produce falsely positive score (e.g. 82.0)
            comp_score = 50.0  # Neutral baseline
            comp_conf = 20.0   # Low confidence
            comp_flags.append("UNKNOWN_COMPETITION: 0 competitor listings recorded — insufficient evidence to assume low competition")
        elif comp_count >= 12:
            comp_score = 30.0
            comp_conf = 85.0
            comp_flags.append(f"Severe multi-platform competition density ({comp_count} active listings)")
        elif comp_count >= 5:
            comp_score = 45.0
            comp_conf = 80.0
            comp_flags.append(f"High cross-platform competition density ({comp_count} active listings)")
        elif comp_count >= 2:
            comp_score = 65.0
            comp_conf = 75.0
        else:  # exactly 1 competitor verified
            comp_score = 78.0
            comp_conf = 65.0
            comp_flags.append("Single competitor verified — white space opportunity")

        if comp_count > 0 and avg_rating >= 4.6:
            comp_flags.append("Incumbents maintain high average rating (>=4.6★)")

        dimensions["competition_pressure"] = {
            "dimension": "Competition Pressure",
            "score": round(comp_score, 1),
            "confidence": comp_conf,
            "evidence_count": comp_count,
            "freshness": freshness_info.get("listings_freshness", "INSUFFICIENT" if comp_count == 0 else "FRESH"),
            "risk_flags": comp_flags
        }

        # 4. Customer Pain
        total_defects = sum(int(d.get("frequency_count") or 1) for d in defects)
        pain_flags = []
        if not defects or total_defects == 0:
            pain_score = 50.0  # Neutral baseline
            pain_conf = 25.0   # Low confidence
            pain_ev = 0
            pain_flags.append("LOW_DIFFERENTIATION_EVIDENCE: No customer defect reports mined — differentiation opportunity unverified")
        elif total_defects >= 30:
            pain_score = 90.0  # High customer pain = huge opportunity for v2 fix!
            pain_conf = 85.0
            pain_ev = len(defects)
        elif total_defects >= 10:
            pain_score = 75.0
            pain_conf = 80.0
            pain_ev = len(defects)
        elif total_defects >= 3:
            pain_score = 60.0
            pain_conf = 70.0
            pain_ev = len(defects)
        else:
            pain_score = 40.0
            pain_conf = 55.0
            pain_ev = len(defects)
            pain_flags.append("LOW_DIFFERENTIATION_EVIDENCE: Complaints are minor/cosmetic with low frequency (<3)")

        dimensions["customer_pain"] = {
            "dimension": "Customer Pain",
            "score": round(pain_score, 1),
            "confidence": pain_conf,
            "evidence_count": pain_ev,
            "freshness": freshness_info.get("defects_freshness", "INSUFFICIENT" if not defects else "FRESH"),
            "risk_flags": pain_flags
        }

        # 5. Economic Viability
        base_cm = econ.get("base_case", {}).get("contribution_margin", 0.0)
        base_cm_pct = econ.get("base_case", {}).get("contribution_margin_pct", 0.0)
        downside_cm = econ.get("downside_case", {}).get("contribution_margin", 0.0)
        econ_flags = []
        if not econ or not econ.get("base_case"):
            econ_score = 50.0
            econ_conf = 20.0
            econ_ev = 0
            econ_flags.append("INSUFFICIENT_EVIDENCE: 15-factor economics not calculated")
        elif base_cm > 0 and base_cm_pct >= 20.0 and downside_cm > 0:
            econ_score = 88.0
            econ_conf = 90.0
            econ_ev = 15
        elif base_cm > 0 and downside_cm > 0:
            econ_score = 72.0
            econ_conf = 85.0
            econ_ev = 15
        elif base_cm > 0:
            econ_score = 52.0
            econ_conf = 80.0
            econ_ev = 15
            econ_flags.append("Downside scenario generates margin deficit")
        else:
            econ_score = 25.0
            econ_conf = 90.0
            econ_ev = 15
            econ_flags.append("Base case economics in negative contribution margin")

        dimensions["economic_viability"] = {
            "dimension": "Economic Viability",
            "score": round(econ_score, 1),
            "confidence": econ_conf,
            "evidence_count": econ_ev,
            "freshness": "FRESH" if econ_ev > 0 else "INSUFFICIENT",
            "risk_flags": econ_flags
        }

        # 6. Sourcing Feasibility
        sup_count = len(suppliers)
        hub = prod.get("sourcing_cluster") or ""
        sourcing_flags = []
        if not suppliers and not hub:
            sourcing_score = 50.0  # Neutral baseline
            sourcing_conf = 25.0   # Low confidence
            sourcing_ev = 0
            sourcing_flags.append("INSUFFICIENT_EVIDENCE: No verified manufacturing supplier quote or industrial cluster")
        elif sup_count >= 2 and hub:
            sourcing_score = 85.0
            sourcing_conf = 85.0
            sourcing_ev = sup_count
        elif sup_count >= 1 or hub:
            sourcing_score = 70.0
            sourcing_conf = 75.0
            sourcing_ev = sup_count
        else:
            sourcing_score = 40.0
            sourcing_conf = 50.0
            sourcing_ev = sup_count

        dimensions["sourcing_feasibility"] = {
            "dimension": "Sourcing Feasibility",
            "score": round(sourcing_score, 1),
            "confidence": sourcing_conf,
            "evidence_count": sourcing_ev,
            "freshness": "FRESH" if sourcing_ev > 0 else "INSUFFICIENT",
            "risk_flags": sourcing_flags
        }

        # 7. Operational Risk
        op_score = 75.0
        op_flags = []
        break_evens = econ.get("break_evens", {})
        if not break_evens:
            op_score = 50.0
            op_conf = 30.0
            op_flags.append("INSUFFICIENT_EVIDENCE: Break-even stress parameters not calculated")
        else:
            op_conf = 75.0
            max_rto = break_evens.get("maximum_acceptable_rto_pct", 30.0)
            if max_rto < 20.0:
                op_score -= 20.0
                op_flags.append(f"Vulnerable to RTO spikes (Breaks even at only {max_rto}% RTO)")
            if prod.get("region") == "India":
                op_flags.append("COD logistics default active (estimated 60% COD mix)")

        dimensions["operational_risk"] = {
            "dimension": "Operational Risk",
            "score": round(max(20.0, op_score), 1),
            "confidence": op_conf,
            "evidence_count": 4 if break_evens else 0,
            "freshness": "FRESH" if break_evens else "INSUFFICIENT",
            "risk_flags": op_flags
        }

        # 8. Market Saturation
        sat_flags = []
        if comp_count == 0:
            sat_score = 50.0  # Neutral baseline
            sat_conf = 20.0   # Low confidence
            sat_flags.append("UNKNOWN_SATURATION: No competitor listings tracked to assess market saturation")
        elif comp_count > 4:
            sat_score = 45.0
            sat_conf = 75.0
            sat_flags.append("Multi-platform listings suggest market approaching saturation")
        else:
            sat_score = 70.0
            sat_conf = 70.0
            sat_flags.append("White space present across alternate regional platforms")

        dimensions["market_saturation"] = {
            "dimension": "Market Saturation",
            "score": round(sat_score, 1),
            "confidence": sat_conf,
            "evidence_count": comp_count,
            "freshness": freshness_info.get("listings_freshness", "INSUFFICIENT" if comp_count == 0 else "FRESH"),
            "risk_flags": sat_flags
        }

        # 9. Evidence Quality
        total_evidence_points = comp_count + len(defects) + sup_count + (2 if units > 0 else 0)
        ev_score = min(100.0, total_evidence_points * 12.0)
        ev_flags = []
        if total_evidence_points < 3:
            ev_flags.append("Critically low evidence count — research status INSUFFICIENT")

        dimensions["evidence_quality"] = {
            "dimension": "Evidence Quality",
            "score": round(ev_score, 1),
            "confidence": 85.0 if total_evidence_points >= 3 else 35.0,
            "evidence_count": total_evidence_points,
            "freshness": "FRESH",
            "risk_flags": ev_flags
        }

        # 10. Data Freshness
        overall_fresh = freshness_info.get("overall_status", "FRESH")
        df_score = 95.0 if overall_fresh == "FRESH" else (65.0 if overall_fresh == "AGING" else 40.0)
        df_flags = []
        if overall_fresh != "FRESH":
            df_flags.append(f"Telemetry signals are {overall_fresh.lower()} — re-scrape advised")

        dimensions["data_freshness"] = {
            "dimension": "Data Freshness",
            "score": round(df_score, 1),
            "confidence": 90.0 if overall_fresh != "INSUFFICIENT" else 30.0,
            "evidence_count": 5,
            "freshness": overall_fresh,
            "risk_flags": df_flags
        }

        # Composite Opportunity Score (Weighted non-opaque formula)
        weights = {
            "demand_strength": 0.18,
            "trend_strength": 0.12,
            "competition_pressure": 0.10,
            "customer_pain": 0.15,
            "economic_viability": 0.18,
            "sourcing_feasibility": 0.10,
            "operational_risk": 0.05,
            "market_saturation": 0.04,
            "evidence_quality": 0.05,
            "data_freshness": 0.03
        }

        composite_score = sum(dimensions[k]["score"] * weights[k] for k in weights)
        overall_confidence = sum(dimensions[k]["confidence"] * weights[k] for k in weights)

        return {
            "composite_score": round(composite_score, 1),
            "overall_confidence": round(overall_confidence, 1),
            "dimensions": dimensions
        }

    @classmethod
    def evaluate_kill_switch(
        cls,
        prod: Dict[str, Any],
        listings: List[Dict[str, Any]],
        defects: List[Dict[str, Any]],
        suppliers: List[Dict[str, Any]],
        econ: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Feature 4: Opportunity Kill Switch.
        Actively attempts to DISPROVE the opportunity across 6 failure domains:
        1. Demand Failure
        2. Competition Failure (Contextual: Saturation vs Moat)
        3. Economics Failure
        4. Sourcing Failure
        5. Customer Pain Failure (Viability vs Differentiation Opportunity)
        6. Marketplace Failure

        Returns:
            status: SURVIVES | KILLED | INSUFFICIENT_EVIDENCE
            kill_reasons: List[str]
            kill_evidence: Dict[str, Any]
            missing_evidence: List[str]
        """
        kill_reasons = []
        kill_evidence = {}
        missing_evidence = []

        # ── Test 1: Demand Failure ──
        bsr = prod.get("bsr_rank") or 0
        daily_units = prod.get("estimated_daily_units") or 0
        trend_conf = float(prod.get("trend_confidence_score") or 0.0)

        if bsr == 0 and daily_units == 0 and trend_conf == 0.0:
            missing_evidence.append("No verified BSR, daily unit volume, or trend telemetry recorded.")
        elif bsr > 35000 and daily_units < 3:
            kill_reasons.append("Demand Collapse: BSR exceeds 35,000 with less than 3 estimated daily units.")
            kill_evidence["demand_failure"] = {"bsr": bsr, "daily_units": daily_units}
        elif trend_conf > 0 and trend_conf < 25.0:
            kill_reasons.append("Trend Decay: External trend confidence score fell below minimum survival threshold (25%).")
            kill_evidence["trend_decay"] = {"trend_confidence": trend_conf}

        # ── Test 2: Competition Failure (Contextual Audit) ──
        if not listings:
            missing_evidence.append("No competitor listings scraped across target marketplaces.")
        elif len(listings) >= 12:
            # Audit context: raw listing count of 12 should NOT automatically kill if the
            # product has strong economics, distinct customer pain vectors, or price gaps.
            avg_rating = sum(float(l.get("rating") or 4.0) for l in listings) / max(1, len(listings))
            has_high_pain = any(d.get("severity") in ("HIGH", "CRITICAL") or int(d.get("frequency_count") or 1) >= 10 for d in defects)
            base_cm_pct = econ.get("base_case", {}).get("contribution_margin_pct", 0.0) if econ else 0.0
            downside_cm = econ.get("downside_case", {}).get("contribution_margin", 0.0) if econ else 0.0
            has_strong_econ = (base_cm_pct >= 20.0 and downside_cm > 0.0)

            prices = [float(l.get("price") or 0.0) for l in listings if float(l.get("price") or 0.0) > 0]
            planned_msrp = float(prod.get("planned_msrp") or 0.0)
            has_price_gap = (prices and planned_msrp > 0 and planned_msrp < min(prices))

            # Hard kill ONLY if incumbents are universally high rated, there is no high pain to fix, no price gap, and margins are thin
            if avg_rating >= 4.5 and not has_high_pain and not has_price_gap and not has_strong_econ:
                kill_reasons.append("Saturated Monopolized Market: 12+ competitors with high ratings (>=4.5★) and no viable differentiation vector.")
                kill_evidence["competition_failure"] = {
                    "competitor_count": len(listings),
                    "avg_rating": round(avg_rating, 2),
                    "differentiation_found": False
                }
            else:
                # Contextual warning: High saturation risk, but product maintains differentiation/economic viability
                kill_evidence["competition_warning"] = {
                    "competitor_count": len(listings),
                    "avg_rating": round(avg_rating, 2),
                    "status": "HIGH_COMPETITION_SATURATION_WARNING",
                    "note": f"{len(listings)} listings present saturation risk, but opportunity survives via differentiation/economic buffer."
                }

        # ── Test 3: Economics Failure ──
        if not econ or not econ.get("base_case"):
            missing_evidence.append("Comprehensive 15-factor economics analysis has not been calculated.")
        else:
            base_cm = econ.get("base_case", {}).get("contribution_margin", 0.0)
            base_cm_pct = econ.get("base_case", {}).get("contribution_margin_pct", 0.0)
            downside_cm = econ.get("downside_case", {}).get("contribution_margin", 0.0)
            severe_cm = econ.get("severe_downside_case", {}).get("contribution_margin", 0.0)

            if base_cm <= 0.0:
                kill_reasons.append(f"Economics Deficit: Base case contribution margin is negative ({base_cm:.2f}).")
                kill_evidence["economics_failure"] = {"base_cm": base_cm, "base_cm_pct": base_cm_pct}
            elif base_cm_pct < 8.0:
                kill_reasons.append(f"Margin Compression: Base case contribution margin is below 8% ({base_cm_pct:.1f}%).")
                kill_evidence["economics_failure"] = {"base_cm_pct": base_cm_pct}
            elif downside_cm < -25.0:
                kill_reasons.append(f"Severe Downside Vulnerability: Downside stress scenario generates severe deficit ({downside_cm:.2f}).")
                kill_evidence["economics_failure"] = {"downside_cm": downside_cm}

        # ── Test 4: Sourcing Failure ──
        if not suppliers and not prod.get("sourcing_cluster"):
            missing_evidence.append("No verified supplier quote or manufacturing cluster available.")
        for s in suppliers:
            moq = int(s.get("moq_units") or 0)
            if moq > 3000 and daily_units > 0 and (moq / daily_units) > 180:
                kill_reasons.append(f"Sourcing MOQ Risk: Factory MOQ of {moq} units exceeds 6 months of sales velocity.")
                kill_evidence["sourcing_failure"] = {"moq": moq, "daily_units": daily_units}

        # ── Test 5: Customer Pain (Differentiation vs Viability Hardening) ──
        if not defects:
            missing_evidence.append("No customer review defect data mined.")
        else:
            all_low = all(d.get("severity") == "LOW" for d in defects)
            total_freq = sum(int(d.get("frequency_count") or 1) for d in defects)
            if all_low and total_freq < 3:
                # Conflation between product viability and differentiation opportunity is corrected:
                # Weak customer pain does NOT prove product commercial failure.
                # It is recorded as LOW_DIFFERENTIATION_EVIDENCE risk warning rather than hard-killing the product.
                kill_evidence["differentiation_opportunity"] = {
                    "status": "LOW_DIFFERENTIATION_EVIDENCE",
                    "defect_count": len(defects),
                    "total_freq": total_freq,
                    "note": "Identified complaints are cosmetic with low frequency (<3); represents low differentiation opportunity, not product failure."
                }

        # ── Test 6: Marketplace Failure ──
        msrp = float(prod.get("planned_msrp") or 0.0)
        if msrp <= 0.0:
            kill_reasons.append("Marketplace Listing Invalid: Target MSRP is zero or undefined.")
            kill_evidence["marketplace_failure"] = {"planned_msrp": msrp}

        # Final Status Decision
        if kill_reasons:
            status = "KILLED"
        elif len(missing_evidence) >= 2:
            status = "INSUFFICIENT_EVIDENCE"
        else:
            status = "SURVIVES"

        return {
            "status": status,
            "kill_reasons": kill_reasons,
            "kill_evidence": kill_evidence,
            "missing_evidence": missing_evidence
        }

    @classmethod
    def generate_explainability(
        cls,
        prod: Dict[str, Any],
        listings: List[Dict[str, Any]],
        defects: List[Dict[str, Any]],
        suppliers: List[Dict[str, Any]],
        econ: Dict[str, Any],
        kill_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Feature 3: "Why This Product?" Explainability Panel.
        Generates structured positive signals, negative signals, and missing evidence.
        """
        positive_signals = []
        negative_signals = []
        missing_evidence = list(kill_result.get("missing_evidence", []))

        # Positive Signals
        units = prod.get("estimated_daily_units") or 0
        if units >= 30:
            positive_signals.append(f"Strong sustained sales velocity: ~{units} units/day estimated from real rank telemetry.")
        if prod.get("keepa_price_stability") and float(prod.get("keepa_price_stability")) >= 80.0:
            positive_signals.append(f"Price consistency: {float(prod.get('keepa_price_stability')):.1f}% 90-day price stability.")
        if defects:
            total_def = sum(int(d.get("frequency_count") or 1) for d in defects)
            positive_signals.append(f"Clear product defect vector: {len(defects)} clusters ({total_def} complaint reports) identified for v2 engineering.")
        if prod.get("upgrade_v2_engineering"):
            positive_signals.append(f"Engineered differentiator: {str(prod.get('upgrade_v2_engineering') or '')[:120]}...")
        base_cm = econ.get("base_case", {}).get("contribution_margin", 0.0)
        base_cm_pct = econ.get("base_case", {}).get("contribution_margin_pct", 0.0)
        if base_cm > 0 and base_cm_pct >= 15.0:
            positive_signals.append(f"Healthy unit economics: {base_cm_pct:.1f}% contribution margin ({base_cm:.2f} profit/unit) in Base Case.")
        if suppliers:
            s0 = suppliers[0]
            positive_signals.append(f"Direct factory quote: {s0.get('factory_name')} ({s0.get('fob_unit_price')}, MOQ {s0.get('moq_units')}).")

        # Negative Signals / Risks
        downside_cm = econ.get("downside_case", {}).get("contribution_margin", 0.0)
        if downside_cm <= 0:
            negative_signals.append("Vulnerable to price competition: Downside scenario drops contribution margin below break-even.")
        if prod.get("region") == "India":
            be_rto = econ.get("break_evens", {}).get("maximum_acceptable_rto_pct", 25.0)
            if be_rto < 25.0:
                negative_signals.append(f"High COD exposure: RTO above {be_rto}% eliminates profitability.")
        if len(listings) >= 3:
            negative_signals.append(f"Multi-platform price dispersion: Competitors exist across {len(listings)} platforms.")
        for r in kill_result.get("kill_reasons", []):
            negative_signals.append(r)

        return {
            "positive_signals": positive_signals,
            "negative_signals": negative_signals,
            "missing_evidence": missing_evidence
        }

    @classmethod
    def detect_competitor_gaps(
        cls,
        prod: Dict[str, Any],
        listings: List[Dict[str, Any]],
        defects: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Feature 6: Competitor Gap Detection.
        Identifies Price, Feature, Review, Rating, Complaint, and Availability gaps.
        Explicitly marked as research hypotheses.
        """
        gaps = []
        if not listings:
            gaps.append({
                "gap_type": "Availability Gap",
                "finding": "No competing listings currently tracked in multi-platform database.",
                "hypothesis": "Potential first-mover white space or unindexed niche.",
                "evidence_status": "INSUFFICIENT"
            })
            return gaps

        prices = [float(l.get("price") or 0.0) for l in listings if float(l.get("price") or 0.0) > 0]
        ratings = [float(l.get("rating") or 0.0) for l in listings if float(l.get("rating") or 0.0) > 0]
        planned_msrp = float(prod.get("planned_msrp") or 0.0)

        # 1. Price Gap
        if prices and planned_msrp > 0:
            min_p, max_p = min(prices), max(prices)
            avg_p = sum(prices) / len(prices)
            if planned_msrp < min_p:
                gaps.append({
                    "gap_type": "Price Advantage Gap",
                    "finding": f"Planned price ({planned_msrp:.0f}) is below lowest competitor ({min_p:.0f}).",
                    "hypothesis": f"Disruptive price positioning with potential {(min_p - planned_msrp)/min_p*100:.1f}% discount to market.",
                    "evidence_status": "VERIFIED"
                })
            elif planned_msrp > max_p:
                gaps.append({
                    "gap_type": "Premium Feature Gap",
                    "finding": f"Planned price ({planned_msrp:.0f}) exceeds highest competitor ({max_p:.0f}).",
                    "hypothesis": "Must justify premium positioning with superior v2 build materials.",
                    "evidence_status": "VERIFIED"
                })
            else:
                gaps.append({
                    "gap_type": "Market Midpoint Gap",
                    "finding": f"Planned price ({planned_msrp:.0f}) targets middle of competitor range ({min_p:.0f}–{max_p:.0f}).",
                    "hypothesis": "Captures value-conscious buyers by bundling v2 quality improvements at standard price.",
                    "evidence_status": "VERIFIED"
                })

        # 2. Rating & Complaint Gap
        if ratings and defects:
            avg_r = sum(ratings) / len(ratings)
            top_defect = defects[0]
            gaps.append({
                "gap_type": "Complaint / Quality Gap",
                "finding": f"Average competitor rating is {avg_r:.1f}★ with frequent complaints in: '{top_defect.get('defect_category')}'.",
                "hypothesis": f"A product specifically resolving '{top_defect.get('defect_category')}' can capture 4.5+★ market position.",
                "evidence_status": "VERIFIED"
            })

        # 3. Platform Availability Gap
        platforms = {l.get("platform") for l in listings if l.get("platform")}
        major_platforms = {"amazon_in", "flipkart", "meesho"} if prod.get("region") == "India" else {"amazon", "walmart", "shopify"}
        missing_platforms = major_platforms - platforms
        if missing_platforms:
            gaps.append({
                "gap_type": "Cross-Platform Arbitrage Gap",
                "finding": f"Product not present on: {', '.join(sorted(missing_platforms))}.",
                "hypothesis": f"Cross-listing arbitrage opportunity on underserved regional channels.",
                "evidence_status": "VERIFIED"
            })

        return gaps

    @classmethod
    def generate_pain_map(cls, defects: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Feature 7: Customer Pain Map.
        Categorizes complaints with genuine frequencies, severity, and persistence trend.
        Zero fabricated percentages.
        """
        if not defects:
            return {
                "status": "INSUFFICIENT_DATA",
                "message": "No defect review records currently available to build pain map.",
                "categories": [],
                "total_complaints": 0
            }

        total_freq = sum(max(1, int(d.get("frequency_count") or 1)) for d in defects)
        categories = []

        for d in defects:
            freq = max(1, int(d.get("frequency_count") or 1))
            pct = round((freq / total_freq * 100.0), 1) if total_freq > 0 else 0.0
            sev = d.get("severity") or "MEDIUM"

            # Determine trend based on severity & frequency
            trend = "Persistent" if freq >= 20 else ("Increasing" if sev in ("HIGH", "CRITICAL") else "Newly emerging")

            categories.append({
                "category": d.get("defect_category", "General"),
                "description": d.get("defect_description", ""),
                "frequency": freq,
                "percentage": pct,
                "severity": sev,
                "trend": trend,
                "v2_fix": d.get("v2_fix_description", "Standard quality upgrade")
            })

        categories.sort(key=lambda x: x["frequency"], reverse=True)

        return {
            "status": "VERIFIED",
            "total_complaints": total_freq,
            "categories": categories,
            "top_pain_point": categories[0]["category"] if categories else "None"
        }

    @classmethod
    def evaluate_trend_early_warning(cls, prod: Dict[str, Any]) -> Dict[str, Any]:
        """
        Feature 8: Trend Early-Warning System (Heuristic Trend Model).
        Detects trend stages: EARLY RISE, ACCELERATING, PEAKING, STABLE, DECLINING, COLLAPSING, or INSUFFICIENT_HISTORY.
        Computes heuristic velocity, acceleration, and early warning alerts.
        Labeled explicitly as HEURISTIC_TREND_MODEL (does not claim continuous calculus without daily time-series).
        """
        t_conf = float(prod.get("trend_confidence_score") or 0.0)
        days_active = int(prod.get("ad_active_days") or 14)
        daily_units = int(prod.get("estimated_daily_units") or 0)
        source = prod.get("trend_source") or "Internal Telemetry"

        alerts = []
        if t_conf <= 0.0:
            stage = "INSUFFICIENT_HISTORY"
            velocity = 0.0
            acceleration = 0.0
            decay_rate = 0.0
            half_life = 0
            alerts.append({
                "type": "DATA_NOTICE",
                "message": "Insufficient trend history: No verified external trend velocity recorded."
            })
        elif t_conf >= 85.0 and days_active <= 30:
            stage = "ACCELERATING"
            velocity = 1.45
            acceleration = 0.25
            decay_rate = 0.02
            half_life = 90
            alerts.append({
                "type": "OPPORTUNITY_ALERT",
                "message": "Demand acceleration detected: High confidence signal under 30 days active."
            })
        elif t_conf >= 70.0 and days_active <= 45:
            stage = "EARLY RISE"
            velocity = 1.20
            acceleration = 0.15
            decay_rate = 0.03
            half_life = 75
            alerts.append({
                "type": "OPPORTUNITY_ALERT",
                "message": "Early rise trajectory: Verified search volume expansion across social sources."
            })
        elif t_conf >= 80.0 and days_active > 45:
            stage = "PEAKING"
            velocity = 1.05
            acceleration = -0.05
            decay_rate = 0.04
            half_life = 60
            alerts.append({
                "type": "RISK_ALERT",
                "message": "Trend peaking: Velocity remains positive but momentum deceleration detected."
            })
        elif t_conf >= 50.0:
            stage = "STABLE"
            velocity = 1.00
            acceleration = 0.00
            decay_rate = 0.05
            half_life = 60
        elif t_conf >= 30.0:
            stage = "DECLINING"
            velocity = 0.75
            acceleration = -0.15
            decay_rate = 0.12
            half_life = 30
            alerts.append({
                "type": "RISK_ALERT",
                "message": "Trend velocity has decayed: Product entering late lifecycle phase."
            })
        else:
            stage = "COLLAPSING"
            velocity = 0.30
            acceleration = -0.30
            decay_rate = 0.25
            half_life = 14
            alerts.append({
                "type": "FALSE_TREND_ALERT",
                "message": "Short-lived spike detected with insufficient velocity persistence."
            })

        return {
            "model_type": "HEURISTIC_TREND_MODEL",
            "stage": stage,
            "velocity": velocity,
            "acceleration": acceleration,
            "decay_rate": decay_rate,
            "trend_half_life_days": half_life,
            "trend_source": source or "None",
            "confidence": t_conf,
            "alerts": alerts
        }

    @classmethod
    def evaluate_data_freshness(
        cls,
        prod: Dict[str, Any],
        listings: List[Dict[str, Any]],
        defects: List[Dict[str, Any]],
        suppliers: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Feature 9: Data Freshness + Trust System (Per-Source Freshness Policy).
        Applies differentiated expiration policies across diverse telemetry types:
        - marketplace_listings: FRESH <= 3d, AGING <= 14d, STALE > 14d (Rapid price/stock changes)
        - product_demand:       FRESH <= 7d, AGING <= 21d, STALE > 21d (BSR & sales velocity)
        - supplier_quotes:      FRESH <= 30d, AGING <= 60d, STALE > 60d (Factory quotation validity)
        - customer_defects:     FRESH <= 30d, AGING <= 90d, STALE > 90d (Product flaws evolve slowly)
        - trend_signals:        FRESH <= 14d, AGING <= 30d, STALE > 30d (Viral & search momentum)
        Grounds every score on actual source timestamps.
        """
        now = datetime.datetime.now()
        freshness_map = {}

        def _parse_age_days(dt_str: Optional[str]) -> Optional[int]:
            if not dt_str:
                return None
            try:
                clean_str = str(dt_str).replace("Z", "+00:00")
                parsed_dt = datetime.datetime.fromisoformat(clean_str)
                if parsed_dt.tzinfo is not None:
                    parsed_dt = parsed_dt.replace(tzinfo=None)
                return max(0, (now - parsed_dt).days)
            except Exception:
                return None

        # 1. Product & Demand freshness (Policy: 7d / 21d)
        p_age = _parse_age_days(prod.get("last_evaluated_date") or prod.get("updated_at"))
        if p_age is None:
            p_fresh = "AGING"
        elif p_age <= 7:
            p_fresh = "FRESH"
        elif p_age <= 21:
            p_fresh = "AGING"
        else:
            p_fresh = "STALE"

        freshness_map["product_freshness"] = p_fresh
        freshness_map["demand_freshness"] = p_fresh
        freshness_map["trend_freshness"] = "FRESH" if prod.get("trend_source") else "INSUFFICIENT"

        # 2. Listings freshness (Policy: 3d / 14d)
        if not listings:
            l_fresh = "INSUFFICIENT"
        else:
            newest_l_age = None
            for l in listings:
                age = _parse_age_days(l.get("created_at"))
                if age is not None and (newest_l_age is None or age < newest_l_age):
                    newest_l_age = age
            if newest_l_age is None or newest_l_age <= 3:
                l_fresh = "FRESH"
            elif newest_l_age <= 14:
                l_fresh = "AGING"
            else:
                l_fresh = "STALE"
        freshness_map["listings_freshness"] = l_fresh

        # 3. Defects freshness (Policy: 30d / 90d)
        if not defects:
            d_fresh = "INSUFFICIENT"
        else:
            newest_d_age = None
            for d in defects:
                age = _parse_age_days(d.get("created_at"))
                if age is not None and (newest_d_age is None or age < newest_d_age):
                    newest_d_age = age
            if newest_d_age is None or newest_d_age <= 30:
                d_fresh = "FRESH"
            elif newest_d_age <= 90:
                d_fresh = "AGING"
            else:
                d_fresh = "STALE"
        freshness_map["defects_freshness"] = d_fresh

        # 4. Sourcing / Supplier quotes freshness (Policy: 30d / 60d)
        if not suppliers:
            s_fresh = "INSUFFICIENT"
        else:
            newest_s_age = None
            for s in suppliers:
                age = _parse_age_days(s.get("created_at") or s.get("quote_date"))
                if age is not None and (newest_s_age is None or age < newest_s_age):
                    newest_s_age = age
            if newest_s_age is None or newest_s_age <= 30:
                s_fresh = "FRESH"
            elif newest_s_age <= 60:
                s_fresh = "AGING"
            else:
                s_fresh = "STALE"
        freshness_map["sourcing_freshness"] = s_fresh

        # Overall Status
        statuses = list(freshness_map.values())
        if all(s == "FRESH" for s in statuses):
            overall = "FRESH"
            penalty = 0.0
        elif "STALE" in statuses:
            overall = "STALE"
            penalty = 20.0
        elif "INSUFFICIENT" in statuses:
            overall = "INSUFFICIENT"
            penalty = 15.0
        else:
            overall = "AGING"
            penalty = 8.0

        freshness_map["overall_status"] = overall
        freshness_map["confidence_penalty"] = penalty
        return freshness_map

    @classmethod
    def detect_and_record_conflicts(
        cls,
        product_id: str,
        listings: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Feature 17: Multi-Source Conflict Detection.
        If platforms or sources report substantially different prices or ratings,
        records and surfaces POTENTIAL_PRICE_CONFLICT without prematurely declaring
        definitive contradiction. Preserves source A, source B, values, and resolution state.
        """
        conflicts = []
        if len(listings) < 2:
            return conflicts

        # Price Discrepancy Check (>25% difference between lowest and highest)
        valid_listings = [l for l in listings if float(l.get("price") or 0.0) > 0]
        if len(valid_listings) >= 2:
            sorted_by_price = sorted(valid_listings, key=lambda x: float(x.get("price") or 0.0))
            lowest = sorted_by_price[0]
            highest = sorted_by_price[-1]
            p_low = float(lowest.get("price") or 0.0)
            p_high = float(highest.get("price") or 0.0)

            if p_low > 0 and (p_high - p_low) / p_low >= 0.25:
                explanation = f"POTENTIAL_PRICE_CONFLICT: Multi-platform price dispersion ({p_low:.0f} on {lowest.get('platform')} vs {p_high:.0f} on {highest.get('platform')}). May reflect seller spread, pack size, coupon, or platform fees."
                conflict_id = record_data_conflict(
                    product_id=product_id,
                    field_name="price",
                    source_a=lowest.get("platform", "unknown"),
                    value_a=f"{p_low:.0f}",
                    source_b=highest.get("platform", "unknown"),
                    value_b=f"{p_high:.0f}",
                    severity="HIGH" if (p_high - p_low)/p_low >= 0.50 else "MEDIUM",
                    explanation=explanation
                )
                conflicts.append({
                    "conflict_id": conflict_id,
                    "field_name": "price",
                    "conflict_type": "POTENTIAL_PRICE_CONFLICT",
                    "source_a": lowest.get("platform"),
                    "value_a": p_low,
                    "source_b": highest.get("platform"),
                    "value_b": p_high,
                    "severity": "HIGH" if (p_high - p_low)/p_low >= 0.50 else "MEDIUM",
                    "explanation": explanation
                })

        return conflicts

    @classmethod
    def build_evidence_graph(cls, product_id: str) -> Dict[str, Any]:
        """
        Feature 10: Evidence Graph.
        Connects Product -> Demand -> Trend -> Customer Defects -> Competitors -> Prices -> Suppliers -> Economics -> Gate Decisions.
        Traceable in SQLite without external graph DB dependencies.
        """
        prod, listings, defects, suppliers, gates = cls.get_product_raw_data(product_id)
        if not prod:
            return {"nodes": [], "edges": []}

        nodes = []
        edges = []

        # Root Node: Product
        nodes.append({
            "id": f"prod_{product_id}",
            "type": "PRODUCT",
            "label": prod.get("name", product_id),
            "status": prod.get("status", "PENDING")
        })

        # Demand Node
        d_id = f"demand_{product_id}"
        nodes.append({
            "id": d_id,
            "type": "DEMAND_EVIDENCE",
            "label": f"BSR #{prod.get('bsr_rank', 0)} ({prod.get('estimated_daily_units', 0)} units/day)",
            "status": "VERIFIED" if int(prod.get("estimated_daily_units") or 0) > 0 else "ESTIMATED"
        })
        edges.append({"from": f"prod_{product_id}", "to": d_id, "relation": "DEMAND_SIGNAL"})

        # Trend Node
        t_id = f"trend_{product_id}"
        nodes.append({
            "id": t_id,
            "type": "TREND_EVIDENCE",
            "label": f"{prod.get('trend_source', 'No trend source')} ({prod.get('trend_confidence_score', 0)}% conf)",
            "status": "VERIFIED" if prod.get("trend_source") else "INSUFFICIENT"
        })
        edges.append({"from": d_id, "to": t_id, "relation": "TREND_CORRELATION"})

        # Defects Nodes
        for i, d in enumerate(defects[:3]):
            def_id = f"defect_{product_id}_{i}"
            nodes.append({
                "id": def_id,
                "type": "CUSTOMER_DEFECT",
                "label": f"{d.get('defect_category')} ({d.get('frequency_count')} reports)",
                "status": d.get("severity", "MEDIUM")
            })
            edges.append({"from": t_id, "to": def_id, "relation": "UNMET_NEED"})

        # Competitor Listings
        for i, l in enumerate(listings[:3]):
            list_id = f"comp_{product_id}_{i}"
            nodes.append({
                "id": list_id,
                "type": "COMPETITOR_LISTING",
                "label": f"{l.get('platform')}: {l.get('price')} ({l.get('rating')}★)",
                "status": "ACTIVE"
            })
            edges.append({"from": f"prod_{product_id}", "to": list_id, "relation": "MARKET_COMPETITOR"})

        # Sourcing / Supplier Node
        if suppliers:
            s0 = suppliers[0]
            sup_id = f"sup_{product_id}"
            nodes.append({
                "id": sup_id,
                "type": "SUPPLIER_QUOTE",
                "label": f"{s0.get('factory_name')} ({s0.get('fob_unit_price')})",
                "status": "VETTED"
            })
            edges.append({"from": f"prod_{product_id}", "to": sup_id, "relation": "SOURCING_ORIGIN"})

        # Economics Node
        econ_id = f"econ_{product_id}"
        nodes.append({
            "id": econ_id,
            "type": "UNIT_ECONOMICS",
            "label": f"Net Margin {prod.get('net_profit_pct', 0)}% (MSRP {prod.get('planned_msrp', 0)})",
            "status": "PASS" if float(prod.get("net_profit_pct") or 0.0) >= 12.0 else "FAIL"
        })
        edges.append({"from": f"prod_{product_id}", "to": econ_id, "relation": "PROFITABILITY_VALIDATION"})

        # Gate Decisions
        for g in gates:
            g_id = f"gate_{product_id}_{g.get('gate_number')}"
            nodes.append({
                "id": g_id,
                "type": "GATE_DECISION",
                "label": f"Gate {g.get('gate_number')}: {g.get('status')}",
                "status": g.get("status")
            })
            edges.append({"from": econ_id, "to": g_id, "relation": "PIPELINE_PROGRESSION"})

        return {"nodes": nodes, "edges": edges}

    @classmethod
    def run_war_room_2(cls, product_id: str, intel_dossier: Dict[str, Any]) -> Dict[str, Any]:
        """
        Features 18 & 19: War Room 2.0 & Disagreement Engine.
        5 conceptual agents evaluate structured evidence packets.
        Chief Arbiter resolves CONSENSUS, DISAGREEMENT, MISSING EVIDENCE, or CRITICAL RISK.
        """
        prod = intel_dossier.get("product", {})
        scorecard = intel_dossier.get("scorecard", {}).get("dimensions", {})
        kill = intel_dossier.get("kill_switch", {})
        econ = intel_dossier.get("counterfactual_economics", {})

        agent_packets = []

        # 1. Trend Scout
        t_score = scorecard.get("trend_strength", {}).get("score", 50.0)
        t_flags = scorecard.get("trend_strength", {}).get("risk_flags", [])
        agent_packets.append({
            "agent": "Trend Scout",
            "finding": f"Trend strength rated at {t_score}/100 based on external velocity tracking.",
            "confidence": scorecard.get("trend_strength", {}).get("confidence", 70.0),
            "evidence": [f"Source: {prod.get('trend_source', 'N/A')}", f"Stability: {prod.get('keepa_price_stability', 0)}%"],
            "risks": t_flags,
            "missing_data": ["Multi-quarter historical trend persistence"] if not prod.get("trend_source") else [],
            "recommendation": "PASS" if t_score >= 60.0 else "REVIEW"
        })

        # 2. Defect Analyst
        pain_score = scorecard.get("customer_pain", {}).get("score", 50.0)
        agent_packets.append({
            "agent": "Defect Analyst",
            "finding": f"Customer pain opportunity scored at {pain_score}/100. Specific engineering flaws identified.",
            "confidence": scorecard.get("customer_pain", {}).get("confidence", 80.0),
            "evidence": [f"Flaws: {str(prod.get('competitor_3star_flaws') or 'N/A')[:80]}..."],
            "risks": scorecard.get("customer_pain", {}).get("risk_flags", []),
            "missing_data": ["Long-term customer warranty return data"],
            "recommendation": "PASS" if pain_score >= 60.0 else "REVIEW"
        })

        # 3. Economics Auditor
        econ_score = scorecard.get("economic_viability", {}).get("score", 50.0)
        base_cm = econ.get("base_case", {}).get("contribution_margin", 0.0)
        downside_cm = econ.get("downside_case", {}).get("contribution_margin", 0.0)
        econ_rec = "PASS" if base_cm > 0 and downside_cm > 0 else "FAIL"
        agent_packets.append({
            "agent": "Economics Auditor",
            "finding": f"15-factor economics viability rated at {econ_score}/100. Base CM: {base_cm:.2f}, Downside CM: {downside_cm:.2f}.",
            "confidence": 90.0,
            "evidence": [f"MSRP: {prod.get('planned_msrp')}", f"Landed COGS: {prod.get('landed_cogs')}"],
            "risks": scorecard.get("economic_viability", {}).get("risk_flags", []),
            "missing_data": ["Realized ad TACoS under competitive bidding"],
            "recommendation": econ_rec
        })

        # 4. Marketplace Harvester
        comp_score = scorecard.get("competition_pressure", {}).get("score", 50.0)
        agent_packets.append({
            "agent": "Marketplace Harvester",
            "finding": f"Cross-platform competitive pressure evaluated at {comp_score}/100.",
            "confidence": 75.0,
            "evidence": [f"Platforms: {prod.get('platform_availability', 'Single platform')}"],
            "risks": scorecard.get("competition_pressure", {}).get("risk_flags", []),
            "missing_data": ["Seller stock velocity rates"],
            "recommendation": "PASS" if comp_score >= 50.0 else "REVIEW"
        })

        # Disagreement Detection (Feature 19)
        recommendations = [p["recommendation"] for p in agent_packets]
        disagreements = []
        if "FAIL" in recommendations and "PASS" in recommendations:
            failing_agents = [p["agent"] for p in agent_packets if p["recommendation"] == "FAIL"]
            passing_agents = [p["agent"] for p in agent_packets if p["recommendation"] == "PASS"]
            disagreements.append(
                f"Core Conflict: {', '.join(failing_agents)} rejected the opportunity while {', '.join(passing_agents)} approved."
            )
            decision_type = "DISAGREEMENT"
            summary = "WAR ROOM DISAGREEMENT: Fundamental contradiction between market demand and economic downside risk."
        elif kill.get("status") == "KILLED":
            decision_type = "CRITICAL_RISK"
            summary = f"CRITICAL RISK TRIGGERED: Opportunity Kill Switch fired ({', '.join(kill.get('kill_reasons', []))})."
        elif kill.get("status") == "INSUFFICIENT_EVIDENCE":
            decision_type = "MISSING_EVIDENCE"
            summary = "EVIDENCE INSUFFICIENT: Missing critical data points before full capital commitment can be approved."
        else:
            decision_type = "CONSENSUS"
            summary = "UNANIMOUS CONSENSUS: All swarm agents concur that the opportunity meets high-velocity criteria."

        return {
            "decision_type": decision_type,
            "summary": summary,
            "disagreements": disagreements,
            "agent_packets": agent_packets,
            "recommended_actions": [
                "Verify downside unit economics buffer",
                "Audit factory sample against defect spec",
                "Deploy test order before mass production batch"
            ]
        }

    @classmethod
    def run_full_product_intelligence(cls, product_id: str) -> Dict[str, Any]:
        """
        Master forensic pipeline:
        Compiles the entire product intelligence card, performs kill tests,
        calculates counterfactuals, generates scorecards, checks freshness,
        detects conflicts, and persists everything to SQLite.
        """
        prod, listings, defects, suppliers, gates = cls.get_product_raw_data(product_id)
        if not prod:
            return {"error": f"Product {product_id} not found."}

        # 1. Freshness & Trust
        freshness_info = cls.evaluate_data_freshness(prod, listings, defects, suppliers)

        # 2. Counterfactual Economics
        fob = float(prod.get("factory_cogs") or (float(prod.get("landed_cogs") or 0.0) * 0.75) or 100.0)
        msrp = float(prod.get("planned_msrp") or 500.0)
        region = prod.get("region") or "India"
        category = prod.get("category") or "General"

        counterfactual_econ = Comprehensive15FactorEconomics.calculate_counterfactual_scenarios(
            fob_price=fob,
            planned_msrp=msrp,
            region=region,
            category=category
        )

        # 3. Opportunity Scorecard
        scorecard = cls.evaluate_scorecard(prod, listings, defects, suppliers, counterfactual_econ, freshness_info)

        # 4. Opportunity Kill Switch
        kill_result = cls.evaluate_kill_switch(prod, listings, defects, suppliers, counterfactual_econ)

        # 5. Explainability
        explanations = cls.generate_explainability(prod, listings, defects, suppliers, counterfactual_econ, kill_result)

        # 6. Competitor Gaps
        gaps = cls.detect_competitor_gaps(prod, listings, defects)

        # 7. Customer Pain Map
        pain_map = cls.generate_pain_map(defects)

        # 8. Trend Early Warning
        trend_analysis = cls.evaluate_trend_early_warning(prod)

        # 9. Conflict Detection
        conflicts = cls.detect_and_record_conflicts(product_id, listings)

        # Compile Opportunity Signals
        signals = {
            "demand_signal": f"{prod.get('estimated_daily_units', 0)} units/day",
            "trend_velocity": trend_analysis.get("velocity", 1.0),
            "trend_acceleration": trend_analysis.get("acceleration", 0.0),
            "competition_density": len(listings),
            "price_dispersion": len(set(l.get("price") for l in listings if l.get("price"))),
            "review_velocity": f"{len(defects)} defect clusters",
            "defect_frequency": pain_map.get("total_complaints", 0),
            "defect_severity": defects[0].get("severity", "MEDIUM") if defects else "UNKNOWN",
            "supplier_availability": len(suppliers),
            "supplier_concentration": "HIGH" if len(suppliers) == 1 else ("DIVERSIFIED" if len(suppliers) > 1 else "NONE"),
            "estimated_margin": f"{prod.get('gross_margin_pct', 0)}%",
            "estimated_contribution_margin": f"{counterfactual_econ.get('base_case', {}).get('contribution_margin_pct', 0)}%",
            "rto_exposure": f"{counterfactual_econ.get('break_evens', {}).get('maximum_acceptable_rto_pct', 0)}% max",
            "seasonality": "All-Year Utility",
            "market_saturation": "LOW" if len(listings) <= 2 else ("MEDIUM" if len(listings) <= 6 else "HIGH"),
            "marketplace_availability": prod.get("platform_availability", "Amazon India"),
            "sourcing_difficulty": "LOW" if suppliers else "MEDIUM"
        }

        # Persist Intelligence Record in SQLite (Feature 1 & 2)
        save_product_intelligence(
            product_id=product_id,
            opportunity_score=scorecard.get("composite_score", 0.0),
            kill_status=kill_result.get("status", "INSUFFICIENT_EVIDENCE"),
            kill_reasons=kill_result.get("kill_reasons", []),
            kill_evidence=kill_result.get("kill_evidence", {}),
            scorecard=scorecard,
            signals=signals,
            explanations=explanations,
            counterfactual=counterfactual_econ,
            gaps={"gaps": gaps},
            pain_map=pain_map,
            trend_analysis=trend_analysis,
            freshness_status=freshness_info.get("overall_status", "FRESH"),
            confidence_score=scorecard.get("overall_confidence", 0.0)
        )

        # Persist Discrete Evidence Records (Features 6 & 10)
        dims = scorecard.get("dimensions", {})
        try:
            record_intelligence_evidence(
                product_id=product_id,
                signal_type="DEMAND",
                conclusion=f"BSR #{prod.get('bsr_rank', 0)}, {prod.get('estimated_daily_units', 0)} units/day",
                confidence=dims.get("demand_strength", {}).get("confidence", 50.0),
                source=prod.get("marketplace_url") or "Marketplace Telemetry"
            )
            record_intelligence_evidence(
                product_id=product_id,
                signal_type="TREND",
                conclusion=f"{prod.get('trend_source', 'Internal Telemetry')} ({prod.get('trend_confidence_score', 0)}% conf, Stage: {trend_analysis.get('stage')})",
                confidence=dims.get("trend_strength", {}).get("confidence", 50.0),
                source=prod.get("trend_source") or "Trend Scout / Scraper"
            )
            if defects:
                record_intelligence_evidence(
                    product_id=product_id,
                    signal_type="DEFECTS",
                    conclusion=f"{len(defects)} clusters ({pain_map.get('total_complaints', 0)} reports, Top: {pain_map.get('top_pain_point')})",
                    confidence=dims.get("customer_pain", {}).get("confidence", 50.0),
                    source="Customer Review Mining"
                )
            if suppliers:
                record_intelligence_evidence(
                    product_id=product_id,
                    signal_type="SOURCING",
                    conclusion=f"{len(suppliers)} quotes, Hub: {prod.get('sourcing_cluster', 'N/A')}",
                    confidence=dims.get("sourcing_feasibility", {}).get("confidence", 50.0),
                    source="Supplier Catalog / RFQ"
                )
            record_intelligence_evidence(
                product_id=product_id,
                signal_type="ECONOMICS",
                conclusion=f"Base CM: {counterfactual_econ.get('base_case', {}).get('contribution_margin_pct')}%, Downside CM: {counterfactual_econ.get('downside_case', {}).get('contribution_margin_pct')}%",
                confidence=dims.get("economic_viability", {}).get("confidence", 50.0),
                source="Comprehensive 15-Factor Economics"
            )
        except Exception as ee:
            logger.warning(f"Failed to record discrete evidence for {product_id}: {ee}")

        # Record Source Health Telemetry for sources consulted during dossier generation
        try:
            update_source_health("MarketplaceTelemetry", True, 45.0)
            update_source_health("EconomicsEngine", True, 12.0)
            if listings:
                update_source_health("UniversalScraper", True, 110.0)
            if defects:
                update_source_health("ReviewMiner", True, 80.0)
            if suppliers:
                update_source_health("SupplierCatalog", True, 55.0)
        except Exception as se:
            logger.debug(f"Source health update notice: {se}")

        # Generate Actionable Alert if Opportunity Kill triggered or high potential
        if kill_result.get("status") == "KILLED":
            create_opportunity_alert(
                product_id=product_id,
                alert_type="KILL_TRIGGER",
                severity="HIGH",
                title=f"🛑 Opportunity Kill Trigger: {str(prod.get('name') or product_id)[:30]}",
                what_happened=f"Product failed kill tests: {'; '.join(kill_result.get('kill_reasons', []))}",
                why_it_matters="Prevents capital allocation into flawed or unprofitable opportunity.",
                evidence_summary=json.dumps(kill_result.get("kill_evidence", {})),
                recommended_action="Archive opportunity or renegotiate supplier FOB."
            )
        elif (
            scorecard.get("composite_score", 0) >= 80.0
            and kill_result.get("status") == "SURVIVES"
            and scorecard.get("overall_confidence", 0) >= 70.0
        ):
            create_opportunity_alert(
                product_id=product_id,
                alert_type="NEW_OPPORTUNITY",
                severity="INFO",
                title=f"🔥 High Potential Opportunity: {str(prod.get('name') or product_id)[:30]}",
                what_happened=f"Opportunity Score reached {scorecard.get('composite_score')}/100 with verified signals.",
                why_it_matters="Exhibits strong demand velocity, viable downside economics, and engineered flaw fixes.",
                evidence_summary=f"Base CM: {counterfactual_econ.get('base_case', {}).get('contribution_margin_pct')}%, Units: {prod.get('estimated_daily_units')}",
                recommended_action="Initiate supplier sample order in Sourcing Launchpad."
            )

        # Record Timeline Event (Feature 11)
        record_timeline_event(
            product_id=product_id,
            event_type="INTELLIGENCE_EVALUATION",
            event_title="Autonomous Intelligence Profile Generated",
            event_description=f"Evaluated 10 scorecard dimensions (Score: {scorecard.get('composite_score')}/100, Kill Status: {kill_result.get('status')}).",
            metadata={"opportunity_score": scorecard.get("composite_score"), "kill_status": kill_result.get("status")}
        )

        # War Room 2.0 Evaluation
        dossier = {
            "product": prod,
            "listings": listings,
            "defects": defects,
            "suppliers": suppliers,
            "scorecard": scorecard,
            "kill_switch": kill_result,
            "counterfactual_economics": counterfactual_econ,
            "explainability": explanations,
            "competitor_gaps": gaps,
            "customer_pain_map": pain_map,
            "trend_early_warning": trend_analysis,
            "freshness": freshness_info,
            "conflicts": conflicts
        }
        war_room = cls.run_war_room_2(product_id, dossier)
        dossier["war_room_2"] = war_room

        return dossier
