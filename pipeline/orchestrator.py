"""
Orchestrator — pipeline/orchestrator.py

Composition layer: imports all pipeline modules and drives the full
reproduce-one-outcome workflow.

Public API
----------
se_from_ci(mean, ci_lower, ci_upper, is_ratio)  -> float | None
select_primary_outcome(outcomes)                 -> dict
reproduce_outcome(review_id, outcome)            -> dict

Internal
--------
_is_ratio_type(effect_type) -> bool
"""

from __future__ import annotations

import math
from typing import Optional

from scipy import stats

from pipeline import meta_engine, comparator, taxonomy, truthcert, effect_extractor


# ---------------------------------------------------------------------------
# Type priority for outcome selection (lower = preferred)
# ---------------------------------------------------------------------------
TYPE_PRIORITY: dict[str, int] = {
    "binary": 0,
    "continuous": 1,
    "giv_only": 2,
}

# Ratio-scale effect types (log-transform for pooling)
_RATIO_TYPES: set[str] = {"OR", "RR", "HR", "IRR", "unknown_ratio"}


# ---------------------------------------------------------------------------
# se_from_ci
# ---------------------------------------------------------------------------

def se_from_ci(
    mean: float,
    ci_lower: float,
    ci_upper: float,
    is_ratio: bool,
) -> Optional[float]:
    """Back-calculate SE from a point estimate and 95 % confidence interval.

    Parameters
    ----------
    mean      : point estimate (natural scale)
    ci_lower  : lower CI bound (natural scale)
    ci_upper  : upper CI bound (natural scale)
    is_ratio  : True for ratio measures (OR, RR, HR) — uses log scale

    Returns
    -------
    float  — estimated SE (on log scale for ratios, natural scale for diffs)
    None   — when inputs are invalid (e.g. non-positive bounds for ratio)
    """
    z = stats.norm.ppf(0.975)

    if is_ratio:
        # Guard: ratio-scale CI bounds must be positive
        if ci_lower is None or ci_upper is None:
            return None
        if ci_lower <= 0 or ci_upper <= 0:
            return None
        try:
            se = (math.log(ci_upper) - math.log(ci_lower)) / (2.0 * z)
        except (ValueError, OverflowError):
            return None
    else:
        if ci_lower is None or ci_upper is None:
            return None
        try:
            se = (ci_upper - ci_lower) / (2.0 * z)
        except (ValueError, OverflowError):
            return None

    if se <= 0 or not math.isfinite(se):
        return None
    return se


# ---------------------------------------------------------------------------
# select_primary_outcome
# ---------------------------------------------------------------------------

def select_primary_outcome(outcomes: list[dict]) -> dict:
    """Select the primary outcome from a list.

    Priority: largest k, then binary > continuous > giv_only,
    then alphabetical by outcome_label.

    Parameters
    ----------
    outcomes : list of outcome dicts (each must have "k", "data_type",
               "outcome_label")

    Returns
    -------
    dict — the selected outcome
    """
    return min(
        outcomes,
        key=lambda o: (
            -o["k"],
            TYPE_PRIORITY.get(o.get("data_type", ""), 9),
            o.get("outcome_label", ""),
        ),
    )


# ---------------------------------------------------------------------------
# _is_ratio_type
# ---------------------------------------------------------------------------

def _is_ratio_type(effect_type: str) -> bool:
    """Return True if effect_type uses log scale for pooling."""
    return effect_type in _RATIO_TYPES


# ---------------------------------------------------------------------------
# reproduce_outcome
# ---------------------------------------------------------------------------

