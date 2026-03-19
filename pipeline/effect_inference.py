"""
Effect Type Inference — pipeline/effect_inference.py

Infer OR / RR / MD / SMD from raw study data vs the Cochrane "Mean" column
using back-computation with a relative tolerance of 1e-3.

Public API
----------
infer_effect_type(study)       -> str
infer_outcome_types(outcome)   -> None  (mutates outcome in-place)
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Optional


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _compute_or(a: float, n1: float, c: float, n2: float) -> Optional[float]:
    """Odds ratio = (a / (n1-a)) / (c / (n2-c)).

    Returns None when any cell count is zero (undefined).
    """
    b = n1 - a   # non-events in experimental arm
    d = n2 - c   # non-events in control arm
    if b <= 0 or d <= 0 or a <= 0 or c <= 0:
        return None
    return (a / b) / (c / d)


def _compute_rr(a: float, n1: float, c: float, n2: float) -> Optional[float]:
    """Risk ratio = (a/n1) / (c/n2).

    Returns None when n1, n2, or c are zero.
    """
    if n1 <= 0 or n2 <= 0 or c <= 0:
        return None
    return (a / n1) / (c / n2)


def _compute_md(m1: float, m2: float) -> float:
    """Mean difference = experimental_mean - control_mean."""
    return m1 - m2


def _compute_smd(
    m1: float,
    sd1: float,
    n1: float,
    m2: float,
    sd2: float,
    n2: float,
) -> Optional[float]:
    """Hedges' g with correction j = 1 - 3 / (4*(n1+n2-2) - 1).

    Returns None when pooled SD is zero or df <= 0.
    """
    df = n1 + n2 - 2
    if df <= 0:
        return None
    pooled_var = ((n1 - 1) * sd1 ** 2 + (n2 - 1) * sd2 ** 2) / df
    if pooled_var <= 0:
        return None
    pooled_sd = math.sqrt(pooled_var)
    d = (m1 - m2) / pooled_sd
    j = 1.0 - 3.0 / (4.0 * df - 1)
    return d * j


def _matches(computed: Optional[float], observed: float, tol: float = 1e-3) -> bool:
    """Relative-difference match: |computed - observed| / max(|observed|, 1e-10) < tol."""
    if computed is None:
        return False
    denom = max(abs(observed), 1e-10)
    return abs(computed - observed) / denom < tol


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def infer_effect_type(study: dict) -> str:
    """Infer the effect type of a single study by back-computing from raw data.

    Parameters
    ----------
    study : dict
        Must contain "data_type" and "mean".
        For binary: also "Experimental.cases", "Experimental.N",
                    "Control.cases", "Control.N".
        For continuous: also "Experimental.mean", "Experimental.SD",
                        "Experimental.N", "Control.mean", "Control.SD",
                        "Control.N".

    Returns
    -------
    str — one of: "OR", "RR", "MD", "SMD", "unknown_ratio", "ambiguous"
    """
    data_type: str = study.get("data_type", "")
    observed: float = study.get("mean", float("nan"))

    # GIV-only: no raw counts or means available
    if data_type == "giv_only":
        return "unknown_ratio"

    if data_type == "binary":
        a = study.get("Experimental.cases")
        n1 = study.get("Experimental.N")
        c = study.get("Control.cases")
        n2 = study.get("Control.N")

        if any(v is None for v in (a, n1, c, n2)):
            return "unknown_ratio"

        or_val = _compute_or(a, n1, c, n2)
        rr_val = _compute_rr(a, n1, c, n2)

        matches_or = _matches(or_val, observed)
        matches_rr = _matches(rr_val, observed)

        if matches_or and not matches_rr:
            return "OR"
        if matches_rr and not matches_or:
            return "RR"
        if matches_or and matches_rr:
            # Both match (happens when or ≈ rr, e.g. very rare events): prefer OR
            return "OR"
        # Neither matches
        return "ambiguous"

    if data_type == "continuous":
        m1 = study.get("Experimental.mean")
        sd1 = study.get("Experimental.SD")
        n1 = study.get("Experimental.N")
        m2 = study.get("Control.mean")
        sd2 = study.get("Control.SD")
        n2 = study.get("Control.N")

        if any(v is None for v in (m1, m2)):
            return "unknown_ratio"

        md_val = _compute_md(m1, m2)
        matches_md = _matches(md_val, observed)

        smd_val: Optional[float] = None
        if all(v is not None for v in (sd1, n1, sd2, n2)):
            smd_val = _compute_smd(m1, sd1, n1, m2, sd2, n2)
        matches_smd = _matches(smd_val, observed)

        if matches_md and not matches_smd:
            return "MD"
        if matches_smd and not matches_md:
            return "SMD"
        if matches_md and matches_smd:
            return "MD"
        return "ambiguous"

    # Unknown data_type
    return "unknown_ratio"


def infer_outcome_types(outcome: dict) -> None:
    """Majority-vote effect type across studies; mutates outcome in-place.

    Sets outcome["inferred_effect_type"] to the plurality winner.
    Falls back to "unknown_ratio" for empty or all-ambiguous outcomes.

    Parameters
    ----------
    outcome : dict
        Must contain "studies" list. Each study must be compatible with
        infer_effect_type().
    """
    studies = outcome.get("studies", [])
    votes: list[str] = []

    for study in studies:
        et = infer_effect_type(study)
        if et not in ("ambiguous", "unknown_ratio"):
            votes.append(et)

    if votes:
        counts = Counter(votes)
        outcome["inferred_effect_type"] = counts.most_common(1)[0][0]
    else:
        outcome["inferred_effect_type"] = "unknown_ratio"
