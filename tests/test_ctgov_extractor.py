"""Tests for pipeline/ctgov_extractor.py — AACT CT.gov integration."""

import pytest


# ---------------------------------------------------------------------------
# match_aact_effect
# ---------------------------------------------------------------------------

def test_match_aact_effect_hr():
    """AACT HR matches Cochrane value within 5%."""
    from pipeline.ctgov_extractor import match_aact_effect

    effects = [
        {
            "point_estimate": 0.74,
            "ci_lower": 0.65,
            "ci_upper": 0.85,
            "param_type": "Hazard Ratio (HR)",
            "method": "Cox",
        }
    ]
    result = match_aact_effect(effects, cochrane_mean=0.75, is_ratio=True)
    assert result is not None
    assert result["matched"] is True
    assert result["match_tier"].startswith("aact_")
    assert result["source"] == "aact"


def test_match_aact_effect_no_match():
    """AACT effect too far from Cochrane -> None."""
    from pipeline.ctgov_extractor import match_aact_effect

    effects = [
        {
            "point_estimate": 1.50,
            "ci_lower": 1.1,
            "ci_upper": 2.0,
            "param_type": "OR",
            "method": "logistic",
        }
    ]
    result = match_aact_effect(effects, cochrane_mean=0.75, is_ratio=True)
    assert result is None


def test_match_aact_effect_best_of_multiple():
    """When multiple AACT effects exist, pick closest match."""
    from pipeline.ctgov_extractor import match_aact_effect

    effects = [
        {
            "point_estimate": 0.90,
            "ci_lower": 0.7,
            "ci_upper": 1.1,
            "param_type": "HR",
            "method": "Cox",
        },
        {
            "point_estimate": 0.76,
            "ci_lower": 0.6,
            "ci_upper": 0.9,
            "param_type": "HR",
            "method": "Cox",
        },
    ]
    result = match_aact_effect(effects, cochrane_mean=0.75, is_ratio=True)
    assert result is not None
    assert abs(result["point_estimate"] - 0.76) < 0.01


def test_match_aact_effect_empty_list():
    """Empty effects list returns None."""
    from pipeline.ctgov_extractor import match_aact_effect

    result = match_aact_effect([], cochrane_mean=0.75, is_ratio=True)
    assert result is None


def test_match_aact_effect_none_point_estimate():
    """Effects with None point_estimate are skipped."""
    from pipeline.ctgov_extractor import match_aact_effect

    effects = [
        {
            "point_estimate": None,
            "ci_lower": 0.6,
            "ci_upper": 0.9,
            "param_type": "HR",
            "method": "Cox",
        }
    ]
    result = match_aact_effect(effects, cochrane_mean=0.75, is_ratio=True)
    assert result is None


def test_match_aact_effect_md():
    """Mean difference match works (non-ratio)."""
    from pipeline.ctgov_extractor import match_aact_effect

    effects = [
        {
            "point_estimate": -2.45,
            "ci_lower": -4.0,
            "ci_upper": -0.9,
            "param_type": "Mean Difference (Final Values)",
            "method": "ANCOVA",
        }
    ]
    result = match_aact_effect(effects, cochrane_mean=-2.50, is_ratio=False)
    assert result is not None
    assert result["matched"] is True
    assert result["match_tier"] == "aact_5pct"


def test_match_aact_effect_tier_10pct():
    """Effect within 10% log-scale but outside 5% gets aact_10pct tier.

    P1-4: Log-scale comparison. |log(0.737)-log(0.75)|/|log(0.75)| ≈ 6.1%.
    """
    from pipeline.ctgov_extractor import match_aact_effect

    effects = [
        {
            "point_estimate": 0.737,
            "ci_lower": 0.6,
            "ci_upper": 0.9,
            "param_type": "Hazard Ratio (HR)",
            "method": "Cox",
        }
    ]
    result = match_aact_effect(effects, cochrane_mean=0.75, is_ratio=True)
    assert result is not None
    assert result["match_tier"] == "aact_10pct"


# ---------------------------------------------------------------------------
# PARAM_TYPE_MAP
# ---------------------------------------------------------------------------

def test_param_type_map():
    """PARAM_TYPE_MAP covers key effect types."""
    from pipeline.ctgov_extractor import PARAM_TYPE_MAP

    assert PARAM_TYPE_MAP["Hazard Ratio (HR)"] == "HR"
    assert PARAM_TYPE_MAP["Odds Ratio (OR)"] == "OR"
    assert PARAM_TYPE_MAP["Risk Ratio (RR)"] == "RR"
    assert PARAM_TYPE_MAP["Mean Difference (Final Values)"] == "MD"
    assert PARAM_TYPE_MAP["LS Mean Difference"] == "MD"


# ---------------------------------------------------------------------------
# Empty input handling
# ---------------------------------------------------------------------------

def test_batch_pmid_to_nct_empty():
    """batch_pmid_to_nct with empty list returns empty dict."""
    from pipeline.ctgov_extractor import batch_pmid_to_nct

    result = batch_pmid_to_nct(None, [])
    assert result == {}


def test_fetch_precomputed_effects_empty():
    """fetch_precomputed_effects with empty list returns empty dict."""
    from pipeline.ctgov_extractor import fetch_precomputed_effects

    result = fetch_precomputed_effects(None, [])
    assert result == {}


def test_fetch_raw_outcomes_empty():
    """fetch_raw_outcomes with empty list returns empty dict."""
    from pipeline.ctgov_extractor import fetch_raw_outcomes

    result = fetch_raw_outcomes(None, [])
    assert result == {}


# ---------------------------------------------------------------------------
# build_aact_lookup callable
# ---------------------------------------------------------------------------

def test_build_aact_lookup_exists():
    """build_aact_lookup function exists and is callable."""
    from pipeline.ctgov_extractor import build_aact_lookup

    assert callable(build_aact_lookup)


# ---------------------------------------------------------------------------
# get_connection
# ---------------------------------------------------------------------------

def test_get_connection_exists():
    """get_connection function exists and is callable."""
    from pipeline.ctgov_extractor import get_connection

    assert callable(get_connection)
