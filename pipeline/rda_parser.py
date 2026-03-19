"""
rda_parser.py — Load and parse Cochrane RDA files into CochraneReview dicts.

Public API
----------
parse_rows(review_id, rows)   — list[dict] → CochraneReview dict
load_rda(rda_path)             — Path → CochraneReview dict
load_all_rdas(rda_dir)         — Path → list[CochraneReview dict]

CochraneReview dict schema
--------------------------
{
    "review_id": str,
    "outcomes": [
        {
            "outcome_label": str,
            "data_type": "binary" | "continuous" | "giv_only",
            "inferred_effect_type": None,   # set downstream
            "k": int,
            "studies": [StudyDict, ...]
        }
    ],
    "total_k": int
}

StudyDict keys
--------------
study_id, year, mean, ci_start, ci_end, data_type,
events_int, total_int, events_ctrl, total_ctrl,
mean_int, sd_int, n_int,
mean_ctrl, sd_ctrl, n_ctrl,
doi, pmcid, pdf_path
"""

from __future__ import annotations

import math
import re
import warnings
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

# pyreadr is optional — only needed for load_rda / load_all_rdas
try:
    import pyreadr  # type: ignore
    _PYREADR_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PYREADR_AVAILABLE = False

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_float(val: Any) -> Optional[float]:
    """Convert val to float; return None for NaN / None / non-numeric."""
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _safe_int(val: Any) -> Optional[int]:
    """Convert val to int via float; return None for NaN / None."""
    f = _safe_float(val)
    return None if f is None else int(f)


def _detect_data_type(row: dict) -> str:
    """
    Classify a study row as 'binary', 'continuous', or 'giv_only'.

    binary     — has Experimental.cases + Control.cases + both Ns
    continuous — has Experimental.mean + Control.mean + SDs
    giv_only   — only GIV fields (Mean/CI) available
    """
    e_cases = _safe_float(row.get("Experimental.cases"))
    c_cases = _safe_float(row.get("Control.cases"))
    e_n     = _safe_float(row.get("Experimental.N"))
    c_n     = _safe_float(row.get("Control.N"))

    e_mean  = _safe_float(row.get("Experimental.mean"))
    c_mean  = _safe_float(row.get("Control.mean"))
    e_sd    = _safe_float(row.get("Experimental.SD"))
    c_sd    = _safe_float(row.get("Control.SD"))

    if (e_cases is not None and c_cases is not None
            and e_n is not None and c_n is not None):
        return "binary"

    if (e_mean is not None and c_mean is not None
            and e_sd is not None and c_sd is not None):
        return "continuous"

    return "giv_only"


def _build_study_dict(row: dict) -> dict:
    """Convert a single RDA row to a StudyDict."""
    data_type = _detect_data_type(row)

    return {
        # identity
        "study_id": row.get("Study"),
        "year":     _safe_int(row.get("Study.year")),
        # GIV fields (always present if valid)
        "mean":     _safe_float(row.get("Mean")),
        "ci_start": _safe_float(row.get("CI.start")),
        "ci_end":   _safe_float(row.get("CI.end")),
        # classification
        "data_type": data_type,
        # binary counts
        "events_int":  _safe_int(row.get("Experimental.cases")),
        "total_int":   _safe_int(row.get("Experimental.N")),
        "events_ctrl": _safe_int(row.get("Control.cases")),
        "total_ctrl":  _safe_int(row.get("Control.N")),
        # continuous
        "mean_int":  _safe_float(row.get("Experimental.mean")),
        "sd_int":    _safe_float(row.get("Experimental.SD")),
        "n_int":     _safe_int(row.get("Experimental.N")),
        "mean_ctrl": _safe_float(row.get("Control.mean")),
        "sd_ctrl":   _safe_float(row.get("Control.SD")),
        "n_ctrl":    _safe_int(row.get("Control.N")),
        # linking fields — populated downstream
        "doi":      None,
        "pmcid":    None,
        "pdf_path": None,
    }


