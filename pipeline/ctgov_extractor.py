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
import math
import os
import re
import zipfile
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from scipy.stats import norm as _norm

# Load AACT credentials for remote fallback (P1-7: single .env location)
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")

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


_REF_TYPE_PRIORITY = {"RESULT": 0, "DERIVED": 1, "BACKGROUND": 2}


def _load_pmid_to_nct(zf: zipfile.ZipFile, pmid_set: set[str]) -> dict[str, str]:
    """Stream study_references.txt, return {pmid: nct_id} for target PMIDs.

    P0-3: Only accepts RESULT and DERIVED reference types (not BACKGROUND).
    P0-4: When multiple NCTs map to one PMID, prefers RESULT over DERIVED,
           then picks the lexicographically smallest NCT for determinism.
    """
    # Collect all candidates: {pmid: [(priority, nct_id), ...]}
    candidates: dict[str, list[tuple[int, str]]] = {}
    for row in _read_zip_csv(zf, "study_references.txt"):
        pmid = (row.get("pmid") or "").strip()
        nct = (row.get("nct_id") or "").strip()
        ref_type = (row.get("reference_type") or "").strip()
        if pmid not in pmid_set or not nct:
            continue
        priority = _REF_TYPE_PRIORITY.get(ref_type, 99)
        if priority > 1:  # Skip BACKGROUND and unknown types
            continue
        if pmid not in candidates:
            candidates[pmid] = []
        candidates[pmid].append((priority, nct))

    # Pick best NCT per PMID: lowest priority, then lexicographic NCT
    mapping: dict[str, str] = {}
    for pmid, options in candidates.items():
        options.sort()  # sort by (priority, nct_id)
        mapping[pmid] = options[0][1]
    return mapping


# Regex for extracting DOIs from citation text
_DOI_RE = re.compile(r"10\.\d{4,}/[^\s]+")


def _load_doi_to_nct(
    zf: zipfile.ZipFile, doi_set: set[str]
) -> dict[str, str]:
    """Stream study_references.txt, extract DOIs from citation text.

    Returns {doi: nct_id} for DOIs in *doi_set*.

    Uses the same RESULT/DERIVED filtering and deterministic selection
    as _load_pmid_to_nct: prefers RESULT over DERIVED, then picks the
    lexicographically smallest NCT for determinism.
    """
    # Collect all candidates: {doi: [(priority, nct_id), ...]}
    candidates: dict[str, list[tuple[int, str]]] = {}
    # Normalise DOI set to lowercase for case-insensitive matching
    doi_set_lower = {d.lower().rstrip(".") for d in doi_set}

    for row in _read_zip_csv(zf, "study_references.txt"):
        nct = (row.get("nct_id") or "").strip()
        ref_type = (row.get("reference_type") or "").strip()
        if not nct:
            continue
        priority = _REF_TYPE_PRIORITY.get(ref_type, 99)
        if priority > 1:  # Skip BACKGROUND and unknown types
            continue

        citation = (row.get("citation") or "")
        for m in _DOI_RE.finditer(citation):
            # Clean trailing punctuation from DOI
            doi_raw = m.group(0).rstrip(".,;)]\"'>:")
            doi_lower = doi_raw.lower()
            if doi_lower in doi_set_lower:
                if doi_lower not in candidates:
                    candidates[doi_lower] = []
                candidates[doi_lower].append((priority, nct))

    # Pick best NCT per DOI: lowest priority, then lexicographic NCT
    mapping: dict[str, str] = {}
    for doi, options in candidates.items():
        options.sort()  # sort by (priority, nct_id)
        mapping[doi] = options[0][1]
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


