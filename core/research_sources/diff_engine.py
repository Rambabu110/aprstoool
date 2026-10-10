"""
core/research_sources/diff_engine.py — Observation Change Detection & Diff Engine.

Calculates state differentials between sequential observations (e.g. Observation[t] vs Observation[t-1]),
evaluates materiality thresholds, and identifies trigger events that necessitate intelligence recalculation.
Zero synthetic values; strictly compares verified observed measurements.
"""

from enum import Enum
from typing import Dict, Any, List, Optional, Union
import datetime
import math
from pydantic import BaseModel, Field

from core.research_sources.observation import CanonicalObservation


# ─────────────────────────────────────────────────────────────────────────────
# 1. CHANGE CLASSIFICATION ENUM
# ─────────────────────────────────────────────────────────────────────────────
class ChangeType(str, Enum):
    """Explicit taxonomy of observable market state changes."""
    PRICE_INCREASE = "PRICE_INCREASE"
    PRICE_DECREASE = "PRICE_DECREASE"
    RATING_CHANGE = "RATING_CHANGE"
    REVIEW_COUNT_CHANGE = "REVIEW_COUNT_CHANGE"
    STOCKOUT = "STOCKOUT"
    RESTOCK = "RESTOCK"
    BSR_CHANGE = "BSR_CHANGE"
    TREND_ACCELERATION = "TREND_ACCELERATION"
    TREND_DECELERATION = "TREND_DECELERATION"
    NO_MATERIAL_CHANGE = "NO_MATERIAL_CHANGE"


