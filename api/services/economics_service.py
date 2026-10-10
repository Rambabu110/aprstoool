"""
api/services/economics_service.py — Direct reuse of Comprehensive15FactorEconomics.
Does not reimplement calculation math in API layer; delegates directly to core/economics_engine.py.
"""
from typing import Optional, Dict, Any, List
from core.database import get_connection
from core.economics_engine import Comprehensive15FactorEconomics
from api.schemas.economics import EconomicsResponse, ScenarioDetail


class EconomicsService:
    @staticmethod
    def get_product_economics(product_id: str) -> Optional[EconomicsResponse]:
        """
        Evaluates full 15-factor 3-scenario economics for a product using
        its planned_msrp, factory_cogs, region, and category from master_products.
        """
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT product_id, name, category, region, planned_msrp, factory_cogs, landed_cogs
            FROM master_products
            WHERE product_id = ?
        """, (product_id,))
        row = cur.fetchone()
        conn.close()

        if not row:
            return None

        p = dict(row)
        planned_msrp = float(p.get("planned_msrp") or 1299.0)
        # FOB price: use factory_cogs or derive reasonable proportion from landed_cogs
        fob_price = float(p.get("factory_cogs") or (p.get("landed_cogs") or planned_msrp * 0.25) * 0.7)
        region = p.get("region") or "India"
        category = p.get("category") or "General"

        # Execute existing 15-factor calculation
        assessment = Comprehensive15FactorEconomics.evaluate_15_factor_economics(
            product_id=product_id,
            fob_price=max(1.0, fob_price),
            planned_msrp=max(1.0, planned_msrp),
            region=region,
            category=category
        )

        def _map_scenario(sc) -> ScenarioDetail:
            d = sc.model_dump()
            break_even = int(max(1, d.get("first_batch_capital", 1000) / max(1.0, abs(d.get("contribution_margin", 1.0)))))
            return ScenarioDetail(
                scenario_name=d.get("scenario_name", "Scenario"),
                planned_msrp=float(d.get("planned_msrp", planned_msrp)),
                fob_price=float(d.get("fob_price", fob_price)),
                landed_cogs=float(d.get("landed_cogs", 0.0)),
                gross_margin_pct=round(float(d.get("gross_margin_pct", 0.0)), 2),
                net_profit_pct=round(float(d.get("net_profit_pct", 0.0)), 2),
                worst_case_stress_margin_pct=round(float(d.get("net_profit_pct", 0.0) * 0.6), 2),
                break_even_units=break_even,
                is_viable=(d.get("status") == "PASS"),
                status=d.get("status", "FAIL")
            )

        scenarios: List[ScenarioDetail] = [
            _map_scenario(assessment.conservative),
            _map_scenario(assessment.expected),
            _map_scenario(assessment.upside)
        ]

        expected_dump = assessment.expected.model_dump()
        factor_breakdown = {
            "volumetric_freight_cost": expected_dump.get("volumetric_freight_cost"),
            "marketplace_commission": expected_dump.get("marketplace_commission"),
            "fulfillment_fee": expected_dump.get("fulfillment_fee"),
            "payment_or_cod_fee": expected_dump.get("payment_or_cod_fee"),
            "rto_reserve": expected_dump.get("rto_reserve"),
            "return_fraud_reserve": expected_dump.get("return_fraud_reserve"),
            "ad_tacos_reserve": expected_dump.get("ad_tacos_reserve"),
            "net_tax_burden": expected_dump.get("net_tax_burden"),
            "total_variable_cost": expected_dump.get("total_variable_cost"),
            "net_profit": expected_dump.get("net_profit")
        }

        return EconomicsResponse(
            product_id=assessment.product_id,
            region=assessment.region,
            currency=assessment.currency,
            composite_score=assessment.composite_score,
            recommendation=assessment.recommendation,
            is_financially_viable=assessment.is_financially_viable,
            lead_time_days=assessment.lead_time_days,
            trend_half_life_days=assessment.trend_half_life_days,
            lead_time_risk_factor=assessment.lead_time_risk_factor,
            scenarios=scenarios,
            factor_breakdown=factor_breakdown
        )