def _load_raw_arm_data(
    zf: zipfile.ZipFile, nct_set: set[str]
) -> dict[str, dict[str, dict[str, dict]]]:
    """Stream outcome_measurements.txt and outcome_counts.txt from ZIP.

    Returns nested dict:
        {nct_id: {outcome_id: {group_code: {events, total_n, mean, sd}}}}

    Only keeps data for NCTs in *nct_set* (memory-efficient).
    """
    # Structure: raw[nct][outcome_id][group_code] = {events, total_n, mean, sd}
    raw: dict[str, dict[str, dict[str, dict]]] = {}

    def _ensure_slot(nct: str, oid: str, gc: str) -> dict:
        if nct not in raw:
            raw[nct] = {}
        if oid not in raw[nct]:
            raw[nct][oid] = {}
        if gc not in raw[nct][oid]:
            raw[nct][oid][gc] = {
                "events": None,
                "total_n": None,
                "mean": None,
                "sd": None,
            }
        return raw[nct][oid][gc]

    # --- outcome_measurements.txt: events, means, SDs ---
    for row in _read_zip_csv(zf, "outcome_measurements.txt"):
        nct = (row.get("nct_id") or "").strip()
        if nct not in nct_set:
            continue
        oid = (row.get("outcome_id") or "").strip()
        gc = (row.get("ctgov_group_code") or "").strip()
        if not oid or not gc:
            continue

        param_type = (row.get("param_type") or "").strip().upper()
        val = _parse_float(row.get("param_value_num", ""))

        slot = _ensure_slot(nct, oid, gc)

        if param_type == "COUNT_OF_PARTICIPANTS" and val is not None:
            slot["events"] = val
        elif param_type == "MEAN" and val is not None:
            slot["mean"] = val
            # P0-2: Only use dispersion as SD when dispersion_type confirms it
            disp_type = (row.get("dispersion_type") or "").strip().lower()
            disp = _parse_float(row.get("dispersion_value_num", ""))
            if disp is not None:
                if disp_type in ("standard deviation", "sd", ""):
                    # Empty dispersion_type defaults to SD (most common)
                    slot["sd"] = disp
                elif disp_type in ("standard error", "standard error of mean",
                                   "standard error of the mean"):
                    # Convert SE to SD: sd = se * sqrt(n)
                    n = slot.get("total_n")
                    if n is not None and n > 0:
                        slot["sd"] = disp * math.sqrt(n)
        elif param_type == "NUMBER" and val is not None:
            # NUMBER can also represent event counts
            if slot["events"] is None:
                slot["events"] = val

    # --- outcome_counts.txt: total N per arm ---
    for row in _read_zip_csv(zf, "outcome_counts.txt"):
        nct = (row.get("nct_id") or "").strip()
        if nct not in nct_set:
            continue
        scope = (row.get("scope") or "").strip()
        units = (row.get("units") or "").strip()
        if scope != "Measure" or units != "Participants":
            continue
        oid = (row.get("outcome_id") or "").strip()
        gc = (row.get("ctgov_group_code") or "").strip()
        count = _parse_float(row.get("count", ""))
        if not oid or not gc or count is None:
            continue

        slot = _ensure_slot(nct, oid, gc)
        slot["total_n"] = count

    return raw


# Critical value for 95% CI (two-sided)
_Z_ALPHA = _norm.ppf(0.975)