def reproduce_outcome(review_id: str, outcome: dict) -> dict:
    """Run the full reproducibility pipeline for one outcome.

    Steps
    -----
    a. Reference pooled — back-calculate yi/SE from Cochrane studies, pool DL.
    b. Extract effects — run extraction on studies with PDFs.
    c. Study-level assessment — classify match rates.
    d. Reproduced pooled — pool matched extractions, compare.
    e. Error taxonomy — classify and aggregate study errors.
    f. TruthCert — build provenance chain.

    Parameters
    ----------
    review_id : Cochrane review ID (e.g. "CD001234")
    outcome   : outcome dict with keys: outcome_label, studies,
                data_type, inferred_effect_type, k

    Returns
    -------
    dict with keys: review_id, outcome_label, inferred_effect_type,
                    study_level, review_level, reference_pooled,
                    reproduced_pooled, extractions, errors, cert
    """
    outcome_label = outcome.get("outcome_label", "")
    effect_type = outcome.get("inferred_effect_type", "unknown_ratio")
    is_ratio = _is_ratio_type(effect_type)
    studies = outcome.get("studies", [])
    total_k = outcome.get("k", len(studies))

    # ----- (a) Reference pooled from Cochrane reported values -----
    ref_yi: list[float] = []
    ref_sei: list[float] = []

    for s in studies:
        mean_val = s.get("mean")
        ci_lo = s.get("ci_start")
        ci_hi = s.get("ci_end")

        if mean_val is None or ci_lo is None or ci_hi is None:
            continue

        se = se_from_ci(mean_val, ci_lo, ci_hi, is_ratio)
        if se is None:
            continue

        if is_ratio:
            try:
                yi = math.log(mean_val)
            except (ValueError, OverflowError):
                continue
        else:
            yi = mean_val

        ref_yi.append(yi)
        ref_sei.append(se)

    reference_pooled: Optional[dict] = None
    if ref_yi:
        reference_pooled = meta_engine.pool_dl(ref_yi, ref_sei)

    # ----- (b) Extract effects for studies with PDFs -----
    # Load pre-computed extraction results (avoids re-running on 1,290 PDFs)
    existing_extractions = effect_extractor.load_existing_extractions()

    extractions: list[dict] = []
    n_with_pdf = 0

    for s in studies:
        study_id = s.get("study_id", "")
        pdf_path = s.get("pdf_path")
        cochrane_mean = s.get("mean")
        year = s.get("year")

        extraction_result: Optional[dict] = None

        if pdf_path is not None:
            n_with_pdf += 1

            # Try pre-computed results first
            raw_extractions = effect_extractor.get_extraction_for_study(
                study_id, year, existing_extractions
            )

            # Fall back to live extraction if no pre-computed result
            if raw_extractions is None:
                try:
                    raw_extractions = effect_extractor.extract_from_pdf(pdf_path)
                except Exception:
                    raw_extractions = []

            # Find the best match against Cochrane mean
            if raw_extractions and cochrane_mean is not None:
                best_match: Optional[dict] = None
                best_rel = math.inf

                for ext in raw_extractions:
                    pt = ext.get("point_estimate")
                    if pt is None:
                        continue
                    match_result = effect_extractor.classify_match(
                        extracted=pt,
                        cochrane_mean=cochrane_mean,
                        is_ratio=is_ratio,
                    )
                    pct = match_result.get("pct_difference")
                    if pct is not None and pct < best_rel:
                        best_rel = pct
                        best_match = {
                            "study_id": study_id,
                            "extracted_effect": pt,
                            "matched": match_result["matched"],
                            "match_tier": match_result["match_tier"],
                            "pct_difference": match_result["pct_difference"],
                            "cochrane_giv_mean": cochrane_mean,
                        }

                extraction_result = best_match

            # If no match found but we had the PDF
            if extraction_result is None:
                extraction_result = {
                    "study_id": study_id,
                    "extracted_effect": None,
                    "matched": False,
                    "match_tier": None,
                    "pct_difference": None,
                    "cochrane_giv_mean": cochrane_mean,
                }

        extractions.append(extraction_result)

    # ----- (c) Study-level assessment -----
    study_level = comparator.assess_study_level(
        total_k=total_k,
        extractions=[e for e in extractions if e is not None],
        n_with_pdf=n_with_pdf,
    )

    # ----- (d) Reproduced pooled from matched extractions -----
    repro_yi: list[float] = []
    repro_sei: list[float] = []
    k_extracted = 0

    for idx, s in enumerate(studies):
        ext = extractions[idx] if idx < len(extractions) else None
        if ext is None or not ext.get("matched", False):
            continue

        extracted_effect = ext.get("extracted_effect")
        if extracted_effect is None:
            continue

        # Use Cochrane SE as proxy for the reproduced SE
        ci_lo = s.get("ci_start")
        ci_hi = s.get("ci_end")
        mean_val = s.get("mean")
        if ci_lo is None or ci_hi is None or mean_val is None:
            continue

        se = se_from_ci(mean_val, ci_lo, ci_hi, is_ratio)
        if se is None:
            continue

        if is_ratio:
            try:
                yi = math.log(extracted_effect)
            except (ValueError, OverflowError):
                continue
        else:
            yi = extracted_effect

        repro_yi.append(yi)
        repro_sei.append(se)
        k_extracted += 1

    reproduced_pooled: Optional[dict] = None
    review_level: Optional[dict] = None

    if repro_yi and reference_pooled is not None:
        reproduced_pooled = meta_engine.pool_dl(repro_yi, repro_sei)
        review_level = comparator.assess_review_level(
            ref=reference_pooled,
            repro=reproduced_pooled,
            original_k=total_k,
            k_extracted=k_extracted,
        )

    # ----- (e) Error taxonomy -----
    study_errors: list[Optional[str]] = []
    for idx, s in enumerate(studies):
        has_pdf = s.get("pdf_path") is not None
        ext = extractions[idx] if idx < len(extractions) else None
        err = taxonomy.classify_study_error(has_pdf=has_pdf, extraction=ext)
        study_errors.append(err)

    errors = taxonomy.aggregate_errors(study_errors)

    # ----- (f) TruthCert -----
    rda_hash = truthcert.hash_data({"review_id": review_id, "outcome": outcome_label})
    extraction_hash = truthcert.hash_data(extractions)
    pooling_hash = truthcert.hash_data(reproduced_pooled)

    classification = "no_extraction"
    if review_level is not None:
        classification = review_level.get("classification", "insufficient")

    cert = truthcert.certify(
        review_id=review_id,
        rda_hash=rda_hash,
        extraction_hash=extraction_hash,
        pooling_hash=pooling_hash,
        classification=classification,
    )

    return {
        "review_id": review_id,
        "outcome_label": outcome_label,
        "inferred_effect_type": effect_type,
        "study_level": study_level,
        "review_level": review_level,
        "reference_pooled": reference_pooled,
        "reproduced_pooled": reproduced_pooled,
        "extractions": extractions,
        "errors": errors,
        "cert": cert,
    }
