"""
AACT CT.gov Integration — pipeline/ctgov_extractor.py

Two data sources (tried in order):
1. Local AACT ZIP export (pipe-delimited text files) — fast, no network
2. Remote AACT PostgreSQL — fallback if ZIP unavailable

Public API
----------
build_aact_lookup_local(zip_path, pmids)   -> {pmid: {nct_id, effects, raw}}
get_connection()                           -> connection | None
batch_pmid_to_nct(conn, pmids)             -> {pmid: nct_id}
fetch_precomputed_effects(conn, nct_ids)   -> {nct_id: [effect_dict]}
fetch_raw_outcomes(conn, nct_ids)          -> {nct_id: [outcome_dict]}
match_aact_effect(effects, cochrane, is_r) -> match_dict | None
build_aact_lookup(conn, pmids)             -> {pmid: {nct_id, effects, raw}}

Notes
-----
- Local ZIP is preferred — no credentials needed, ~10x faster.
- match_aact_effect reuses classify_match from effect_extractor for consistency.
"""

from __future__ import annotations

import csv
import io
import os
import zipfile
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load AACT credentials for remote fallback
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")
load_dotenv(Path(r"C:\Users\user\Downloads\Metaprojects\ctgov-search-strategies\.env"))

# Default local AACT export path
AACT_ZIP_PATH = Path(
    r"C:\Users\user\Pairwise70\hfpef_registry_calibration\data\aact"
    r"\20260219_export_ctgov.zip"
)


# ---------------------------------------------------------------------------
# Local ZIP-based lookup (preferred — no network)
# ---------------------------------------------------------------------------

def _parse_float(val: str) -> Optional[float]:
    """Parse a pipe-delimited float, returning None for empty/invalid."""
    val = val.strip()
    if not val:
        return None
    try:
        return float(val)
    except ValueError:
        return None


def _read_zip_csv(zf: zipfile.ZipFile, filename: str):
    """Yield dicts from a pipe-delimited AACT text file inside the ZIP."""
    with zf.open(filename) as raw:
        reader = csv.DictReader(
            io.TextIOWrapper(raw, encoding="utf-8", errors="replace"),
            delimiter="|",
        )
        yield from reader


def _load_pmid_to_nct(zf: zipfile.ZipFile, pmid_set: set[str]) -> dict[str, str]:
    """Stream study_references.txt, return {pmid: nct_id} for target PMIDs."""
    mapping: dict[str, str] = {}
    for row in _read_zip_csv(zf, "study_references.txt"):
        pmid = (row.get("pmid") or "").strip()
        nct = (row.get("nct_id") or "").strip()
        if pmid in pmid_set and nct:
            mapping[pmid] = nct
    return mapping


def _load_precomputed_effects(
    zf: zipfile.ZipFile, nct_set: set[str]
) -> dict[str, list[dict]]:
    """Stream outcome_analyses.txt, return {nct_id: [effect_dict]}."""
    results: dict[str, list[dict]] = {}
    for row in _read_zip_csv(zf, "outcome_analyses.txt"):
        nct = (row.get("nct_id") or "").strip()
        if nct not in nct_set:
            continue
        pe = _parse_float(row.get("param_value", ""))
        if pe is None:
            continue
        if nct not in results:
            results[nct] = []
        results[nct].append({
            "param_type": (row.get("param_type") or "").strip(),
            "point_estimate": pe,
            "ci_lower": _parse_float(row.get("ci_lower_limit", "")),
            "ci_upper": _parse_float(row.get("ci_upper_limit", "")),
            "method": (row.get("method") or "").strip(),
        })
    return results


