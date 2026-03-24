"""Tests for pipeline/ctgov_extractor.py — AACT CT.gov integration."""

import math
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


# ---------------------------------------------------------------------------
# compute_effects_from_raw — OR
# ---------------------------------------------------------------------------

def test_compute_or_basic():
    """Compute OR from a 2x2 table: a=10, N_exp=100, c=20, N_ctrl=100."""
    from pipeline.ctgov_extractor import compute_effects_from_raw

    raw = {
        "NCT001": {
            "out1": {
                "OG000": {"events": 10, "total_n": 100, "mean": None, "sd": None},
                "OG001": {"events": 20, "total_n": 100, "mean": None, "sd": None},
            }
        }
    }
    result = compute_effects_from_raw(raw)
    assert "NCT001" in result
    effects = result["NCT001"]
    or_effects = [e for e in effects if e["param_type"] == "Computed OR"]
    assert len(or_effects) == 1
    eff = or_effects[0]
    # Manual: OR = (10*80)/(90*20) = 800/1800 = 0.4444
    assert abs(eff["point_estimate"] - 0.4444) < 0.01
    assert eff["ci_lower"] < eff["point_estimate"]
    assert eff["ci_upper"] > eff["point_estimate"]
    assert eff["method"] == "raw_2x2"


def test_compute_or_continuity_correction():
    """When one cell is 0, continuity correction (0.5) is applied."""
    from pipeline.ctgov_extractor import compute_effects_from_raw

    raw = {
        "NCT002": {
            "out1": {
                "OG000": {"events": 0, "total_n": 50, "mean": None, "sd": None},
                "OG001": {"events": 10, "total_n": 50, "mean": None, "sd": None},
            }
        }
    }
    result = compute_effects_from_raw(raw)
    assert "NCT002" in result
    or_effects = [e for e in result["NCT002"] if e["param_type"] == "Computed OR"]
    assert len(or_effects) == 1
    # With cc=0.5: OR = (0.5 * 40.5) / (50.5 * 10.5)
    expected_or = (0.5 * 40.5) / (50.5 * 10.5)
    assert abs(or_effects[0]["point_estimate"] - expected_or) < 0.001


# ---------------------------------------------------------------------------
# compute_effects_from_raw — RR
# ---------------------------------------------------------------------------

def test_compute_rr_basic():
    """Compute RR from arm data."""
    from pipeline.ctgov_extractor import compute_effects_from_raw

    raw = {
        "NCT003": {
            "out1": {
                "OG000": {"events": 15, "total_n": 100, "mean": None, "sd": None},
                "OG001": {"events": 30, "total_n": 100, "mean": None, "sd": None},
            }
        }
    }
    result = compute_effects_from_raw(raw)
    rr_effects = [e for e in result["NCT003"] if e["param_type"] == "Computed RR"]
    assert len(rr_effects) == 1
    # RR = (15/100) / (30/100) = 0.5
    assert abs(rr_effects[0]["point_estimate"] - 0.5) < 0.01
    assert rr_effects[0]["ci_lower"] < 0.5
    assert rr_effects[0]["ci_upper"] > 0.5


# ---------------------------------------------------------------------------
# compute_effects_from_raw — MD
# ---------------------------------------------------------------------------

def test_compute_md_basic():
    """Compute MD from means and SDs."""
    from pipeline.ctgov_extractor import compute_effects_from_raw

    raw = {
        "NCT004": {
            "out1": {
                "OG000": {"events": None, "total_n": 50, "mean": 120.0, "sd": 15.0},
                "OG001": {"events": None, "total_n": 50, "mean": 130.0, "sd": 15.0},
            }
        }
    }
    result = compute_effects_from_raw(raw)
    assert "NCT004" in result
    md_effects = [e for e in result["NCT004"] if e["param_type"] == "Computed MD"]
    assert len(md_effects) == 1
    eff = md_effects[0]
    # MD = 120 - 130 = -10
    assert abs(eff["point_estimate"] - (-10.0)) < 0.01
    # SE = sqrt(15^2/50 + 15^2/50) = sqrt(4.5+4.5) = 3.0
    # CI: -10 +/- 1.96*3.0 = [-15.88, -4.12]
    from scipy.stats import norm
    z = norm.ppf(0.975)
    expected_lo = -10.0 - z * 3.0
    expected_hi = -10.0 + z * 3.0
    assert abs(eff["ci_lower"] - expected_lo) < 0.01
    assert abs(eff["ci_upper"] - expected_hi) < 0.01
    assert eff["method"] == "raw_means"


# ---------------------------------------------------------------------------
# compute_effects_from_raw — edge cases
# ---------------------------------------------------------------------------

