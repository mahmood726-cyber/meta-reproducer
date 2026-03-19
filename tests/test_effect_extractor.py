"""Tests for pipeline.effect_extractor — classify_match strict tier logic."""

import math
import pytest


# ---------------------------------------------------------------------------
# classify_match — direct extracted vs Cochrane reference
# ---------------------------------------------------------------------------

def test_match_strict_5pct():
    """0.74 vs 0.75 on ratio scale — 1.33% diff → direct_5pct."""
    from pipeline.effect_extractor import classify_match
    result = classify_match(extracted=0.74, cochrane_mean=0.75, is_ratio=True)
    assert result["matched"] is True
    assert result["match_tier"] == "direct_5pct"


def test_match_strict_10pct():
    """0.68 vs 0.75 on ratio scale — 9.33% diff → direct_10pct."""
    from pipeline.effect_extractor import classify_match
    result = classify_match(extracted=0.68, cochrane_mean=0.75, is_ratio=True)
    assert result["matched"] is True
    assert result["match_tier"] == "direct_10pct"


def test_no_match():
    """0.50 vs 0.75 on ratio scale — 33.3% diff → no match."""
    from pipeline.effect_extractor import classify_match
    result = classify_match(extracted=0.50, cochrane_mean=0.75, is_ratio=True)
    assert result["matched"] is False


def test_computed_match():
    """extracted=None, computed=0.74 vs cochrane=0.75 → computed_5pct."""
    from pipeline.effect_extractor import classify_match
    result = classify_match(extracted=None, cochrane_mean=0.75, is_ratio=True, computed_effect=0.74)
    assert result["matched"] is True
    assert result["match_tier"] == "computed_5pct"


def test_log_scale_comparison():
    """0.82 vs 0.80 on ratio scale — 2.5% diff on natural scale → matched."""
    from pipeline.effect_extractor import classify_match
    result = classify_match(extracted=0.82, cochrane_mean=0.80, is_ratio=True)
    assert result["matched"] is True  # 2.5% diff on natural scale


def test_diff_scale_comparison():
    """-2.4 vs -2.5 on difference scale — 4% diff → direct_5pct."""
    from pipeline.effect_extractor import classify_match
    result = classify_match(extracted=-2.4, cochrane_mean=-2.5, is_ratio=False)
    assert result["matched"] is True
    assert result["match_tier"] == "direct_5pct"


# ---------------------------------------------------------------------------
# Additional edge cases
# ---------------------------------------------------------------------------

def test_returns_pct_difference():
    """Return dict always includes pct_difference when extracted is provided."""
    from pipeline.effect_extractor import classify_match
    result = classify_match(extracted=0.74, cochrane_mean=0.75, is_ratio=True)
    assert result["pct_difference"] is not None
    assert abs(result["pct_difference"] - abs(0.74 - 0.75) / abs(0.75)) < 1e-9


def test_no_extracted_no_computed_returns_unmatched():
    """Both extracted and computed_effect are None — cannot match."""
    from pipeline.effect_extractor import classify_match
    result = classify_match(extracted=None, cochrane_mean=0.75, is_ratio=True)
    assert result["matched"] is False
    assert result["match_tier"] is None
    assert result["pct_difference"] is None


def test_computed_10pct():
    """extracted=None, computed=0.68 vs cochrane=0.75 → 9.33% diff → computed_10pct."""
    from pipeline.effect_extractor import classify_match
    result = classify_match(extracted=None, cochrane_mean=0.75, is_ratio=True, computed_effect=0.68)
    assert result["matched"] is True
    assert result["match_tier"] == "computed_10pct"


def test_extracted_preferred_over_computed():
    """When extracted is provided and matches, computed_effect is ignored for tier."""
    from pipeline.effect_extractor import classify_match
    result = classify_match(extracted=0.74, cochrane_mean=0.75, is_ratio=True, computed_effect=0.50)
    assert result["matched"] is True
    assert result["match_tier"] == "direct_5pct"