def build_aact_lookup_local(
    zip_path: str | Path | None = None,
    pmids: list[str] | None = None,
) -> dict:
    """Build AACT lookup from local ZIP export (no network needed).

    Parameters
    ----------
    zip_path : path to AACT ZIP export; defaults to AACT_ZIP_PATH
    pmids    : list of PMID strings to look up

    Returns
    -------
    {pmid: {"nct_id": str, "effects": [...]}} or empty dict on failure
    """
    zip_path = Path(zip_path) if zip_path else AACT_ZIP_PATH
    if not zip_path.exists():
        print(f"AACT ZIP not found: {zip_path}")
        return {}
    if not pmids:
        return {}

    pmid_set = set(str(p) for p in pmids)
    print(f"Loading AACT from local ZIP ({zip_path.name})...")

    with zipfile.ZipFile(zip_path, "r") as zf:
        # Step 1: PMID → NCT mapping
        pmid_to_nct = _load_pmid_to_nct(zf, pmid_set)
        nct_set = set(pmid_to_nct.values())
        print(f"  PMID->NCT: {len(pmid_to_nct)} mapped ({len(nct_set)} unique NCTs)")

        # Step 2: Pre-computed effects for those NCTs
        effects = _load_precomputed_effects(zf, nct_set)
        n_with_effects = sum(1 for v in effects.values() if v)
        print(f"  NCTs with pre-computed effects: {n_with_effects}")

    # Assemble lookup
    lookup: dict[str, dict] = {}
    for pmid, nct_id in pmid_to_nct.items():
        lookup[pmid] = {
            "nct_id": nct_id,
            "effects": effects.get(nct_id, []),
            "raw": [],  # skip raw outcomes for now — pre-computed is sufficient
        }
    return lookup


# ---------------------------------------------------------------------------
# Remote AACT PostgreSQL (fallback)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def get_connection():
    """Connect to AACT PostgreSQL. Returns connection or None on failure."""
    try:
        import psycopg2
    except ImportError:
        print("psycopg2 not installed — AACT pathway disabled")
        return None

    user = os.environ.get("AACT_USER")
    password = os.environ.get("AACT_PASSWORD")
    if not user or not password:
        print("AACT_USER / AACT_PASSWORD not set — AACT pathway disabled")
        return None

    try:
        return psycopg2.connect(
            host="aact-db.ctti-clinicaltrials.org",
            port=5432,
            database="aact",
            user=user,
            password=password,
            sslmode="require",
            connect_timeout=15,
        )
    except Exception as e:
        print(f"AACT connection failed: {e}")
        return None


# ---------------------------------------------------------------------------
# PMID → NCT mapping
# ---------------------------------------------------------------------------