def compute_effects_from_raw(
    raw_data: dict[str, dict[str, dict[str, dict]]],
) -> dict[str, list[dict]]:
    """Compute OR, RR, and MD from raw arm-level data.

    Parameters
    ----------
    raw_data : nested dict from _load_raw_arm_data

    Returns
    -------
    {nct_id: [{param_type, point_estimate, ci_lower, ci_upper, method}]}
    Same format as pre-computed effects for seamless merging.
    """
    results: dict[str, list[dict]] = {}

    for nct_id, outcomes in raw_data.items():
        for outcome_id, groups in outcomes.items():
            # P0-3: Don't assume OG000=exp, OG001=ctrl. Use any two groups.
            # CT.gov group codes are order-dependent, not role-dependent.
            # We compute effects for both orderings; match_aact_effect's
            # reciprocal matching (P1-3) handles direction resolution.
            group_codes = sorted(groups.keys())
            if len(group_codes) < 2:
                continue
            # Use first two groups (typically OG000 and OG001)
            g1, g2 = groups[group_codes[0]], groups[group_codes[1]]

            # --- Binary outcome: both have events + total_n ---
            # P0-1: Use nested block (not continue) so continuous still runs
            _binary_ok = (
                g1.get("events") is not None
                and g2.get("events") is not None
                and g1.get("total_n") is not None
                and g2.get("total_n") is not None
            )
            if _binary_ok:
                a = g1["events"]
                n_a = g1["total_n"]
                c = g2["events"]
                n_c_bin = g2["total_n"]

                # Sanity + P1-1: skip double-zero (Cochrane excludes these)
                _valid = (
                    n_a > 0 and n_c_bin > 0
                    and a >= 0 and c >= 0
                    and a <= n_a and c <= n_c_bin
                    and not (a == 0 and c == 0)  # double-zero exclusion
                )
                if _valid:
                    b = n_a - a
                    d = n_c_bin - c

                    cc = 0.5 if (a == 0 or b == 0 or c == 0 or d == 0) else 0.0
                    a_c, b_c, c_c, d_c = a + cc, b + cc, c + cc, d + cc
                    n_a_c = n_a + 2 * cc
                    n_c_c = n_c_bin + 2 * cc

                    # --- OR ---
                    denom_or = b_c * c_c
                    if denom_or > 0:
                        or_val = (a_c * d_c) / denom_or
                        if or_val > 0:
                            log_or = math.log(or_val)
                            se_sq = 1/a_c + 1/b_c + 1/c_c + 1/d_c
                            if se_sq > 1e-10:  # P1-2: SE floor
                                se = math.sqrt(se_sq)
                                ci_lo = math.exp(log_or - _Z_ALPHA * se)
                                ci_hi = math.exp(log_or + _Z_ALPHA * se)
                                if nct_id not in results:
                                    results[nct_id] = []
                                results[nct_id].append({
                                    "param_type": "Computed OR",
                                    "point_estimate": round(or_val, 6),
                                    "ci_lower": round(ci_lo, 6),
                                    "ci_upper": round(ci_hi, 6),
                                    "method": "raw_2x2",
                                })

                    # --- RR ---
                    p_a = a_c / n_a_c
                    p_c = c_c / n_c_c
                    if p_c > 0:
                        rr_val = p_a / p_c
                        if rr_val > 0 and a_c > 0 and c_c > 0:
                            log_rr = math.log(rr_val)
                            se_sq = 1/a_c - 1/n_a_c + 1/c_c - 1/n_c_c
                            if se_sq > 1e-10:  # P1-2: SE floor
                                se = math.sqrt(se_sq)
                                ci_lo = math.exp(log_rr - _Z_ALPHA * se)
                                ci_hi = math.exp(log_rr + _Z_ALPHA * se)
                                if nct_id not in results:
                                    results[nct_id] = []
                                results[nct_id].append({
                                    "param_type": "Computed RR",
                                    "point_estimate": round(rr_val, 6),
                                    "ci_lower": round(ci_lo, 6),
                                    "ci_upper": round(ci_hi, 6),
                                    "method": "raw_2x2",
                                })

            # --- Continuous outcome: both have mean + sd + total_n ---
            # P0-1: Independent of binary block (no continue above)
            _cont_ok = (
                g1.get("mean") is not None
                and g2.get("mean") is not None
                and g1.get("sd") is not None
                and g2.get("sd") is not None
                and g1.get("total_n") is not None
                and g2.get("total_n") is not None
            )
            if _cont_ok:
                mean_1 = g1["mean"]
                mean_2 = g2["mean"]
                sd_1 = g1["sd"]
                sd_2 = g2["sd"]
                n_1 = g1["total_n"]
                n_2 = g2["total_n"]

                if n_1 > 0 and n_2 > 0 and sd_1 >= 0 and sd_2 >= 0:
                    # P2-5: Skip when both SDs are exactly 0
                    if sd_1 == 0 and sd_2 == 0:
                        pass
                    else:
                        md = mean_1 - mean_2
                        var_sum = (sd_1 ** 2) / n_1 + (sd_2 ** 2) / n_2
                        if var_sum > 0:
                            se_md = math.sqrt(var_sum)
                            ci_lo = md - _Z_ALPHA * se_md
                            ci_hi = md + _Z_ALPHA * se_md
                            if nct_id not in results:
                                results[nct_id] = []
                            results[nct_id].append({
                                "param_type": "Computed MD",
                                "point_estimate": round(md, 6),
                                "ci_lower": round(ci_lo, 6),
                                "ci_upper": round(ci_hi, 6),
                                "method": "raw_means",
                            })

    return results


