"""Tests for pipeline.comparator — two-level reproducibility classification."""

import pytest


# ---------------------------------------------------------------------------
# Study-level tests
# ---------------------------------------------------------------------------

def test_study_level_all_matched():
    """3 extractions: 2 at 5%, 1 at 10% — rates computed with n_with_pdf denominator."""
    from pipeline.comparator import assess_study_level

    extractions = [
        {"study_id": "A", "extracted_effect": 0.73, "matched": True,
         "match_tier": "direct_5pct",  "cochrane_giv_mean": 0.75},
        {"study_id": "B", "extracted_effect": 0.62, "matched": True,
         "match_tier": "direct_5pct",  "cochrane_giv_mean": 0.60},
        {"study_id": "C", "extracted_effect": 0.85, "matched": True,
         "match_tier": "direct_10pct", "cochrane_giv_mean": 0.88},
    ]
    result = assess_study_level(total_k=3, extractions=extractions, n_with_pdf=3)

    assert result["matched_strict"]   == 2          # direct_5pct only
    assert result["matched_moderate"] == 3          # all tiers qualify
    assert abs(result["rate_strict"]   - 2 / 3) < 1e-9
    assert abs(result["rate_moderate"] - 3 / 3) < 1e-9
    assert result["n_with_pdf"] == 3
    assert result["total_k"]    == 3


def test_study_level_missing_pdfs():
    """5 total, 2 with PDF — no_pdf = 3, denominator = 2."""
    from pipeline.comparator import assess_study_level

    extractions = [
        {"study_id": "A", "extracted_effect": 0.73, "matched": True,
         "match_tier": "direct_5pct", "cochrane_giv_mean": 0.75},
        {"study_id": "B", "extracted_effect": 0.62, "matched": True,
         "match_tier": "computed_5pct", "cochrane_giv_mean": 0.60},
    ]
    result = assess_study_level(total_k=5, extractions=extractions, n_with_pdf=2)

    assert result["no_pdf"]       == 3
    assert result["n_with_pdf"]   == 2
    assert result["matched_strict"] == 2
    assert abs(result["rate_strict"] - 2 / 2) < 1e-9


# ---------------------------------------------------------------------------
# Review-level tests
# ---------------------------------------------------------------------------

def _pooled(mean, se):
    return {"pooled": mean, "se": se}


def test_review_level_reproduced():
    """Within 10%, same direction & significance, k_coverage >= 0.5 → 'reproduced'."""
    from pipeline.comparator import assess_review_level

    ref   = _pooled(-0.500, 0.10)
    repro = _pooled(-0.480, 0.10)   # 4% difference, same dir, both sig (z>1.96)
    result = assess_review_level(ref, repro, original_k=10, k_extracted=6)
    assert result["classification"] == "reproduced"


def test_review_level_major_direction_flip():
    """Opposite direction → 'major_discrepancy'."""
    from pipeline.comparator import assess_review_level

    ref   = _pooled(-0.500, 0.10)
    repro = _pooled( 0.300, 0.10)
    result = assess_review_level(ref, repro, original_k=10, k_extracted=6)
    assert result["classification"] == "major_discrepancy"


def test_review_level_major_significance_flip():
    """One significant, other not → 'major_discrepancy'."""
    from pipeline.comparator import assess_review_level

    ref   = _pooled(-0.500, 0.10)    # sig: z=5.0, p<<0.05
    repro = _pooled(-0.050, 0.10)    # not sig: z=0.5, p=0.62
    result = assess_review_level(ref, repro, original_k=10, k_extracted=6)
    assert result["classification"] == "major_discrepancy"


def test_review_level_insufficient():
    """k_coverage = 2/10 = 0.20 < 0.30 → 'insufficient'."""
    from pipeline.comparator import assess_review_level

    ref   = _pooled(-0.500, 0.10)
    repro = _pooled(-0.480, 0.10)
    result = assess_review_level(ref, repro, original_k=10, k_extracted=2)
    assert result["classification"] == "insufficient"


def test_review_level_minor_effect_diff():
    """Same direction+significance but >10% relative difference → 'minor_discrepancy'."""
    from pipeline.comparator import assess_review_level

    ref   = _pooled(-0.500, 0.10)
    repro = _pooled(-0.400, 0.10)   # 20% relative diff, same dir, both sig
    result = assess_review_level(ref, repro, original_k=10, k_extracted=6)
    assert result["classification"] == "minor_discrepancy"


def test_review_level_returns_metadata():
    """Result dict always contains k_coverage, rel_diff, ref_sig, repro_sig."""
    from pipeline.comparator import assess_review_level

    ref   = _pooled(-0.500, 0.10)
    repro = _pooled(-0.480, 0.10)
    result = assess_review_level(ref, repro, original_k=10, k_extracted=6)

    assert "k_coverage"  in result
    assert "rel_diff"    in result
    assert "ref_sig"     in result
    assert "repro_sig"   in result
    assert abs(result["k_coverage"] - 0.60) < 1e-9


# ---------------------------------------------------------------------------
# Regression: scalar .copy() spray (2026-04-15 triage-sweep)
# ---------------------------------------------------------------------------

def test_assess_review_level_handles_non_copyable_scalars():
    """Regression for 2026-04-15 triage-sweep.

    An earlier WIP sprayed `.copy()` onto dict values that are plain floats
    (``ref["pooled"]``, ``repro["pooled"]``) in pipeline.comparator.
    ``float.copy()`` raises ``AttributeError``, which halted the test suite
    at the first assess_review_level call. Same root cause as FragilityAtlas
    commit 94d1c327. This test asserts the function runs on plain-float inputs
    without calling .copy() on them.
    """
    from pipeline.comparator import assess_review_level

    # Plain python floats - must NOT be .copy()'d.
    ref   = {"pooled": -0.5, "se": 0.1}
    repro = {"pooled": -0.48, "se": 0.1}

    # Pre-fix this raises AttributeError: 'float' object has no attribute 'copy'
    result = assess_review_level(ref, repro, original_k=10, k_extracted=6)
    assert isinstance(result, dict)
    assert "classification" in result


def test_pool_dl_k1_handles_scalar_sei():
    """Regression: pipeline.meta_engine.pool_dl with k=1 accessed sei[0].copy().

    When ``sei`` is a 1-D numpy array, ``sei[0]`` is a numpy scalar; the spray
    added .copy() which fails for python-float inputs and is meaningless for
    numpy scalars (they're immutable). Verify the k=1 branch runs cleanly.
    """
    import numpy as np
    from pipeline.meta_engine import pool_dl

    yi  = np.array([0.5])
    sei = np.array([0.2])
    result = pool_dl(yi, sei)
    assert isinstance(result, dict)
    assert "pooled" in result and "se" in result


def test_pool_reml_does_not_copy_tau2_scalar():
    """Regression: pipeline.meta_engine.pool_reml called dl_result['tau2'].copy().

    ``tau2`` from ``pool_dl`` is a python float (not an array); .copy() raises.
    """
    import numpy as np
    from pipeline.meta_engine import pool_reml

    yi  = np.array([0.3, 0.5, 0.4, 0.45, 0.35])
    sei = np.array([0.1, 0.12, 0.11, 0.09, 0.1])
    result = pool_reml(yi, sei)
    assert isinstance(result, dict)
    assert "tau2" in result
