"""
Comparator — pipeline/comparator.py

Two-level reproducibility classification:
  - Study level: strict / moderate match rates
  - Review level: reproduced / minor_discrepancy / major_discrepancy / insufficient

Public API
----------
assess_study_level(total_k, extractions, n_with_pdf) -> dict
assess_review_level(ref, repro, original_k, k_extracted, alpha=0.05) -> dict
_is_significant(pooled, se, alpha=0.05) -> bool
"""

from __future__ import annotations

from scipy import stats

# ---------------------------------------------------------------------------
# Tier definitions
# ---------------------------------------------------------------------------
STRICT_TIERS: set[str] = {"direct_5pct", "computed_5pct", "aact_5pct"}
MODERATE_TIERS: set[str] = {
    "direct_5pct", "direct_10pct",
    "computed_5pct", "computed_10pct",
    "aact_5pct", "aact_10pct",
}
WEAK_TIERS: set[str] = MODERATE_TIERS | {
    "direct_20pct", "computed_20pct", "aact_20pct",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_significant(pooled: float, se: float, alpha: float = 0.05) -> bool:
    """Two-sided z-test: return True when p < alpha."""
    if se <= 0:
        return False
    z = abs(pooled / se)
    p = 2.0 * (1.0 - stats.norm.cdf(z))
    return p < alpha


# ---------------------------------------------------------------------------
# Study-level assessment
# ---------------------------------------------------------------------------

def assess_study_level(
    total_k: int,
    extractions: list[dict],
    n_with_pdf: int,
) -> dict:
    """Count study-level match rates.

    Parameters
    ----------
    total_k    : total number of studies in the Cochrane review
    extractions: list of extraction result dicts, each with keys:
                   study_id, extracted_effect, matched, match_tier,
                   cochrane_giv_mean
    n_with_pdf : number of studies for which a PDF was obtained
                 (denominator for match rates)

    Returns
    -------
    dict with keys:
        total_k, n_with_pdf, no_pdf,
        matched_strict, matched_moderate,
        rate_strict, rate_moderate
    """
    matched_strict = sum(
        1 for e in extractions
        if e.get("match_tier") in STRICT_TIERS and e.get("matched", False)
    )
    matched_moderate = sum(
        1 for e in extractions
        if e.get("match_tier") in MODERATE_TIERS and e.get("matched", False)
    )
    matched_weak = sum(
        1 for e in extractions
        if e.get("match_tier") in WEAK_TIERS and e.get("matched", False)
    )

    denom = n_with_pdf if n_with_pdf > 0 else 1  # guard div-by-zero
    no_pdf = total_k - n_with_pdf

    return {
        "total_k": total_k,
        "n_with_pdf": n_with_pdf,
        "no_pdf": no_pdf,
        "matched_strict": matched_strict,
        "matched_moderate": matched_moderate,
        "matched_weak": matched_weak,
        "rate_strict": matched_strict / denom,
        "rate_moderate": matched_moderate / denom,
        "rate_weak": matched_weak / denom,
    }


# ---------------------------------------------------------------------------
# Review-level assessment
# ---------------------------------------------------------------------------

def assess_review_level(
    ref: dict,
    repro: dict,
    original_k: int,
    k_extracted: int,
    alpha: float = 0.05,
) -> dict:
    """Classify reproducibility at the review (meta-analysis) level.

    Parameters
    ----------
    ref         : reference pooled result dict {"pooled": float, "se": float}
    repro       : reproduced pooled result dict {"pooled": float, "se": float}
    original_k  : number of studies in the Cochrane meta-analysis
    k_extracted : number of studies successfully extracted / included
                  in the reproduced pooling
    alpha       : significance level (default 0.05)

    Returns
    -------
    dict with keys:
        classification  — "reproduced" | "minor_discrepancy" |
                          "major_discrepancy" | "insufficient"
        k_coverage      — k_extracted / original_k
        rel_diff        — |repro_pooled - ref_pooled| / |ref_pooled|
        ref_sig         — bool
        repro_sig       — bool
        same_direction  — bool
        same_sig        — bool
    """
    ref_pooled  = ref["pooled"]
    ref_se      = ref["se"]
    repro_pooled = repro["pooled"]
    repro_se     = repro["se"]

    k_coverage = k_extracted / original_k if original_k > 0 else 0.0

    ref_sig   = _is_significant(ref_pooled,   ref_se,   alpha)
    repro_sig = _is_significant(repro_pooled, repro_se, alpha)

    # P1-2: Near-zero effects have no meaningful direction
    _null_threshold = 1e-4
    if abs(ref_pooled) < _null_threshold or abs(repro_pooled) < _null_threshold:
        same_direction = True
    else:
        same_direction = (ref_pooled * repro_pooled) > 0
    same_sig = ref_sig == repro_sig

    # P1-1: Use absolute difference on log scale for near-null effects
    # to avoid denominator explosion when ref_pooled ≈ 0
    abs_diff = abs(repro_pooled - ref_pooled)
    if abs(ref_pooled) < 0.01:
        # Near null: use absolute difference directly (log-scale units)
        rel_diff = abs_diff
    else:
        rel_diff = abs_diff / abs(ref_pooled)

    # Classification logic (order matters — most severe checked first)
    if k_coverage < 0.30:
        classification = "insufficient"
    elif not same_direction or not same_sig:
        classification = "major_discrepancy"
    elif rel_diff <= 0.10 and k_coverage >= 0.50:
        classification = "reproduced"
    else:
        classification = "minor_discrepancy"

    return {
        "classification": classification,
        "k_coverage": k_coverage,
        "rel_diff": rel_diff,
        "ref_sig": ref_sig,
        "repro_sig": repro_sig,
        "same_direction": same_direction,
        "same_sig": same_sig,
    }
