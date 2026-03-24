"""
Effect Extractor Wrapper — pipeline/effect_extractor.py

Wraps the RCT Extractor v10.3 for use in the MetaReproducer pipeline.

Public API
----------
classify_match(extracted, cochrane_mean, is_ratio, computed_effect=None) -> dict
load_existing_extractions() -> dict
get_extraction_for_study(study_id, year, existing) -> list | None
extract_from_pdf(pdf_path) -> list

Notes
-----
- classify_match uses the NATURAL scale for both ratio and difference measures.
  (i.e. no log transformation — compare values as reported).
- Tier precedence: direct match is tried first; computed_effect only tried
  when extracted is None.
- Integration points (load/extract) depend on external data not available
  during unit tests; they are exercised in Task 12 integration tests.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_RCT_EXTRACTOR_PATH = r"C:\Users\user\rct-extractor-v2"
_MEGA_EVAL_PATH = (
    r"C:\Users\user\rct-extractor-v2\gold_data\mega\mega_eval_v10_3_merged.jsonl"
)

_TIER_5PCT = 0.05
_TIER_10PCT = 0.10
_TIER_20PCT = 0.20


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _rel_diff(a: float, b: float, log_scale: bool = False) -> float:
    """Relative difference.  Returns inf when b ≈ 0.

    P1-4: When log_scale=True, computes on log scale for symmetric
    comparison of ratio measures: |log(a) - log(b)| / |log(b)|.
    """
    if log_scale:
        if a <= 0 or b <= 0:
            return math.inf
        la, lb = math.log(a), math.log(b)
        denom = abs(lb)
        if denom < 1e-15:
            return math.inf
        return abs(la - lb) / denom
    denom = abs(b)
    if denom < 1e-15:
        return math.inf
    return abs(a - b) / denom


def _tier_from_rel(rel: float, prefix: str) -> Tuple[bool, Optional[str]]:
    """Map a relative difference to a match tier string.

    Returns (matched, tier_str | None).
    Tiers: 5% (strict), 10% (moderate), 20% (weak — reporting only).
    """
    if rel <= _TIER_5PCT:
        return True, f"{prefix}_5pct"
    if rel <= _TIER_10PCT:
        return True, f"{prefix}_10pct"
    if rel <= _TIER_20PCT:
        return True, f"{prefix}_20pct"
    return False, None


# ---------------------------------------------------------------------------
# classify_match
# ---------------------------------------------------------------------------

def classify_match(
    extracted: Optional[float],
    cochrane_mean: float,
    is_ratio: bool,
    computed_effect: Optional[float] = None,
) -> Dict[str, Any]:
    """Classify extracted vs Cochrane reference on the natural scale.

    Parameters
    ----------
    extracted:
        Directly extracted point estimate (None if extraction failed).
    cochrane_mean:
        Cochrane reference effect (GIV pooled or single arm mean).
    is_ratio:
        True for ratio measures (OR, RR, HR); False for difference measures
        (MD, SMD, RD).  Currently unused — comparison is always natural scale —
        but kept for future log-scale variant.
    computed_effect:
        Effect computed from raw arm data (fallback when extracted is None).

    Returns
    -------
    dict with keys:
        matched (bool)
        match_tier (str | None) — "direct_5pct", "direct_10pct",
                                   "computed_5pct", "computed_10pct"
        pct_difference (float | None) — relative diff for the winning candidate
    """
    # --- Try direct extraction first ---
    if extracted is not None:
        rel = _rel_diff(extracted, cochrane_mean, log_scale=is_ratio)
        matched, tier = _tier_from_rel(rel, "direct")
        return {
            "matched": matched,
            "match_tier": tier,
            "pct_difference": rel,
        }

    # --- Fall back to computed effect ---
    if computed_effect is not None:
        rel = _rel_diff(computed_effect, cochrane_mean, log_scale=is_ratio)
        matched, tier = _tier_from_rel(rel, "computed")
        return {
            "matched": matched,
            "match_tier": tier,
            "pct_difference": rel,
        }

    # --- Nothing available ---
    return {
        "matched": False,
        "match_tier": None,
        "pct_difference": None,
    }


# ---------------------------------------------------------------------------
# load_existing_extractions
# ---------------------------------------------------------------------------

def load_existing_extractions() -> Dict[Tuple[str, int], Any]:
    """Load pre-computed RCT Extractor results from mega_eval_v10_3_merged.jsonl.

    Returns a dict mapping (first_author, year) → entry dict, so downstream
    code can look up results without re-running extraction on ~1,290 PDFs.

    Raises FileNotFoundError if the data file is absent (integration context).
    """
    path = Path(_MEGA_EVAL_PATH)
    if not path.exists():
        raise FileNotFoundError(
            f"Mega eval file not found: {_MEGA_EVAL_PATH}\n"
            "Run RCT Extractor v10.3 to generate this file, or mount the "
            "correct OneDrive path."
        )

    index: Dict[Tuple[str, int], Any] = {}
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            first_author = entry.get("first_author", "")
            year = entry.get("year")
            if first_author and year is not None:
                key = (first_author, int(year))
                # Last entry wins if duplicate keys exist
                index[key] = entry
    return index


# ---------------------------------------------------------------------------
# get_extraction_for_study
# ---------------------------------------------------------------------------

def get_extraction_for_study(
    study_id: str,
    year: int,
    existing: Dict[Tuple[str, int], Any],
) -> Optional[List[Dict[str, Any]]]:
    """Look up a study's extraction result from the pre-loaded index.

    Parameters
    ----------
    study_id:
        First author surname (used as the dict key alongside year).
    year:
        Publication year.
    existing:
        Index returned by load_existing_extractions().

    Returns
    -------
    List of extraction dicts (keys: effect_type, point_estimate, ci_lower,
    ci_upper, confidence), or None if not found.
    Each dict corresponds to one extracted effect estimate.
    """
    key = (study_id, int(year))
    entry = existing.get(key)
    if entry is None:
        return None

    raw_extractions = entry.get("extracted")
    if not raw_extractions:
        return None

    results: List[Dict[str, Any]] = []
    for ext in raw_extractions:
        results.append(
            {
                "effect_type": ext.get("effect_type"),
                "point_estimate": ext.get("point_estimate"),
                "ci_lower": ext.get("ci_lower"),
                "ci_upper": ext.get("ci_upper"),
                "confidence": ext.get("confidence"),
            }
        )
    return results if results else None


# ---------------------------------------------------------------------------
# extract_from_pdf  (integration fallback)
# ---------------------------------------------------------------------------

def extract_from_pdf(pdf_path: str) -> List[Dict[str, Any]]:
    """Fallback: run RCT Extractor v10.3 directly on a PDF file.

    Imports PDFExtractionPipeline from the local rct-extractor-v2 checkout.
    LLM extraction is disabled; only deterministic rule-based extraction
    with raw-effect computation is performed.

    Parameters
    ----------
    pdf_path:
        Absolute path to the trial PDF.

    Returns
    -------
    List of extraction dicts (same schema as get_extraction_for_study).
    Returns an empty list on extraction failure.
    """
    extractor_src = str(Path(_RCT_EXTRACTOR_PATH) / "src")
    if extractor_src not in sys.path:
        sys.path.insert(0, extractor_src)

    try:
        from core.pdf_extraction_pipeline import PDFExtractionPipeline  # type: ignore
    except ImportError as exc:
        raise ImportError(
            f"Cannot import PDFExtractionPipeline from {extractor_src}. "
            "Ensure the rct-extractor-v2 repo is present at "
            f"{_RCT_EXTRACTOR_PATH}."
        ) from exc

    pipeline = PDFExtractionPipeline(
        compute_raw_effects=True,
        enable_llm=False,
    )

    try:
        result = pipeline.extract(pdf_path)
    except Exception:  # noqa: BLE001
        return []

    # Normalise to standard dict list
    extractions: List[Dict[str, Any]] = []
    raw_list = result if isinstance(result, list) else getattr(result, "extractions", [])
    for ext in raw_list:
        if hasattr(ext, "__dict__"):
            ext = ext.__dict__
        extractions.append(
            {
                "effect_type": ext.get("effect_type"),
                "point_estimate": ext.get("point_estimate"),
                "ci_lower": ext.get("ci_lower"),
                "ci_upper": ext.get("ci_upper"),
                "confidence": ext.get("confidence"),
            }
        )
    return extractions
