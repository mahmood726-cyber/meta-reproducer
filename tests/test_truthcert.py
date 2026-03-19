"""Tests for pipeline.truthcert — SHA-256 provenance chain."""

import os
import tempfile
import pytest


def test_hash_deterministic():
    """Same input dict always produces the same hash."""
    from pipeline.truthcert import hash_data

    data = {"review_id": "CD001234", "k": 10, "pooled": -0.42}
    h1 = hash_data(data)
    h2 = hash_data(data)
    assert h1 == h2
    assert h1.startswith("sha256:")


def test_hash_different_input():
    """Different input dicts produce different hashes."""
    from pipeline.truthcert import hash_data

    h1 = hash_data({"value": 1})
    h2 = hash_data({"value": 2})
    assert h1 != h2


def test_certify_produces_chain():
    """certify() returns a dict with a 4-step provenance chain."""
    from pipeline.truthcert import certify

    result = certify(
        review_id="CD001234",
        rda_hash="sha256:aabbccdd",
        extraction_hash="sha256:11223344",
        pooling_hash="sha256:deadbeef",
        classification="reproduced",
        pipeline_version="1.0.0",
    )

    assert "provenance_chain" in result
    chain = result["provenance_chain"]
    assert len(chain) == 4

    # Each step must have step_id and description
    for step in chain:
        assert "step_id" in step
        assert "description" in step

    # Step IDs should be sequential
    step_ids = [s["step_id"] for s in chain]
    assert step_ids == list(range(1, 5))

    # Top-level metadata
    assert result["review_id"]       == "CD001234"
    assert result["classification"]  == "reproduced"
    assert result["pipeline_version"] == "1.0.0"
    assert "bundle_hash" in result
    assert result["bundle_hash"].startswith("sha256:")


def test_hash_file():
    """hash_file() produces a sha256: prefixed hash of a file's contents."""
    from pipeline.truthcert import hash_file

    content = b"deterministic test content"
    with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
        f.write(content)
        tmp_path = f.name

    try:
        h = hash_file(tmp_path)
        assert h.startswith("sha256:")
        # Same file hashes consistently
        assert hash_file(tmp_path) == h
        # Different content → different hash
        with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f2:
            f2.write(b"different content")
            tmp_path2 = f2.name
        try:
            assert hash_file(tmp_path2) != h
        finally:
            os.unlink(tmp_path2)
    finally:
        os.unlink(tmp_path)
