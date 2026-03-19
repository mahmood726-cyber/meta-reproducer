"""
TruthCert — pipeline/truthcert.py

SHA-256 provenance chain for MetaReproducer audit bundles.

The four-step chain records:
  1. RDA ingestion    — Cochrane RDA file hash
  2. PDF extraction   — extraction results hash
  3. Re-pooling       — reproduced pooled result hash
  4. Classification   — reproducibility verdict + bundle seal

Public API
----------
hash_data(data)                                              -> str
hash_file(file_path)                                         -> str
certify(review_id, rda_hash, extraction_hash,
        pooling_hash, classification,
        pipeline_version="1.0.0")                           -> dict
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


_CHUNK_SIZE = 65_536  # 64 KB read chunks for file hashing


# ---------------------------------------------------------------------------
# Hashing helpers
# ---------------------------------------------------------------------------

def hash_data(data: Any) -> str:
    """SHA-256 hash of JSON-serialised data (sort_keys for determinism).

    Parameters
    ----------
    data : any JSON-serialisable object

    Returns
    -------
    str — "sha256:<hex_digest>"
    """
    serialised = json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")
    digest = hashlib.sha256(serialised).hexdigest()
    return f"sha256:{digest}"


def hash_file(file_path: str | Path) -> str:
    """SHA-256 hash of a file's binary contents.

    Parameters
    ----------
    file_path : path to the file

    Returns
    -------
    str — "sha256:<hex_digest>"
    """
    h = hashlib.sha256()
    with open(file_path, "rb") as fh:
        while chunk := fh.read(_CHUNK_SIZE):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


# ---------------------------------------------------------------------------
# Certification
# ---------------------------------------------------------------------------

def certify(
    review_id: str,
    rda_hash: str,
    extraction_hash: str,
    pooling_hash: str,
    classification: str,
    pipeline_version: str = "1.0.0",
) -> dict:
    """Build a 4-step provenance chain and seal the bundle.

    Parameters
    ----------
    review_id        : Cochrane review identifier (e.g. "CD001234")
    rda_hash         : sha256 hash of the source RDA file
    extraction_hash  : sha256 hash of the extraction results
    pooling_hash     : sha256 hash of the reproduced pooled output
    classification   : reproducibility verdict string
    pipeline_version : semantic version of the pipeline (default "1.0.0")

    Returns
    -------
    dict with:
        review_id, pipeline_version, classification,
        provenance_chain (list of 4 step dicts),
        bundle_hash (sha256 of the whole bundle payload)
    """
    provenance_chain = [
        {
            "step_id": 1,
            "description": "RDA ingestion — Cochrane source file",
            "input_hash": rda_hash,
        },
        {
            "step_id": 2,
            "description": "PDF extraction — effect values extracted from trial PDFs",
            "input_hash": extraction_hash,
        },
        {
            "step_id": 3,
            "description": "Re-pooling — DL/REML random-effects meta-analysis",
            "input_hash": pooling_hash,
        },
        {
            "step_id": 4,
            "description": "Classification — reproducibility verdict",
            "input_hash": hash_data(
                {
                    "rda_hash": rda_hash,
                    "extraction_hash": extraction_hash,
                    "pooling_hash": pooling_hash,
                    "classification": classification,
                }
            ),
        },
    ]

    # Seal the bundle by hashing the full provenance payload
    bundle_payload = {
        "review_id": review_id,
        "pipeline_version": pipeline_version,
        "classification": classification,
        "provenance_chain": provenance_chain,
    }
    bundle_hash = hash_data(bundle_payload)

    return {
        "review_id": review_id,
        "pipeline_version": pipeline_version,
        "classification": classification,
        "provenance_chain": provenance_chain,
        "bundle_hash": bundle_hash,
    }