def test_compute_effects_missing_group():
    """Only one arm -> no effects computed."""
    from pipeline.ctgov_extractor import compute_effects_from_raw

    raw = {
        "NCT005": {
            "out1": {
                "OG000": {"events": 10, "total_n": 100, "mean": None, "sd": None},
                # Missing OG001
            }
        }
    }
    result = compute_effects_from_raw(raw)
    assert result.get("NCT005") is None or len(result.get("NCT005", [])) == 0


def test_compute_effects_zero_n():
    """total_n = 0 -> skip (division by zero guard)."""
    from pipeline.ctgov_extractor import compute_effects_from_raw

    raw = {
        "NCT006": {
            "out1": {
                "OG000": {"events": 0, "total_n": 0, "mean": None, "sd": None},
                "OG001": {"events": 5, "total_n": 50, "mean": None, "sd": None},
            }
        }
    }
    result = compute_effects_from_raw(raw)
    # Should produce no effects (n_exp=0 is invalid)
    assert result.get("NCT006") is None or len(result.get("NCT006", [])) == 0


def test_compute_effects_empty_input():
    """Empty raw data -> empty results."""
    from pipeline.ctgov_extractor import compute_effects_from_raw

    assert compute_effects_from_raw({}) == {}


def test_compute_effects_events_exceed_n():
    """events > total_n -> skip (sanity guard)."""
    from pipeline.ctgov_extractor import compute_effects_from_raw

    raw = {
        "NCT007": {
            "out1": {
                "OG000": {"events": 200, "total_n": 100, "mean": None, "sd": None},
                "OG001": {"events": 10, "total_n": 100, "mean": None, "sd": None},
            }
        }
    }
    result = compute_effects_from_raw(raw)
    assert result.get("NCT007") is None or len(result.get("NCT007", [])) == 0


def test_compute_or_and_rr_both_produced():
    """Binary outcome produces both OR and RR."""
    from pipeline.ctgov_extractor import compute_effects_from_raw

    raw = {
        "NCT008": {
            "out1": {
                "OG000": {"events": 25, "total_n": 100, "mean": None, "sd": None},
                "OG001": {"events": 40, "total_n": 100, "mean": None, "sd": None},
            }
        }
    }
    result = compute_effects_from_raw(raw)
    types = {e["param_type"] for e in result["NCT008"]}
    assert "Computed OR" in types
    assert "Computed RR" in types


def test_compute_mixed_binary_and_continuous():
    """NCT with binary and continuous outcomes produces all three types."""
    from pipeline.ctgov_extractor import compute_effects_from_raw

    raw = {
        "NCT009": {
            "out_binary": {
                "OG000": {"events": 10, "total_n": 100, "mean": None, "sd": None},
                "OG001": {"events": 20, "total_n": 100, "mean": None, "sd": None},
            },
            "out_cont": {
                "OG000": {"events": None, "total_n": 60, "mean": 5.5, "sd": 2.0},
                "OG001": {"events": None, "total_n": 60, "mean": 6.5, "sd": 2.0},
            },
        }
    }
    result = compute_effects_from_raw(raw)
    types = {e["param_type"] for e in result["NCT009"]}
    assert "Computed OR" in types
    assert "Computed RR" in types
    assert "Computed MD" in types


# ---------------------------------------------------------------------------
# compute_effects_from_raw — uses scipy z, not hardcoded 1.96
# ---------------------------------------------------------------------------

def test_z_alpha_from_scipy():
    """_Z_ALPHA is computed from scipy, not hardcoded."""
    from pipeline.ctgov_extractor import _Z_ALPHA
    from scipy.stats import norm

    expected = norm.ppf(0.975)
    assert abs(_Z_ALPHA - expected) < 1e-10
    # Also verify it's close to 1.96 but not exactly (floating point)
    assert abs(_Z_ALPHA - 1.96) < 0.01


# ---------------------------------------------------------------------------
# PARAM_TYPE_MAP — computed types
# ---------------------------------------------------------------------------

def test_param_type_map_computed():
    """PARAM_TYPE_MAP includes computed effect types."""
    from pipeline.ctgov_extractor import PARAM_TYPE_MAP

    assert PARAM_TYPE_MAP["Computed OR"] == "OR"
    assert PARAM_TYPE_MAP["Computed RR"] == "RR"
    assert PARAM_TYPE_MAP["Computed MD"] == "MD"


# ---------------------------------------------------------------------------
# _load_raw_arm_data and compute_effects_from_raw are importable
# ---------------------------------------------------------------------------

def test_load_raw_arm_data_importable():
    """_load_raw_arm_data exists and is callable."""
    from pipeline.ctgov_extractor import _load_raw_arm_data

    assert callable(_load_raw_arm_data)


def test_compute_effects_from_raw_importable():
    """compute_effects_from_raw exists and is callable."""
    from pipeline.ctgov_extractor import compute_effects_from_raw

    assert callable(compute_effects_from_raw)
