"""Tests for pipeline.effect_extractor — classify_match strict tier logic.

P1-4: Ratio measures now use log-scale comparison. Test values updated.
"""

import math
import pytest


# ---------------------------------------------------------------------------
# classify_match — direct extracted vs Cochrane reference
# ---------------------------------------------------------------------------

def test_match_strict_5pct():
    """0.74 vs 0.75 on ratio scale — ~4.7% log-scale diff → direct_5pct."""
    from pipeline.effect_extractor import classify_match
    result = classify_match(extracted=0.74, cochrane_mean=0.75, is_ratio=True)
    assert result["matched"] is True
    assert result["match_tier"] == "direct_5pct"


def test_match_strict_10pct():
    """0.72 vs 0.75 on ratio scale — ~9.2% log-scale diff → direct_10pct.

    Note: 0.68 vs 0.75 was 9.33% on natural scale but 34% on log scale.
    Use 0.72 vs 0.75 instead: |log(0.72)-log(0.75)|/|log(0.75)| ≈ 0.041/0.288 ≈ 14.2%
    Actually need a tighter pair. Use 0.70 vs 0.75:
    |log(0.70)-log(0.75)|/|log(0.75)| = |-.3567-(-.2877)|/.2877 = .069/.288 = 24% — too much.
    Use natural-scale diff scenario: 0.73 vs 0.75 = 2.7% natural, 9.5% log — still too much.
    Actually: 5.1-10% on log scale. Example: 0.74 is 4.7%, so slightly worse:
    Try 0.737: |log(.737)-log(.75)|/|log(.75)| = |-.305-(-.288)|/.288 = .017/.288 = 6.1% → 10pct ✓
    """
    from pipeline.effect_extractor import classify_match
    result = classify_match(extracted=0.737, cochrane_mean=0.75, is_ratio=True)
    assert result["matched"] is True
    assert result["match_tier"] == "direct_10pct"


def test_no_match():
    """0.50 vs 0.75 on ratio scale — large diff → no match."""
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
    """0.74 vs 0.75 on ratio scale — 4.7% log-scale diff → matched.

    P1-4: Ratio measures use log-scale. Natural-scale 2.5% diff (0.82 vs 0.80)
    becomes ~11% log-scale and fails. Use tighter pair instead.
    """
    from pipeline.effect_extractor import classify_match
    result = classify_match(extracted=0.74, cochrane_mean=0.75, is_ratio=True)
    assert result["matched"] is True


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
    """Return dict includes log-scale pct_difference for ratio measures."""
    from pipeline.effect_extractor import classify_match
    result = classify_match(extracted=0.74, cochrane_mean=0.75, is_ratio=True)
    assert result["pct_difference"] is not None
    # Log-scale: |log(0.74) - log(0.75)| / |log(0.75)|
    expected = abs(math.log(0.74) - math.log(0.75)) / abs(math.log(0.75))
    assert abs(result["pct_difference"] - expected) < 1e-9


def test_returns_pct_difference_natural():
    """Return dict includes natural-scale pct_difference for diff measures."""
    from pipeline.effect_extractor import classify_match
    result = classify_match(extracted=-2.4, cochrane_mean=-2.5, is_ratio=False)
    assert result["pct_difference"] is not None
    expected = abs(-2.4 - (-2.5)) / abs(-2.5)
    assert abs(result["pct_difference"] - expected) < 1e-9


def test_no_extracted_no_computed_returns_unmatched():
    """Both extracted and computed_effect are None — cannot match."""
    from pipeline.effect_extractor import classify_match
    result = classify_match(extracted=None, cochrane_mean=0.75, is_ratio=True)
    assert result["matched"] is False
    assert result["match_tier"] is None
    assert result["pct_difference"] is None


def test_computed_10pct():
    """extracted=None, computed=0.737 vs cochrane=0.75 → ~6% log-scale → computed_10pct."""
    from pipeline.effect_extractor import classify_match
    result = classify_match(extracted=None, cochrane_mean=0.75, is_ratio=True, computed_effect=0.737)
    assert result["matched"] is True
    assert result["match_tier"] == "computed_10pct"


def test_extracted_preferred_over_computed():
    """When extracted is provided and matches, computed_effect is ignored for tier."""
    from pipeline.effect_extractor import classify_match
    result = classify_match(extracted=0.74, cochrane_mean=0.75, is_ratio=True, computed_effect=0.50)
    assert result["matched"] is True
    assert result["match_tier"] == "direct_5pct"


def test_log_scale_symmetry():
    """P1-4: Log-scale comparison is symmetric — OR=0.5 and OR=2.0 give same diff vs 1.0."""
    from pipeline.effect_extractor import _rel_diff
    # Natural-scale: |0.5 - 1.0|/1.0 = 50%, |2.0 - 1.0|/1.0 = 100% — asymmetric
    # Log-scale: |log(0.5)|/|log(1.0)| — undefined (log(1)=0)
    # But for non-null: |log(0.5) - log(0.6)| / |log(0.6)| vs |log(2.0) - log(1.67)| / |log(1.67)|
    diff_low = _rel_diff(0.5, 0.6, log_scale=True)
    diff_high = _rel_diff(2.0, 1.0 / 0.6, log_scale=True)  # reciprocal
    assert abs(diff_low - diff_high) < 1e-9, "Log-scale diff should be symmetric"
