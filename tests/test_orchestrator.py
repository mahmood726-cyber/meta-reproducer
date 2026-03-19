"""Tests for pipeline/orchestrator.py — Task 9."""

import math
import pytest


def test_reproduce_outcome_insufficient():
    """Outcome with 0 matched studies -> insufficient."""
    from pipeline.orchestrator import reproduce_outcome
    outcome = {
        "outcome_label": "Mortality",
        "studies": [
            {"study_id": "A", "mean": 0.75, "ci_start": 0.5, "ci_end": 1.1,
             "data_type": "binary", "pdf_path": None,
             "events_int": 15, "total_int": 100,
             "events_ctrl": 20, "total_ctrl": 100,
             "mean_int": None, "sd_int": None, "n_int": None,
             "mean_ctrl": None, "sd_ctrl": None, "n_ctrl": None,
             "year": 2005, "doi": None, "pmcid": None},
        ],
        "data_type": "binary",
        "inferred_effect_type": "RR",
        "k": 1,
    }
    report = reproduce_outcome("CD000123", outcome)
    assert report["study_level"]["no_pdf"] == 1
    assert report["review_level"] is None


def test_reproduce_outcome_structure():
    """Report has required keys."""
    from pipeline.orchestrator import reproduce_outcome
    outcome = {
        "outcome_label": "Mortality",
        "studies": [
            {"study_id": "A", "mean": 0.75, "ci_start": 0.55, "ci_end": 1.02,
             "data_type": "binary", "pdf_path": None,
             "events_int": 15, "total_int": 100,
             "events_ctrl": 20, "total_ctrl": 100,
             "mean_int": None, "sd_int": None, "n_int": None,
             "mean_ctrl": None, "sd_ctrl": None, "n_ctrl": None,
             "year": 2005, "doi": None, "pmcid": None},
        ],
        "data_type": "binary",
        "inferred_effect_type": "RR",
        "k": 1,
    }
    report = reproduce_outcome("CD000123", outcome)
    assert "review_id" in report
    assert "outcome_label" in report
    assert "study_level" in report
    assert "review_level" in report
    assert "errors" in report
    assert "cert" in report


def test_select_primary_outcome():
    """Primary outcome = largest k, binary preferred."""
    from pipeline.orchestrator import select_primary_outcome
    outcomes = [
        {"outcome_label": "A", "k": 5, "data_type": "continuous"},
        {"outcome_label": "B", "k": 10, "data_type": "binary"},
        {"outcome_label": "C", "k": 10, "data_type": "continuous"},
    ]
    primary = select_primary_outcome(outcomes)
    assert primary["outcome_label"] == "B"


def test_se_from_ci_ratio():
    """SE back-calculation for ratio measures."""
    from pipeline.orchestrator import se_from_ci
    from scipy import stats
    z = stats.norm.ppf(0.975)
    expected = (math.log(1.02) - math.log(0.55)) / (2 * z)
    se = se_from_ci(0.75, 0.55, 1.02, is_ratio=True)
    assert se is not None
    assert abs(se - expected) < 1e-6


def test_se_from_ci_diff():
    """SE back-calculation for difference measures."""
    from pipeline.orchestrator import se_from_ci
    from scipy import stats
    z = stats.norm.ppf(0.975)
    expected = (0.1 - (-5.1)) / (2 * z)
    se = se_from_ci(-2.5, -5.1, 0.1, is_ratio=False)
    assert se is not None
    assert abs(se - expected) < 1e-6
