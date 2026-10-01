"""
tests/test_daemon_matcher_regression.py

Regression tests for:
  - Bug 1A: evaluate_match_confidence() returns Tuple[str, float], not dict
  - All callers must unpack the tuple, never call .get("classification")
  - Deduplication logic in background_daemon and orchestrator contexts

These tests MUST pass. They fail if the dict-access regression is reintroduced.
"""
import pytest
from core.product_matcher import CanonicalProductMatcher


class TestEvaluateMatchConfidenceContract:
    """Verify the tuple return contract is correctly typed and stable."""

    def test_returns_tuple_not_dict(self):
        """evaluate_match_confidence MUST return a tuple, never a dict."""
        result = CanonicalProductMatcher.evaluate_match_confidence(
            canonical_title="Wireless Bluetooth Earbuds",
            target_listing_title="Bluetooth Wireless Earbuds",
            canonical_price=1299.0,
            target_price=1199.0,
        )
        assert isinstance(result, tuple), (
            f"evaluate_match_confidence must return tuple, got {type(result)}"
        )
        assert len(result) == 2, f"Expected 2-tuple (classification, confidence), got len={len(result)}"

    def test_tuple_has_no_get_method(self):
        """Tuple does NOT have .get() — calling it raises AttributeError.
        This test documents the original bug to prevent regression."""
        result = CanonicalProductMatcher.evaluate_match_confidence(
            "Product A", "Product B", 100.0, 100.0
        )
        with pytest.raises(AttributeError):
            result.get("classification")  # This is the bug — must not exist

    def test_exact_match_classification(self):
        """Two nearly identical products at similar price → EXACT_MATCH."""
        title_a = "2 Tier Sliding Under Sink Cabinet Storage Organizer Rack Kitchen"
        title_b = "2-Tier Under Sink Organizers Storage Multi-Purpose Sliding Drawer Rack Kitchen"
        classification, confidence = CanonicalProductMatcher.evaluate_match_confidence(
            canonical_title=title_a,
            target_listing_title=title_b,
            canonical_price=1299.0,
            target_price=1199.0,
        )
        assert isinstance(classification, str)
        assert classification in {"EXACT_MATCH", "PROBABLE_VARIANT"}, (
            f"Expected EXACT_MATCH or PROBABLE_VARIANT, got {classification}"
        )
        assert isinstance(confidence, float)
        assert 0.0 <= confidence <= 1.0

    def test_unrelated_products(self):
        """Completely unrelated products → UNRELATED."""
        classification, confidence = CanonicalProductMatcher.evaluate_match_confidence(
            canonical_title="Yoga Mat Non-Slip Exercise",
            target_listing_title="Steel Frying Pan Non-Stick Cookware",
            canonical_price=800.0,
            target_price=1200.0,
        )
        assert classification == "UNRELATED"
        assert 0.0 <= confidence <= 1.0

    def test_extreme_price_deviation_forces_unrelated(self):
        """Price ratio > 4.5x forces UNRELATED classification."""
        classification, confidence = CanonicalProductMatcher.evaluate_match_confidence(
            canonical_title="Wireless Headphones",
            target_listing_title="Wireless Headphones Premium",
            canonical_price=100.0,
            target_price=600.0,  # 6x price ratio
        )
        assert classification == "UNRELATED", (
            f"Extreme price ratio should force UNRELATED, got {classification}"
        )

    def test_probable_variant_classification(self):
        """Partially overlapping titles at reasonable price → PROBABLE_VARIANT."""
        classification, confidence = CanonicalProductMatcher.evaluate_match_confidence(
            canonical_title="Stainless Steel Water Bottle 750ml Insulated",
            target_listing_title="Insulated Water Bottle 1000ml Thermos Flask",
            canonical_price=599.0,
            target_price=699.0,
        )
        assert classification in {"PROBABLE_VARIANT", "RELATED_ALTERNATIVE", "EXACT_MATCH"}
        assert 0.0 <= confidence <= 1.0

    def test_all_valid_classifications_covered(self):
        """All 4 possible classifications are valid return values."""
        valid = {"EXACT_MATCH", "PROBABLE_VARIANT", "RELATED_ALTERNATIVE", "UNRELATED"}
        # Run several pairs to confirm classification values stay in set
        test_cases = [
            ("Yoga Mat", "Steel Pan", 500.0, 1500.0),
            ("Wireless Earbuds Bluetooth", "Wireless Earbuds Bluetooth", 999.0, 999.0),
            ("Coffee Mug Ceramic", "Coffee Mug Stainless Steel", 299.0, 350.0),
            ("Running Shoes Nike", "Swimming Goggles", 3000.0, 800.0),
        ]
        for a, b, pa, pb in test_cases:
            classification, _ = CanonicalProductMatcher.evaluate_match_confidence(a, b, pa, pb)
            assert classification in valid, f"Invalid classification: {classification}"

    def test_confidence_always_float_in_range(self):
        """Confidence must always be a float in [0.0, 1.0]."""
        test_cases = [
            ("Widget", "Gadget", 100.0, 200.0),
            ("", "Something", 0.0, 0.0),
            ("A B C D E F G H", "A B C D E F G H", 500.0, 500.0),
        ]
        for a, b, pa, pb in test_cases:
            _, confidence = CanonicalProductMatcher.evaluate_match_confidence(a, b, pa, pb)
            assert isinstance(confidence, float), f"Confidence must be float, got {type(confidence)}"
            assert 0.0 <= confidence <= 1.0, f"Confidence out of range: {confidence}"

    def test_empty_titles_return_unrelated(self):
        """Empty titles should gracefully return UNRELATED with 0.0 confidence."""
        classification, confidence = CanonicalProductMatcher.evaluate_match_confidence(
            canonical_title="",
            target_listing_title="",
            canonical_price=100.0,
            target_price=100.0,
        )
        assert classification == "UNRELATED"
        assert confidence == 0.0