def build_aact_lookup_local(
    zip_path: str | Path | None = None,
    pmids: list[str] | None = None,
    dois: list[str] | None = None,
) -> dict:
    """Build AACT lookup from local ZIP export (no network needed).

    Parameters
    ----------
    zip_path : path to AACT ZIP export; defaults to AACT_ZIP_PATH
    pmids    : list of PMID strings to look up
    dois     : optional list of DOI strings for studies without PMIDs;
               DOIs are extracted from citation text in study_references.txt

    Returns
    -------
    {key: {"nct_id": str, "effects": [...]}} where key is PMID or DOI.
    Returns empty dict on failure.
    """
    zip_path = Path(zip_path) if zip_path else AACT_ZIP_PATH
    if not zip_path.exists():
        print(f"AACT ZIP not found: {zip_path}")
        return {}
    if not pmids and not dois:
        return {}

    pmid_set = set(str(p) for p in pmids) if pmids else set()
    doi_set = set(str(d) for d in dois) if dois else set()
    print(f"Loading AACT from local ZIP ({zip_path.name})...")

    with zipfile.ZipFile(zip_path, "r") as zf:
        # Step 1a: PMID → NCT mapping
        pmid_to_nct = _load_pmid_to_nct(zf, pmid_set) if pmid_set else {}
        nct_set = set(pmid_to_nct.values())
        print(f"  PMID->NCT: {len(pmid_to_nct)} mapped ({len(nct_set)} unique NCTs)")

        # Step 1b: DOI → NCT mapping (for studies without PMIDs)
        doi_to_nct: dict[str, str] = {}
        if doi_set:
            doi_to_nct = _load_doi_to_nct(zf, doi_set)
            nct_set |= set(doi_to_nct.values())
            print(f"  DOI->NCT: {len(doi_to_nct)} mapped")

        # Step 2: Pre-computed effects for those NCTs
        effects = _load_precomputed_effects(zf, nct_set)
        n_with_effects = sum(1 for v in effects.values() if v)
        print(f"  NCTs with pre-computed effects: {n_with_effects}")

        # Step 3: Raw arm data → compute OR/RR/MD for NCTs lacking effects
        raw_arm = _load_raw_arm_data(zf, nct_set)
        computed = compute_effects_from_raw(raw_arm)
        n_with_computed = sum(1 for v in computed.values() if v)
        print(f"  NCTs with computed effects: {n_with_computed}")

    # Merge: pre-computed effects first, computed effects appended
    merged_effects: dict[str, list[dict]] = {}
    all_ncts = set(effects.keys()) | set(computed.keys())
    for nct_id in all_ncts:
        merged = list(effects.get(nct_id, []))
        merged.extend(computed.get(nct_id, []))
        merged_effects[nct_id] = merged

    # Assemble lookup — keyed by PMID or DOI
    lookup: dict[str, dict] = {}
    for pmid, nct_id in pmid_to_nct.items():
        lookup[pmid] = {
            "nct_id": nct_id,
            "effects": merged_effects.get(nct_id, []),
            "raw": [],
        }
    for doi, nct_id in doi_to_nct.items():
        lookup[doi] = {
            "nct_id": nct_id,
            "effects": merged_effects.get(nct_id, []),
            "raw": [],
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
    except Exception:
        print("AACT connection failed (check credentials and network)")
        return None


# ---------------------------------------------------------------------------
# PMID → NCT mapping
# ---------------------------------------------------------------------------

def batch_pmid_to_nct(conn, pmids: list[str]) -> dict[str, str]:
    """Map PMIDs to NCT IDs via study_references table.

    P0-3: Filters to RESULT/DERIVED types only (not BACKGROUND).
    P0-4: Deterministic — prefers RESULT, then lexicographic NCT.
    P1-6: Uses context manager for cursor cleanup.
    """
    if not pmids:
        return {}
    with conn.cursor() as cur:
        cur.execute("""
            SELECT pmid, nct_id, reference_type
            FROM ctgov.study_references
            WHERE pmid = ANY(%s)
              AND reference_type IN ('RESULT', 'DERIVED')
        """, (pmids,))
        candidates: dict[str, list[tuple[int, str]]] = {}
        for pmid, nct_id, ref_type in cur.fetchall():
            if not pmid or not nct_id:
                continue
            key = str(pmid)
            priority = 0 if ref_type == "RESULT" else 1
            if key not in candidates:
                candidates[key] = []
            candidates[key].append((priority, nct_id))

    mapping: dict[str, str] = {}
    for pmid, options in candidates.items():
        options.sort()
        mapping[pmid] = options[0][1]
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
    results: dict[str, list[dict]] = {}
    with conn.cursor() as cur:
        cur.execute("""
            SELECT nct_id, param_type, param_value,
                   ci_lower_limit, ci_upper_limit, method
            FROM ctgov.outcome_analyses
            WHERE nct_id = ANY(%s) AND param_value IS NOT NULL
        """, (nct_ids,))
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
    results: dict[str, list[dict]] = {}
    with conn.cursor() as cur:
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
    # Computed from raw arm-level data
    "Computed OR": "OR",
    "Computed RR": "RR",
    "Computed MD": "MD",
}