# ─────────────────────────────────────────────────────────────────────────────
# 2. DOCUMENTED MATERIALITY THRESHOLDS
# ─────────────────────────────────────────────────────────────────────────────
class MaterialityThresholds(BaseModel):
    """
    Documented significance thresholds for filtering market noise.
    Changes below these boundaries are classified as non-material.
    """
    price_pct_threshold: float = Field(
        default=2.0,
        description="Minimum absolute percentage change in price to trigger materiality (e.g. 2.0%)"
    )
    rating_delta_threshold: float = Field(
        default=0.1,
        description="Minimum star rating change to trigger materiality (e.g. 0.1 stars out of 5.0)"
    )
    review_count_delta_threshold: int = Field(
        default=5,
        description="Minimum net reviews added or removed to trigger materiality (e.g. 5 reviews)"
    )
    trend_momentum_threshold: float = Field(
        default=5.0,
        description="Minimum change in 0-100 search index or momentum to trigger materiality (e.g. 5.0 points)"
    )
    bsr_pct_threshold: float = Field(
        default=10.0,
        description="Minimum percentage shift in Best Sellers Rank to trigger materiality (e.g. 10.0%)"
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. STRUCTURED DIFF REPORT MODELS
# ─────────────────────────────────────────────────────────────────────────────
class FieldDiff(BaseModel):
    """Individual field comparison with numerical deltas and materiality flag."""
    field_name: str
    old_value: Any
    new_value: Any
    absolute_delta: Optional[float] = None
    percentage_delta: Optional[float] = None
    is_material: bool = False
    change_type: ChangeType = ChangeType.NO_MATERIAL_CHANGE
    explanation: str = ""


class ObservationDiffReport(BaseModel):
    """
    Comprehensive differential report between two observation points.
    Indicates whether downstream intelligence recalculation is required.
    """
    product_id: Optional[str] = None
    external_id: Optional[str] = None
    source_id: str
    previous_observed_at: Optional[str] = None
    current_observed_at: str
    diffs: List[FieldDiff] = Field(default_factory=list)
    material_changes: List[ChangeType] = Field(default_factory=list)
    requires_intelligence_refresh: bool = False
    summary: str = "No material change detected."


# ─────────────────────────────────────────────────────────────────────────────
# 4. OBSERVATION DIFF ENGINE IMPLEMENTATION
# ─────────────────────────────────────────────────────────────────────────────
class ObservationDiffEngine:
    """
    Stateless comparison engine evaluating sequential market snapshots.
    Supports comparing canonical observations or dictionary snapshots.
    """

    def __init__(self, thresholds: Optional[MaterialityThresholds] = None):
        self.thresholds = thresholds or MaterialityThresholds()

    def compare_observations(
        self,
        prev: CanonicalObservation,
        curr: CanonicalObservation
    ) -> ObservationDiffReport:
        """
        Compares two CanonicalObservation instances of the same signal type.
        """
        diffs: List[FieldDiff] = []
        material_changes: List[ChangeType] = []

        # Handle numeric values (e.g. Price, Rating, Trend Index)
        if isinstance(prev.value, (int, float)) and isinstance(curr.value, (int, float)):
            old_val = float(prev.value)
            new_val = float(curr.value)
            abs_delta = round(new_val - old_val, 4)
            pct_delta = round((abs_delta / old_val * 100.0), 2) if old_val != 0 else 0.0

            field_name = curr.signal_type.value.lower()
            change_type = ChangeType.NO_MATERIAL_CHANGE
            is_material = False
            explanation = ""

            # 1. Price comparison
            if curr.signal_type.value == "PRICE":
                if abs(pct_delta) >= self.thresholds.price_pct_threshold:
                    is_material = True
                    change_type = ChangeType.PRICE_INCREASE if new_val > old_val else ChangeType.PRICE_DECREASE
                    explanation = f"Price moved from {old_val} to {new_val} ({pct_delta:+.1f}%)"
                else:
                    explanation = f"Minor price fluctuation from {old_val} to {new_val} ({pct_delta:+.1f}%)"

            # 2. Trend index / demand comparison
            elif curr.signal_type.value in ("DEMAND", "TREND"):
                if abs(abs_delta) >= self.thresholds.trend_momentum_threshold:
                    is_material = True
                    change_type = ChangeType.TREND_ACCELERATION if new_val > old_val else ChangeType.TREND_DECELERATION
                    explanation = f"Search demand shifted from {old_val} to {new_val} index points ({abs_delta:+.1f})"
                else:
                    explanation = f"Stable demand: {old_val} -> {new_val}"

            # 3. Competition / review count
            elif curr.signal_type.value == "COMPETITION" and curr.unit == "review_count":
                if abs(abs_delta) >= self.thresholds.review_count_delta_threshold:
                    is_material = True
                    change_type = ChangeType.REVIEW_COUNT_CHANGE
                    explanation = f"Review volume changed by {abs_delta:+.0f} reviews ({old_val} -> {new_val})"
                else:
                    explanation = f"Sub-threshold review shift: {abs_delta:+.0f}"

            else:
                if abs_delta != 0:
                    explanation = f"Value adjusted from {old_val} to {new_val}"

            if is_material:
                material_changes.append(change_type)

            diffs.append(FieldDiff(
                field_name=field_name,
                old_value=old_val,
                new_value=new_val,
                absolute_delta=abs_delta,
                percentage_delta=pct_delta,
                is_material=is_material,
                change_type=change_type,
                explanation=explanation
            ))

        # Handle structured payload comparisons (e.g. Scraped Listing dictionaries)
        elif isinstance(prev.value, dict) and isinstance(curr.value, dict):
            return self.compare_listing_snapshots(
                prev=prev.value,
                curr=curr.value,
                source_id=curr.source_id,
                product_id=curr.product_id,
                external_id=curr.external_id,
                prev_time=prev.observed_at,
                curr_time=curr.observed_at
            )

        elif prev.value is not None and curr.value is None:
            # Field missing in new observation: preserve NULL, do NOT convert to zero, do NOT trigger false refresh
            field_name = curr.signal_type.value.lower() if hasattr(curr.signal_type, "value") else "value"
            diffs.append(FieldDiff(
                field_name=field_name,
                old_value=prev.value,
                new_value=None,
                is_material=False,
                change_type=ChangeType.NO_MATERIAL_CHANGE,
                explanation="Field missing in new observation; preserved as NULL without false refresh."
            ))

        elif prev.value is None and curr.value is not None:
            # Field newly observed from previously unobserved state
            field_name = curr.signal_type.value.lower() if hasattr(curr.signal_type, "value") else "value"
            diffs.append(FieldDiff(
                field_name=field_name,
                old_value=None,
                new_value=curr.value,
                is_material=False,
                change_type=ChangeType.NO_MATERIAL_CHANGE,
                explanation="Field newly observed from previously unobserved state."
            ))

        requires_refresh = len(material_changes) > 0
        summary = (
            f"Detected {len(material_changes)} material change(s): {', '.join(c.value for c in material_changes)}"
            if requires_refresh else "No material changes detected."
        )

        return ObservationDiffReport(
            product_id=curr.product_id,
            external_id=curr.external_id,
            source_id=curr.source_id,
            previous_observed_at=prev.observed_at,
            current_observed_at=curr.observed_at,
            diffs=diffs,
            material_changes=material_changes,
            requires_intelligence_refresh=requires_refresh,
            summary=summary
        )

    def compare_listing_snapshots(
        self,
        prev: Dict[str, Any],
        curr: Dict[str, Any],
        source_id: str = "amazon_scraper",
        product_id: Optional[str] = None,
        external_id: Optional[str] = None,
        prev_time: Optional[str] = None,
        curr_time: Optional[str] = None
    ) -> ObservationDiffReport:
        """
        Deep comparison of two marketplace listing snapshots (Price, Rating, Reviews, Stock, BSR).
        """
        diffs: List[FieldDiff] = []
        material_changes: List[ChangeType] = []

        now_utc = curr_time or datetime.datetime.now(datetime.timezone.utc).isoformat()
        old_time = prev_time or prev.get("scraped_at") or prev.get("observed_at")

        # ── 1. Price Comparison ──────────────────────────────────────────────
        p_old = prev.get("price")
        p_new = curr.get("price")
        if p_old is not None and p_new is not None:
            try:
                v_old = float(p_old)
                v_new = float(p_new)
                abs_delta = round(v_new - v_old, 2)
                pct_delta = round((abs_delta / v_old * 100.0), 2) if v_old > 0 else 0.0
                is_mat = abs(pct_delta) >= self.thresholds.price_pct_threshold
                ctype = (
                    (ChangeType.PRICE_INCREASE if v_new > v_old else ChangeType.PRICE_DECREASE)
                    if is_mat else ChangeType.NO_MATERIAL_CHANGE
                )
                if is_mat:
                    material_changes.append(ctype)
                diffs.append(FieldDiff(
                    field_name="price",
                    old_value=v_old,
                    new_value=v_new,
                    absolute_delta=abs_delta,
                    percentage_delta=pct_delta,
                    is_material=is_mat,
                    change_type=ctype,
                    explanation=f"Price: {v_old} -> {v_new} ({pct_delta:+.1f}%)"
                ))
            except (ValueError, TypeError):
                pass
        elif p_old is not None and p_new is None:
            diffs.append(FieldDiff(
                field_name="price",
                old_value=p_old,
                new_value=None,
                is_material=False,
                change_type=ChangeType.NO_MATERIAL_CHANGE,
                explanation="Price missing in new observation; preserved as NULL (not zero)."
            ))

        # ── 2. Rating Comparison ─────────────────────────────────────────────
        r_old = prev.get("rating")
        r_new = curr.get("rating")
        if r_old is not None and r_new is not None:
            try:
                v_old = float(r_old)
                v_new = float(r_new)
                abs_delta = round(v_new - v_old, 2)
                is_mat = abs(abs_delta) >= self.thresholds.rating_delta_threshold
                ctype = ChangeType.RATING_CHANGE if is_mat else ChangeType.NO_MATERIAL_CHANGE
                if is_mat:
                    material_changes.append(ctype)
                diffs.append(FieldDiff(
                    field_name="rating",
                    old_value=v_old,
                    new_value=v_new,
                    absolute_delta=abs_delta,
                    percentage_delta=None,
                    is_material=is_mat,
                    change_type=ctype,
                    explanation=f"Rating: {v_old} -> {v_new} (delta: {abs_delta:+.2f})"
                ))
            except (ValueError, TypeError):
                pass

        # ── 3. Review Count Comparison ───────────────────────────────────────
        rc_old = prev.get("review_count") or prev.get("reviews")
        rc_new = curr.get("review_count") or curr.get("reviews")
        if rc_old is not None and rc_new is not None:
            try:
                v_old = int(rc_old)
                v_new = int(rc_new)
                abs_delta = float(v_new - v_old)
                is_mat = abs(abs_delta) >= self.thresholds.review_count_delta_threshold
                ctype = ChangeType.REVIEW_COUNT_CHANGE if is_mat else ChangeType.NO_MATERIAL_CHANGE
                if is_mat:
                    material_changes.append(ctype)
                diffs.append(FieldDiff(
                    field_name="review_count",
                    old_value=v_old,
                    new_value=v_new,
                    absolute_delta=abs_delta,
                    percentage_delta=round(abs_delta / max(1, v_old) * 100.0, 1),
                    is_material=is_mat,
                    change_type=ctype,
                    explanation=f"Review count: {v_old} -> {v_new} (net: {abs_delta:+.0f})"
                ))
            except (ValueError, TypeError):
                pass

        # ── 4. Stock Availability Comparison ─────────────────────────────────
        avail_old = prev.get("in_stock") if "in_stock" in prev else prev.get("availability")
        avail_new = curr.get("in_stock") if "in_stock" in curr else curr.get("availability")
        if avail_old is not None and avail_new is not None:
            b_old = bool(avail_old)
            b_new = bool(avail_new)
            if b_old != b_new:
                ctype = ChangeType.STOCKOUT if (b_old and not b_new) else ChangeType.RESTOCK
                material_changes.append(ctype)
                diffs.append(FieldDiff(
                    field_name="availability",
                    old_value=b_old,
                    new_value=b_new,
                    absolute_delta=None,
                    percentage_delta=None,
                    is_material=True,
                    change_type=ctype,
                    explanation="Product went out of stock" if ctype == ChangeType.STOCKOUT else "Product restocked"
                ))

        # ── 5. BSR Comparison (ONLY IF PRESENT, NEVER INVENTED) ──────────────
        bsr_old = prev.get("bsr_rank") or prev.get("sales_rank")
        bsr_new = curr.get("bsr_rank") or curr.get("sales_rank")
        if bsr_old is not None and bsr_new is not None:
            try:
                v_old = int(bsr_old)
                v_new = int(bsr_new)
                abs_delta = float(v_new - v_old)
                pct_delta = round((abs_delta / v_old * 100.0), 2) if v_old > 0 else 0.0
                is_mat = abs(pct_delta) >= self.thresholds.bsr_pct_threshold
                ctype = ChangeType.BSR_CHANGE if is_mat else ChangeType.NO_MATERIAL_CHANGE
                if is_mat:
                    material_changes.append(ctype)
                diffs.append(FieldDiff(
                    field_name="bsr_rank",
                    old_value=v_old,
                    new_value=v_new,
                    absolute_delta=abs_delta,
                    percentage_delta=pct_delta,
                    is_material=is_mat,
                    change_type=ctype,
                    explanation=f"BSR Rank: #{v_old} -> #{v_new} ({pct_delta:+.1f}%)"
                ))
            except (ValueError, TypeError):
                pass

        requires_refresh = len(material_changes) > 0
        summary = (
            f"Listing Diff: {len(material_changes)} material event(s): {', '.join(c.value for c in material_changes)}"
            if requires_refresh else "Listing Diff: No material change."
        )

        return ObservationDiffReport(
            product_id=product_id,
            external_id=external_id or curr.get("asin"),
            source_id=source_id,
            previous_observed_at=old_time,
            current_observed_at=now_utc,
            diffs=diffs,
            material_changes=material_changes,
            requires_intelligence_refresh=requires_refresh,
            summary=summary
        )