def _majority_type(studies: list[dict]) -> str:
    """Return the most common data_type among the studies."""
    counts: dict[str, int] = defaultdict(int)
    for s in studies:
        counts[s["data_type"]] += 1
    if not counts:
        return "giv_only"
    return max(counts, key=lambda k: counts[k])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_rows(review_id: str, rows: list[dict], min_year: Optional[int] = 2000) -> dict:
    """
    Parse a list of RDA row dicts into a CochraneReview dict.

    Parameters
    ----------
    review_id : str
        Cochrane review ID, e.g. "CD000123".
    rows : list[dict]
        Each dict is one row from the RDA dataframe with columns:
        Study, Study.year, Analysis.name, Mean, CI.start, CI.end,
        Experimental.cases, Experimental.N, Control.cases, Control.N,
        Experimental.mean, Experimental.SD, Control.mean, Control.SD.
    min_year : int or None
        Only include studies with Study.year >= min_year.
        Default is 2000 (post-2000 filter). Pass None to include all years.

    Returns
    -------
    dict with keys: review_id, outcomes, total_k
    """
    # --- year filter ---
    if min_year is not None:
        filtered = [r for r in rows if (_safe_int(r.get("Study.year")) or 0) >= min_year]
    else:
        filtered = list(rows)

    # --- group by Analysis.name, preserving insertion order ---
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in filtered:
        label = row.get("Analysis.name") or "Unknown"
        groups[label].append(_build_study_dict(row))

    outcomes = []
    for label, studies in groups.items():
        dtype = _majority_type(studies)
        outcomes.append({
            "outcome_label":        label,
            "data_type":            dtype,
            "inferred_effect_type": None,   # set by downstream enricher
            "k":                    len(studies),
            "studies":              studies,
        })

    total_k = sum(o["k"] for o in outcomes)

    return {
        "review_id": review_id,
        "outcomes":  outcomes,
        "total_k":   total_k,
    }


def load_rda(rda_path: Path | str) -> dict:
    """
    Load a single RDA file and return a CochraneReview dict.

    The review_id is extracted from the filename using the pattern CD\\d+.
    Falls back to the stem if no CD number is found.

    Parameters
    ----------
    rda_path : Path or str
        Path to the .rda file.

    Returns
    -------
    CochraneReview dict (see module docstring).

    Raises
    ------
    ImportError  — if pyreadr is not installed
    Exception    — propagated from pyreadr on parse failure
    """
    if not _PYREADR_AVAILABLE:
        raise ImportError(
            "pyreadr is required for load_rda. Install with: pip install pyreadr"
        )

    rda_path = Path(rda_path)

    # Extract review_id from filename (e.g. "CD000123_data.rda" → "CD000123")
    match = re.search(r"(CD\d+)", rda_path.stem, re.IGNORECASE)
    review_id = match.group(1).upper() if match else rda_path.stem

    result = pyreadr.read_r(str(rda_path))

    # pyreadr returns an OrderedDict of {name: DataFrame}; take the first df
    df = next(iter(result.values()))

    # Convert DataFrame rows to list of dicts
    rows = df.to_dict(orient="records")

    return parse_rows(review_id, rows, min_year=None)


def load_all_rdas(rda_dir: Path | str) -> list[dict]:
    """
    Load every *.rda file in rda_dir.

    Failures are logged as warnings and skipped; the returned list contains
    only successfully parsed reviews.

    Parameters
    ----------
    rda_dir : Path or str
        Directory containing .rda files.

    Returns
    -------
    list of CochraneReview dicts
    """
    rda_dir = Path(rda_dir)
    reviews = []
    for rda_file in sorted(rda_dir.glob("*.rda")):
        try:
            review = load_rda(rda_file)
            reviews.append(review)
        except Exception as exc:  # noqa: BLE001
            warnings.warn(
                f"Skipping {rda_file.name}: {exc!r}",
                stacklevel=2,
            )
    return reviews
