"""
core/economics_engine.py — Advanced 15-Factor 3-Scenario Unit Economics Engine for APRS V6 Pro.

Calculates:
- Conservative, Expected, and Upside scenarios simultaneously.
- Volumetric freight calculation: max(Actual Weight, L x W x H / 5000) * Freight Rate.
- Lead-time vs. Trend decay velocity penalty.
- Realistic Indian & Global marketplace schedules (Amazon, Flipkart, Meesho, D2C).
- COD fees, RTO reserves, return fraud/wardrobing buffers, and net contribution margins.
"""
from typing import Dict, Any, Optional
import math
from config.settings import REGIONAL_PROFILES
from core.models import ScenarioEconomics, EconomicsAssessment


class Comprehensive15FactorEconomics:
    """
    15-Factor 3-Scenario Unit Economics Engine.
    Evaluates Conservative, Expected, and Upside contribution margins.
    """

    # Category commission benchmarks
    COMMISSION_RATES = {
        "Kitchen": 0.12,
        "Home": 0.135,
        "Beauty": 0.10,
        "Electronics": 0.08,
        "Fitness": 0.12,
        "Apparel": 0.17,
        "General": 0.13
    }

    # Category RTO and return fraud benchmarks (India / Global)
    CATEGORY_RTO_RATES = {
        "Apparel": 0.28,
        "Beauty": 0.18,
        "Kitchen": 0.14,
        "Home": 0.15,
        "Electronics": 0.12,
        "Fitness": 0.15,
        "General": 0.16
    }

    @classmethod
    def calculate_scenario(
        cls,
        scenario_name: str,
        fob_price: float,
        planned_msrp: float,
        region: str = "India",
        category: str = "General",
        length_cm: float = 20.0,
        width_cm: float = 15.0,
        height_cm: float = 10.0,
        actual_weight_kg: float = 0.5,
        moq_units: int = 300,
        mold_tooling_cost: float = 0.0,
        est_ad_tacos_pct: float = 0.18,
        is_cod: bool = True,
        lead_time_days: int = 30,
        trend_half_life_days: int = 90
    ) -> ScenarioEconomics:
        """Calculates a single scenario economics breakdown."""
        reg_cfg = REGIONAL_PROFILES.get(region, REGIONAL_PROFILES.get("India", {}))
        currency = reg_cfg.get("currency", "INR")
        gst_rate = reg_cfg.get("gst_vat_rate", 0.18)

        # Scenario Multipliers
        if scenario_name == "Conservative":
            msrp = planned_msrp * 0.92  # 8% price depression from competitors
            fob = fob_price * 1.10      # 10% higher raw material/BOM cost
            tacos = min(0.35, est_ad_tacos_pct * 1.30)
            rto_rate_mult = 1.25
        elif scenario_name == "Upside":
            msrp = planned_msrp * 1.08  # Premium packaging / brand power
            fob = fob_price * 0.90      # Volume discounts at scale
            tacos = max(0.10, est_ad_tacos_pct * 0.80)
            rto_rate_mult = 0.85
        else:  # Expected
            msrp = planned_msrp
            fob = fob_price
            tacos = est_ad_tacos_pct
            rto_rate_mult = 1.0

        # Factor 3: Packaging & Inserts
        packaging_cost = 25.0 if currency == "INR" else 0.40

        # Factor 4: Volumetric Freight Calculation
        volumetric_weight_kg = (length_cm * width_cm * height_cm) / 5000.0
        chargeable_weight_kg = max(actual_weight_kg, volumetric_weight_kg)
        freight_rate_per_kg = 75.0 if currency == "INR" else 4.50  # Domestic / Sea Freight
        volumetric_freight = chargeable_weight_kg * freight_rate_per_kg

        # Factor 5: Inbound Customs / Regional Tariff
        tariff_rate = 0.0 if region == "India" else 0.075  # 7.5% for international ocean freight
        customs_duty = fob * tariff_rate

        # Factor 13: Mold / Tooling Amortization per unit
        amortized_units = max(1000, moq_units * 3)
        mold_per_unit = mold_tooling_cost / amortized_units if mold_tooling_cost > 0 else 0.0

        # Landed COGS
        landed_cogs = fob + packaging_cost + volumetric_freight + customs_duty + mold_per_unit
        gross_profit = max(0.0, msrp - landed_cogs)
        gross_margin_pct = (gross_profit / msrp * 100.0) if msrp > 0 else 0.0

        # Factor 6: Marketplace Commission
        comm_pct = cls.COMMISSION_RATES.get(category, 0.13)
        marketplace_commission = msrp * comm_pct

        # Factor 7: FBA / 3PL Fulfillment Fee
        if currency == "INR":
            fulfillment_fee = 55.0 + (chargeable_weight_kg * 20.0)
        else:
            fulfillment_fee = 3.50 + (chargeable_weight_kg * 1.20)

        # Factor 8: Payment Gateway / COD Fee
        if region == "India":
            # 60% COD, 40% Prepaid
            payment_or_cod_fee = (0.40 * (msrp * 0.02)) + (0.60 * (38.0 + (msrp * 0.02)))
        else:
            payment_or_cod_fee = msrp * 0.029 + (0.30 if currency == "USD" else 20.0)

        # Factor 9: RTO Reserve (Reverse logistics cost on non-delivered orders)
        base_rto_pct = cls.CATEGORY_RTO_RATES.get(category, 0.16) * rto_rate_mult
        reverse_shipping_cost = fulfillment_fee * 1.15
        rto_reserve = base_rto_pct * reverse_shipping_cost if region == "India" else base_rto_pct * (fulfillment_fee * 0.5)

        # Factor 10: Return Fraud & Customer Wardrobing Reserve
        fraud_buffer_pct = 0.04 if category != "Apparel" else 0.08
        return_fraud_reserve = msrp * fraud_buffer_pct

        # Factor 11: Ad Spend (TACoS)
        ad_tacos_reserve = msrp * tacos

        # Factor 12: Damage & Defect Reserve
        damage_reserve = landed_cogs * 0.03

        # Factor 14: Net GST / Tax Burden
        # Output GST on MSRP minus Input Tax Credit (ITC on COGS, Ads, Logistics)
        output_tax = msrp * (gst_rate / (1.0 + gst_rate))
        itc_credit = (landed_cogs + fulfillment_fee + marketplace_commission + ad_tacos_reserve) * (gst_rate / (1.0 + gst_rate)) * 0.85
        net_tax_burden = max(0.0, output_tax - itc_credit)

        # Total Variable Costs & Contribution Margin
        total_variable_cost = (
            landed_cogs + marketplace_commission + fulfillment_fee +
            payment_or_cod_fee + rto_reserve + return_fraud_reserve +
            ad_tacos_reserve + damage_reserve + net_tax_burden
        )

        net_profit = msrp - total_variable_cost
        net_profit_pct = (net_profit / msrp * 100.0) if msrp > 0 else 0.0
        contribution_margin = msrp - total_variable_cost

        # Capital required for first batch (MOQ units * Landed COGS + 30 days initial Ad buffer)
        first_batch_capital = (moq_units * landed_cogs) + (moq_units * ad_tacos_reserve * 0.5)

        # Status: Conservative requires Net Margin >= 12% and Gross Margin >= 55%
        pass_threshold = 12.0 if scenario_name != "Upside" else 15.0
        status = "PASS" if (net_profit_pct >= pass_threshold and gross_margin_pct >= 50.0) else "FAIL"

        return ScenarioEconomics(
            scenario_name=scenario_name,
            planned_msrp=round(msrp, 2),
            fob_price=round(fob, 2),
            landed_cogs=round(landed_cogs, 2),
            gross_profit=round(gross_profit, 2),
            gross_margin_pct=round(gross_margin_pct, 2),
            volumetric_freight_cost=round(volumetric_freight, 2),
            marketplace_commission=round(marketplace_commission, 2),
            fulfillment_fee=round(fulfillment_fee, 2),
            payment_or_cod_fee=round(payment_or_cod_fee, 2),
            rto_reserve=round(rto_reserve, 2),
            return_fraud_reserve=round(return_fraud_reserve, 2),
            ad_tacos_reserve=round(ad_tacos_reserve, 2),
            net_tax_burden=round(net_tax_burden, 2),
            total_variable_cost=round(total_variable_cost, 2),
            net_profit=round(net_profit, 2),
            net_profit_pct=round(net_profit_pct, 2),
            contribution_margin=round(contribution_margin, 2),
            first_batch_capital=round(first_batch_capital, 2),
            status=status
        )

    @classmethod
    def evaluate_15_factor_economics(
        cls,
        product_id: str,
        fob_price: float,
        planned_msrp: float,
        region: str = "India",
        category: str = "General",
        length_cm: float = 20.0,
        width_cm: float = 15.0,
        height_cm: float = 10.0,
        actual_weight_kg: float = 0.5,
        moq_units: int = 300,
        mold_tooling_cost: float = 0.0,
        est_ad_tacos_pct: float = 0.18,
        lead_time_days: int = 30,
        trend_half_life_days: int = 90
    ) -> EconomicsAssessment:
        """
        Generates complete 15-factor 3-scenario economics assessment.
        Factor 15: Rejects products if Lead Time > Trend Half Life.
        """
        reg_cfg = REGIONAL_PROFILES.get(region, REGIONAL_PROFILES.get("India", {}))
        currency = reg_cfg.get("currency", "INR")

        cons = cls.calculate_scenario(
            scenario_name="Conservative", fob_price=fob_price, planned_msrp=planned_msrp,
            region=region, category=category, length_cm=length_cm, width_cm=width_cm,
            height_cm=height_cm, actual_weight_kg=actual_weight_kg, moq_units=moq_units,
            mold_tooling_cost=mold_tooling_cost, est_ad_tacos_pct=est_ad_tacos_pct,
            lead_time_days=lead_time_days, trend_half_life_days=trend_half_life_days
        )
        exp = cls.calculate_scenario(
            scenario_name="Expected", fob_price=fob_price, planned_msrp=planned_msrp,
            region=region, category=category, length_cm=length_cm, width_cm=width_cm,
            height_cm=height_cm, actual_weight_kg=actual_weight_kg, moq_units=moq_units,
            mold_tooling_cost=mold_tooling_cost, est_ad_tacos_pct=est_ad_tacos_pct,
            lead_time_days=lead_time_days, trend_half_life_days=trend_half_life_days
        )
        ups = cls.calculate_scenario(
            scenario_name="Upside", fob_price=fob_price, planned_msrp=planned_msrp,
            region=region, category=category, length_cm=length_cm, width_cm=width_cm,
            height_cm=height_cm, actual_weight_kg=actual_weight_kg, moq_units=moq_units,
            mold_tooling_cost=mold_tooling_cost, est_ad_tacos_pct=est_ad_tacos_pct,
            lead_time_days=lead_time_days, trend_half_life_days=trend_half_life_days
        )

        # Factor 15: Lead Time Risk Check
        lead_time_risk_factor = min(1.0, lead_time_days / float(max(1, trend_half_life_days)))
        lead_time_pass = lead_time_days <= (trend_half_life_days * 0.70)  # Must arrive within 70% of trend life

        is_financially_viable = (cons.status == "PASS" or exp.status == "PASS") and lead_time_pass

        # Composite score
        score_base = (exp.net_profit_pct * 2.5) + (exp.gross_margin_pct * 0.5)
        if not lead_time_pass:
            score_base -= 25.0
        composite_score = max(0.0, min(100.0, score_base))

        recommendation = "PASS" if is_financially_viable else "FAIL"

        return EconomicsAssessment(
            product_id=product_id,
            region=region,
            currency=currency,
            conservative=cons,
            expected=exp,
            upside=ups,
            lead_time_days=lead_time_days,
            trend_half_life_days=trend_half_life_days,
            lead_time_risk_factor=round(lead_time_risk_factor, 2),
            is_financially_viable=is_financially_viable,
            composite_score=round(composite_score, 1),
            recommendation=recommendation
        )

    @classmethod
    def calculate_custom_scenario(
        cls,
        scenario_name: str,
        fob_price: float,
        planned_msrp: float,
        region: str = "India",
        category: str = "General",
        length_cm: float = 20.0,
        width_cm: float = 15.0,
        height_cm: float = 10.0,
        actual_weight_kg: float = 0.5,
        moq_units: int = 300,
        mold_tooling_cost: float = 0.0,
        est_ad_tacos_pct: float = 0.18,
        price_multiplier: float = 1.0,
        fob_multiplier: float = 1.0,
        freight_multiplier: float = 1.0,
        rto_multiplier: float = 1.0,
        returns_multiplier: float = 1.0,
        ad_multiplier: float = 1.0,
    ) -> Dict[str, Any]:
        """Calculates a stress-tested scenario applying specific adverse/favorable multipliers."""
        reg_cfg = REGIONAL_PROFILES.get(region, REGIONAL_PROFILES.get("India", {}))
        currency = reg_cfg.get("currency", "INR")
        gst_rate = reg_cfg.get("gst_vat_rate", 0.18)

        msrp = max(1.0, planned_msrp * price_multiplier)
        fob = max(0.0, fob_price * fob_multiplier)
        packaging_cost = 25.0 if currency == "INR" else 0.40

        volumetric_weight_kg = (length_cm * width_cm * height_cm) / 5000.0
        chargeable_weight_kg = max(actual_weight_kg, volumetric_weight_kg)
        freight_rate_per_kg = (75.0 if currency == "INR" else 4.50) * freight_multiplier
        volumetric_freight = chargeable_weight_kg * freight_rate_per_kg

        tariff_rate = 0.0 if region == "India" else 0.075
        customs_duty = fob * tariff_rate

        amortized_units = max(1000, moq_units * 3)
        mold_per_unit = mold_tooling_cost / amortized_units if mold_tooling_cost > 0 else 0.0

        landed_cogs = fob + packaging_cost + volumetric_freight + customs_duty + mold_per_unit
        gross_profit = max(0.0, msrp - landed_cogs)
        gross_margin_pct = (gross_profit / msrp * 100.0) if msrp > 0 else 0.0

        comm_pct = cls.COMMISSION_RATES.get(category, 0.13)
        marketplace_commission = msrp * comm_pct

        if currency == "INR":
            fulfillment_fee = 55.0 + (chargeable_weight_kg * 20.0)
        else:
            fulfillment_fee = 3.50 + (chargeable_weight_kg * 1.20)

        if region == "India":
            payment_or_cod_fee = (0.40 * (msrp * 0.02)) + (0.60 * (38.0 + (msrp * 0.02)))
        else:
            payment_or_cod_fee = msrp * 0.029 + (0.30 if currency == "USD" else 20.0)

        base_rto_pct = cls.CATEGORY_RTO_RATES.get(category, 0.16) * rto_multiplier
        reverse_shipping_cost = fulfillment_fee * 1.15
        rto_reserve = base_rto_pct * reverse_shipping_cost if region == "India" else base_rto_pct * (fulfillment_fee * 0.5)

        fraud_buffer_pct = (0.04 if category != "Apparel" else 0.08) * returns_multiplier
        return_fraud_reserve = msrp * fraud_buffer_pct

        tacos = min(0.60, est_ad_tacos_pct * ad_multiplier)
        ad_tacos_reserve = msrp * tacos
        damage_reserve = landed_cogs * 0.03

        output_tax = msrp * (gst_rate / (1.0 + gst_rate))
        itc_credit = (landed_cogs + fulfillment_fee + marketplace_commission + ad_tacos_reserve) * (gst_rate / (1.0 + gst_rate)) * 0.85
        net_tax_burden = max(0.0, output_tax - itc_credit)

        total_variable_cost = (
            landed_cogs + marketplace_commission + fulfillment_fee +
            payment_or_cod_fee + rto_reserve + return_fraud_reserve +
            ad_tacos_reserve + damage_reserve + net_tax_burden
        )

        contribution_margin = msrp - total_variable_cost
        contribution_margin_pct = (contribution_margin / msrp * 100.0) if msrp > 0 else 0.0
        net_profit = contribution_margin
        net_profit_pct = contribution_margin_pct

        status = "VIABLE" if contribution_margin > 0 and contribution_margin_pct >= 10.0 else ("MARGINAL" if contribution_margin > 0 else "DEFICIT")

        return {
            "scenario_name": scenario_name,
            "msrp": round(msrp, 2),
            "fob": round(fob, 2),
            "landed_cogs": round(landed_cogs, 2),
            "total_variable_cost": round(total_variable_cost, 2),
            "contribution_margin": round(contribution_margin, 2),
            "contribution_margin_pct": round(contribution_margin_pct, 2),
            "net_margin_pct": round(net_profit_pct, 2),
            "rto_reserve": round(rto_reserve, 2),
            "ad_tacos_reserve": round(ad_tacos_reserve, 2),
            "return_fraud_reserve": round(return_fraud_reserve, 2),
            "freight_cost": round(volumetric_freight, 2),
            "status": status
        }

    @classmethod
    def calculate_counterfactual_scenarios(
        cls,
        fob_price: float,
        planned_msrp: float,
        region: str = "India",
        category: str = "General",
        length_cm: float = 20.0,
        width_cm: float = 15.0,
        height_cm: float = 10.0,
        actual_weight_kg: float = 0.5,
        moq_units: int = 300,
        mold_tooling_cost: float = 0.0,
        est_ad_tacos_pct: float = 0.18
    ) -> Dict[str, Any]:
        """
        Feature 5: Counterfactual Economics Simulation.
        Evaluates Base Case, Downside (-10% price, +10% COGS, +15% freight, +25% RTO, +20% returns, +20% ad),
        Severe Downside (-20% price, +20% COGS, +30% freight, +50% RTO, +40% returns, +40% ad),
        and Upside (+10% price, -10% COGS, -10% freight, -20% RTO, -20% returns, -15% ad).
        Computes exact break-even selling price, break-even FOB, max acceptable CAC, max acceptable RTO, and max return rate.
        """
        fob_price = max(0.0, float(fob_price or 0.0))
        planned_msrp = max(1.0, float(planned_msrp or 1.0))

        base = cls.calculate_custom_scenario(
            scenario_name="Base Case", fob_price=fob_price, planned_msrp=planned_msrp,
            region=region, category=category, length_cm=length_cm, width_cm=width_cm,
            height_cm=height_cm, actual_weight_kg=actual_weight_kg, moq_units=moq_units,
            mold_tooling_cost=mold_tooling_cost, est_ad_tacos_pct=est_ad_tacos_pct,
            price_multiplier=1.0, fob_multiplier=1.0, freight_multiplier=1.0,
            rto_multiplier=1.0, returns_multiplier=1.0, ad_multiplier=1.0
        )

        downside = cls.calculate_custom_scenario(
            scenario_name="Downside Case", fob_price=fob_price, planned_msrp=planned_msrp,
            region=region, category=category, length_cm=length_cm, width_cm=width_cm,
            height_cm=height_cm, actual_weight_kg=actual_weight_kg, moq_units=moq_units,
            mold_tooling_cost=mold_tooling_cost, est_ad_tacos_pct=est_ad_tacos_pct,
            price_multiplier=0.90, fob_multiplier=1.10, freight_multiplier=1.15,
            rto_multiplier=1.25, returns_multiplier=1.20, ad_multiplier=1.20
        )

        severe_downside = cls.calculate_custom_scenario(
            scenario_name="Severe Downside", fob_price=fob_price, planned_msrp=planned_msrp,
            region=region, category=category, length_cm=length_cm, width_cm=width_cm,
            height_cm=height_cm, actual_weight_kg=actual_weight_kg, moq_units=moq_units,
            mold_tooling_cost=mold_tooling_cost, est_ad_tacos_pct=est_ad_tacos_pct,
            price_multiplier=0.80, fob_multiplier=1.20, freight_multiplier=1.30,
            rto_multiplier=1.50, returns_multiplier=1.40, ad_multiplier=1.40
        )

        upside = cls.calculate_custom_scenario(
            scenario_name="Upside Case", fob_price=fob_price, planned_msrp=planned_msrp,
            region=region, category=category, length_cm=length_cm, width_cm=width_cm,
            height_cm=height_cm, actual_weight_kg=actual_weight_kg, moq_units=moq_units,
            mold_tooling_cost=mold_tooling_cost, est_ad_tacos_pct=est_ad_tacos_pct,
            price_multiplier=1.10, fob_multiplier=0.90, freight_multiplier=0.90,
            rto_multiplier=0.80, returns_multiplier=0.80, ad_multiplier=0.85
        )

        # ── Binary Search Break-Even Calculations ──
        # 1. Break-even Selling Price (MSRP where contribution margin is 0)
        safe_msrp = max(1.0, planned_msrp)
        safe_fob = max(0.0, fob_price)
        low_p = max(1.0, safe_msrp * 0.2)
        high_p = max(safe_msrp * 3.0, (safe_fob + 100.0) * 3.0, 100.0)
        if low_p >= high_p:
            high_p = low_p + 100.0
        be_price = safe_msrp
        for _ in range(30):
            mid_p = (low_p + high_p) / 2.0
            res = cls.calculate_custom_scenario(
                "BE_P", fob_price=safe_fob, planned_msrp=mid_p, region=region,
                category=category, length_cm=length_cm, width_cm=width_cm,
                height_cm=height_cm, actual_weight_kg=actual_weight_kg,
                moq_units=moq_units, mold_tooling_cost=mold_tooling_cost,
                est_ad_tacos_pct=est_ad_tacos_pct
            )
            if res["contribution_margin"] < 0:
                low_p = mid_p
            else:
                high_p = mid_p
            be_price = mid_p

        # 2. Break-even COGS (Max FOB where contribution margin >= 0 at current MSRP)
        low_f = 0.0
        high_f = max(safe_fob * 4.0, safe_msrp, 100.0)
        if low_f >= high_f:
            high_f = 100.0
        be_cogs = safe_fob
        for _ in range(30):
            mid_f = (low_f + high_f) / 2.0
            res = cls.calculate_custom_scenario(
                "BE_F", fob_price=mid_f, planned_msrp=safe_msrp, region=region,
                category=category, length_cm=length_cm, width_cm=width_cm,
                height_cm=height_cm, actual_weight_kg=actual_weight_kg,
                moq_units=moq_units, mold_tooling_cost=mold_tooling_cost,
                est_ad_tacos_pct=est_ad_tacos_pct
            )
            if res["contribution_margin"] > 0:
                low_f = mid_f
            else:
                high_f = mid_f
            be_cogs = mid_f

        # 3. Maximum Acceptable CAC (Ad Spend Reserve where CM == 0)
        # Margin without ad spend
        res_no_ad = cls.calculate_custom_scenario(
            "NO_AD", fob_price=fob_price, planned_msrp=planned_msrp, region=region,
            category=category, length_cm=length_cm, width_cm=width_cm,
            height_cm=height_cm, actual_weight_kg=actual_weight_kg,
            moq_units=moq_units, mold_tooling_cost=mold_tooling_cost,
            est_ad_tacos_pct=0.0
        )
        max_cac = max(0.0, res_no_ad["contribution_margin"])

        # 4. Maximum Acceptable RTO rate
        low_rto, high_rto = 0.0, 5.0
        max_rto_mult = 1.0
        for _ in range(25):
            mid_rto = (low_rto + high_rto) / 2.0
            res = cls.calculate_custom_scenario(
                "BE_RTO", fob_price=fob_price, planned_msrp=planned_msrp, region=region,
                category=category, length_cm=length_cm, width_cm=width_cm,
                height_cm=height_cm, actual_weight_kg=actual_weight_kg,
                moq_units=moq_units, mold_tooling_cost=mold_tooling_cost,
                est_ad_tacos_pct=est_ad_tacos_pct, rto_multiplier=mid_rto
            )
            if res["contribution_margin"] > 0:
                low_rto = mid_rto
            else:
                high_rto = mid_rto
            max_rto_mult = mid_rto
        base_cat_rto = cls.CATEGORY_RTO_RATES.get(category, 0.16)
        max_acceptable_rto_pct = min(100.0, round(base_cat_rto * max_rto_mult * 100.0, 1))

        # 5. Maximum Acceptable Return Rate
        low_ret, high_ret = 0.0, 8.0
        max_ret_mult = 1.0
        for _ in range(25):
            mid_ret = (low_ret + high_ret) / 2.0
            res = cls.calculate_custom_scenario(
                "BE_RET", fob_price=fob_price, planned_msrp=planned_msrp, region=region,
                category=category, length_cm=length_cm, width_cm=width_cm,
                height_cm=height_cm, actual_weight_kg=actual_weight_kg,
                moq_units=moq_units, mold_tooling_cost=mold_tooling_cost,
                est_ad_tacos_pct=est_ad_tacos_pct, returns_multiplier=mid_ret
            )
            if res["contribution_margin"] > 0:
                low_ret = mid_ret
            else:
                high_ret = mid_ret
            max_ret_mult = mid_ret
        base_cat_ret = 0.04 if category != "Apparel" else 0.08
        max_acceptable_return_pct = min(100.0, round(base_cat_ret * max_ret_mult * 100.0, 1))

        return {
            "base_case": base,
            "downside_case": downside,
            "severe_downside_case": severe_downside,
            "upside_case": upside,
            "break_evens": {
                "break_even_selling_price": round(be_price, 2),
                "break_even_cogs": round(be_cogs, 2),
                "maximum_acceptable_cac": round(max_cac, 2),
                "maximum_acceptable_rto_pct": max_acceptable_rto_pct,
                "maximum_acceptable_return_rate_pct": max_acceptable_return_pct
            }
        }