def batch_pmid_to_nct(conn, pmids: list[str]) -> dict[str, str]:
    """Map PMIDs to NCT IDs via study_references table.

    Parameters
    ----------
    conn   : psycopg2 connection
    pmids  : list of PMID strings

    Returns
    -------
    dict mapping {pmid_str: nct_id}
    """
    if not pmids:
        return {}
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT pmid, nct_id FROM ctgov.study_references
        WHERE pmid = ANY(%s)
    """, (pmids,))
    mapping: dict[str, str] = {}
    for pmid, nct_id in cur.fetchall():
        if pmid and nct_id:
            mapping[str(pmid)] = nct_id
    cur.close()
    return mapping


# ---------------------------------------------------------------------------
# Fetch pre-computed effects
# ---------------------------------------------------------------------------

def fetch_precomputed_effects(conn, nct_ids: list[str]) -> dict[str, list[dict]]:
    """Fetch pre-computed effects from outcome_analyses.

    Returns {nct_id: [{param_type, point_estimate, ci_lower, ci_upper, method}]}.
    """
    if not nct_ids:
        return {}
    cur = conn.cursor()
    cur.execute("""
        SELECT nct_id, param_type, param_value,
               ci_lower_limit, ci_upper_limit, method
        FROM ctgov.outcome_analyses
        WHERE nct_id = ANY(%s) AND param_value IS NOT NULL
    """, (nct_ids,))
    results: dict[str, list[dict]] = {}
    for nct_id, param_type, value, ci_lo, ci_hi, method in cur.fetchall():
        if nct_id not in results:
            results[nct_id] = []
        results[nct_id].append({
            "param_type": param_type or "",
            "point_estimate": float(value) if value is not None else None,
            "ci_lower": float(ci_lo) if ci_lo is not None else None,
            "ci_upper": float(ci_hi) if ci_hi is not None else None,
            "method": method or "",
        })
    cur.close()
    return results


# ---------------------------------------------------------------------------
# Fetch raw outcome measurements
# ---------------------------------------------------------------------------

def fetch_raw_outcomes(conn, nct_ids: list[str]) -> dict[str, list[dict]]:
    """Fetch raw outcome measurements with group info for effect computation.

    Returns {nct_id: [{outcome_title, group_title, group_description,
                       ctgov_group_code, param_type, param_value,
                       dispersion_value}]}.
    """
    if not nct_ids:
        return {}
    cur = conn.cursor()
    cur.execute("""
        SELECT om.nct_id, o.title AS outcome_title,
               rg.title AS group_title, rg.description AS group_desc,
               rg.ctgov_group_code,
               om.param_type, om.param_value_num, om.dispersion_value_num
        FROM ctgov.outcome_measurements om
        JOIN ctgov.outcomes o
            ON om.outcome_id = o.id AND om.nct_id = o.nct_id
        JOIN ctgov.result_groups rg
            ON om.result_group_id = rg.id AND om.nct_id = rg.nct_id
        WHERE om.nct_id = ANY(%s)
    """, (nct_ids,))
    results: dict[str, list[dict]] = {}
    for row in cur.fetchall():
        nct_id = row[0]
        if nct_id not in results:
            results[nct_id] = []
        results[nct_id].append({
            "outcome_title": row[1] or "",
            "group_title": row[2] or "",
            "group_description": row[3] or "",
            "ctgov_group_code": row[4] or "",
            "param_type": row[5] or "",
            "param_value": float(row[6]) if row[6] is not None else None,
            "dispersion_value": float(row[7]) if row[7] is not None else None,
        })
    cur.close()
    return results


# ---------------------------------------------------------------------------
# AACT param_type → our effect type mapping
# ---------------------------------------------------------------------------

PARAM_TYPE_MAP: dict[str, str] = {
    "Hazard Ratio (HR)": "HR",
    "Odds Ratio (OR)": "OR",
    "Risk Ratio (RR)": "RR",
    "Risk Difference (RD)": "RD",
    "Mean Difference (Final Values)": "MD",
    "Mean Difference (Net)": "MD",
    "LS Mean Difference": "MD",
    "LS mean difference": "MD",
    "Least Squares Mean Difference": "MD",
}


# ---------------------------------------------------------------------------
# Match AACT effects to Cochrane
# ---------------------------------------------------------------------------

def match_aact_effect(
    aact_effects: list[dict],
    cochrane_mean: float,
    is_ratio: bool,
) -> Optional[dict]:
    """Try to match AACT pre-computed effects against a Cochrane value.

    Uses classify_match from effect_extractor for consistency with the PDF
    pathway.  Iterates all effects and picks the closest match that passes
    the 10% threshold.

    Parameters
    ----------
    aact_effects  : list of effect dicts from fetch_precomputed_effects
    cochrane_mean : Cochrane reference point estimate (natural scale)
    is_ratio      : True for ratio measures (OR, RR, HR)

    Returns
    -------
    dict with match info, or None if no effect matches.
    """
    from pipeline.effect_extractor import classify_match

    best: Optional[dict] = None
    best_diff = float("inf")

    for eff in aact_effects:
        pe = eff.get("point_estimate")
        if pe is None:
            continue

        result = classify_match(
            extracted=pe,
            cochrane_mean=cochrane_mean,
            is_ratio=is_ratio,
        )
        if result["matched"]:
            diff = result.get("pct_difference", float("inf"))
            if diff is not None and diff < best_diff:
                best_diff = diff
                # Remap tier names to indicate AACT source
                tier = result["match_tier"].replace("direct_", "aact_")
                best = {
                    "matched": True,
                    "match_tier": tier,
                    "pct_difference": diff,
                    "point_estimate": pe,
                    "ci_lower": eff.get("ci_lower"),
                    "ci_upper": eff.get("ci_upper"),
                    "source": "aact",
                    "aact_param_type": eff.get("param_type", ""),
                }

    return best


# ---------------------------------------------------------------------------
# One-shot lookup builder
# ---------------------------------------------------------------------------

def build_aact_lookup(conn, pmids: list[str]) -> dict:
    """Map PMIDs -> NCT IDs -> fetch all effects and raw data in bulk.

    Parameters
    ----------
    conn   : psycopg2 connection
    pmids  : deduplicated list of PMID strings

    Returns
    -------
    {pmid: {"nct_id": str, "effects": [...], "raw": [...]}}
    """
    pmid_to_nct = batch_pmid_to_nct(conn, pmids)
    nct_ids = list(set(pmid_to_nct.values()))

    effects = fetch_precomputed_effects(conn, nct_ids)
    raw = fetch_raw_outcomes(conn, nct_ids)

    lookup: dict[str, dict] = {}
    for pmid, nct_id in pmid_to_nct.items():
        lookup[pmid] = {
            "nct_id": nct_id,
            "effects": effects.get(nct_id, []),
            "raw": raw.get(nct_id, []),
        }

    return lookup