# ---------------------------------------------------------------------------
# Match AACT effects to Cochrane
# ---------------------------------------------------------------------------

def match_aact_effect(
    aact_effects: list[dict],
    cochrane_mean: float,
    is_ratio: bool,
    effect_type: str = "",
) -> Optional[dict]:
    """Try to match AACT pre-computed effects against a Cochrane value.

    P0-1: Filters effects by param_type compatibility with Cochrane effect_type.
    P1-3: For ratio measures, also tries reciprocal match (1/cochrane_mean).

    Parameters
    ----------
    aact_effects  : list of effect dicts from fetch_precomputed_effects
    cochrane_mean : Cochrane reference point estimate (natural scale)
    is_ratio      : True for ratio measures (OR, RR, HR)
    effect_type   : Cochrane effect type string (e.g. "OR", "HR", "MD")

    Returns
    -------
    dict with match info, or None if no effect matches.
    """
    from pipeline.effect_extractor import classify_match

    # P0-1: Filter to type-compatible effects first
    compatible = []
    for eff in aact_effects:
        if eff.get("point_estimate") is None:
            continue
        # P1-7: Case-insensitive lookup for robustness
        raw_pt = eff.get("param_type", "")
        aact_type = PARAM_TYPE_MAP.get(raw_pt, "") or PARAM_TYPE_MAP.get(raw_pt.title(), "")
        if effect_type and aact_type and aact_type != effect_type:
            continue  # Skip type-mismatched effects
        compatible.append(eff)

    # If no type-compatible effects, try all effects as fallback
    if not compatible:
        compatible = [e for e in aact_effects if e.get("point_estimate") is not None]

    best: Optional[dict] = None
    best_diff = float("inf")

    # P1-3: For ratio measures, also try reciprocal Cochrane mean
    targets = [cochrane_mean]
    if is_ratio and cochrane_mean is not None and cochrane_mean > 0:
        reciprocal = 1.0 / cochrane_mean
        targets.append(reciprocal)

    for eff in compatible:
        pe = eff["point_estimate"]

        for target in targets:
            result = classify_match(
                extracted=pe,
                cochrane_mean=target,
                is_ratio=is_ratio,
            )
            if result["matched"]:
                diff = result.get("pct_difference", float("inf"))
                if diff is not None and diff < best_diff:
                    best_diff = diff
                    # Remap tier names: direct_ or computed_ → aact_
                    raw_tier = result["match_tier"] or ""
                    tier = raw_tier.replace("direct_", "aact_").replace("computed_", "aact_")
                    is_reciprocal = (target != cochrane_mean)
                    best = {
                        "matched": True,
                        "match_tier": tier,
                        "pct_difference": diff,
                        "point_estimate": pe,
                        "ci_lower": eff.get("ci_lower"),
                        "ci_upper": eff.get("ci_upper"),
                        "source": "aact",
                        "aact_param_type": eff.get("param_type", ""),
                        "reciprocal_match": is_reciprocal,
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