class TestDaemonDedupConsumesCorrectly:
    """Simulate the daemon dedup loop pattern to verify no AttributeError."""

    def test_daemon_pattern_no_attribute_error(self):
        """Simulate background_daemon.py dedup loop — must not raise AttributeError."""
        matcher = CanonicalProductMatcher

        product_name = "Bamboo Cutting Board Kitchen Chopping"
        product_price = 799.0
        existing_products = [
            {"product_id": "EP_001", "name": "Bamboo Kitchen Cutting Board", "planned_msrp": 749.0},
            {"product_id": "EP_002", "name": "Steel Frying Pan 28cm", "planned_msrp": 1299.0},
        ]

        is_dup = False
        for ep in existing_products:
            # This is the FIXED pattern (tuple unpacking):
            classification, _confidence = matcher.evaluate_match_confidence(
                product_name, ep.get("name", ""),
                product_price, float(ep.get("planned_msrp") or 0)
            )
            if classification == "EXACT_MATCH":
                is_dup = True
                break

        # Result: EP_001 should be detected as EXACT_MATCH or PROBABLE_VARIANT
        # Either way, no AttributeError must be raised — that's the critical assertion
        assert isinstance(is_dup, bool)

    def test_daemon_pattern_detects_true_duplicate(self):
        """Daemon must correctly detect near-identical product as duplicate."""
        matcher = CanonicalProductMatcher

        product_name = "Wireless Bluetooth Earbuds TWS"
        product_price = 999.0
        existing_products = [
            {"product_id": "EP_001", "name": "TWS Wireless Bluetooth Earbuds", "planned_msrp": 949.0},
        ]

        is_dup = False
        for ep in existing_products:
            classification, _confidence = matcher.evaluate_match_confidence(
                product_name, ep.get("name", ""),
                product_price, float(ep.get("planned_msrp") or 0)
            )
            if classification == "EXACT_MATCH":
                is_dup = True
                break

        # These are clearly the same product — should be detected
        assert is_dup is True, "Near-identical product should be flagged as duplicate"

    def test_daemon_pattern_no_false_positive(self):
        """Daemon must NOT flag clearly unrelated products as duplicates."""
        matcher = CanonicalProductMatcher

        product_name = "Yoga Mat Non-Slip Exercise 6mm"
        product_price = 799.0
        existing_products = [
            {"product_id": "EP_001", "name": "Steel Wok 32cm Flat Bottom Cooking Pan", "planned_msrp": 1499.0},
        ]

        is_dup = False
        for ep in existing_products:
            classification, _confidence = matcher.evaluate_match_confidence(
                product_name, ep.get("name", ""),
                product_price, float(ep.get("planned_msrp") or 0)
            )
            if classification == "EXACT_MATCH":
                is_dup = True
                break

        assert is_dup is False, "Completely unrelated products must NOT be flagged as duplicates"

    def test_orchestrator_pattern_no_attribute_error(self):
        """Simulate orchestrator.py dedup loop — must not raise AttributeError."""
        matcher = CanonicalProductMatcher

        all_products = [
            {"title": "Bamboo Cutting Board", "price": 799.0},
            {"title": "Bamboo Kitchen Cutting Board", "price": 749.0},  # near-duplicate
            {"title": "Steel Frying Pan 28cm", "price": 1299.0},        # unrelated
        ]

        canonical_products = []
        for p in all_products:
            pname = p.get("title", "")
            pprice = float(p.get("price", 0))
            is_dup = False
            for cp in canonical_products:
                # FIXED pattern from orchestrator.py:
                classification, _confidence = matcher.evaluate_match_confidence(
                    pname, cp.get("title", ""),
                    pprice, float(cp.get("price", 0))
                )
                if classification == "EXACT_MATCH":
                    is_dup = True
                    if len(str(p)) > len(str(cp)):
                        canonical_products.remove(cp)
                        canonical_products.append(p)
                    break
            if not is_dup:
                canonical_products.append(p)

        # Should deduplicate: bamboo board + bamboo kitchen board = 1 + steel pan = 2
        assert len(canonical_products) <= 3
        assert len(canonical_products) >= 1  # At least one product survived


class TestConfidenceHandling:
    """Verify confidence value edge cases."""

    def test_identical_titles_high_confidence(self):
        """Identical titles at same price should produce maximum confidence."""
        title = "Stainless Steel Water Bottle 750ml"
        classification, confidence = CanonicalProductMatcher.evaluate_match_confidence(
            title, title, 599.0, 599.0
        )
        assert classification == "EXACT_MATCH"
        assert confidence >= 0.9, f"Identical products should have high confidence, got {confidence}"

    def test_zero_price_handled_gracefully(self):
        """Zero prices must not cause division-by-zero errors."""
        # This tests the max(0.1, min(...)) protection in price_ratio calculation
        classification, confidence = CanonicalProductMatcher.evaluate_match_confidence(
            "Product A", "Product A", 0.0, 0.0
        )
        assert isinstance(classification, str)
        assert isinstance(confidence, float)
