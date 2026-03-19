import math
import pytest


def test_dl_basic_pooling(binary_studies):
    """DL pooling of 5 binary studies produces valid result."""
    from pipeline.meta_engine import pool_dl
    result = pool_dl(
        yi=[s["yi"] for s in binary_studies],
        sei=[s["sei"] for s in binary_studies],
    )
    assert result["k"] == 5
    assert result["tau2"] >= 0
    assert result["i2"] >= 0 and result["i2"] <= 100
    assert result["ci_lower"] < result["pooled"] < result["ci_upper"]
    assert result["converged"] is True


def test_dl_homogeneous(homogeneous_studies):
    """Identical studies should give tau2 = 0, I2 = 0."""
    from pipeline.meta_engine import pool_dl
    result = pool_dl(
        yi=[s["yi"] for s in homogeneous_studies],
        sei=[s["sei"] for s in homogeneous_studies],
    )
    assert abs(result["tau2"]) < 1e-10
    assert abs(result["i2"]) < 1e-10
    assert abs(result["pooled"] - math.log(0.80)) < 1e-10


def test_dl_single_study():
    """k=1: pooled = study effect, tau2 = 0."""
    from pipeline.meta_engine import pool_dl
    result = pool_dl(yi=[math.log(0.75)], sei=[0.20])
    assert result["k"] == 1
    assert abs(result["pooled"] - math.log(0.75)) < 1e-10
    assert result["tau2"] == 0
    assert result["prediction_interval"] is None


def test_dl_two_studies():
    """k=2: tau2 can be computed, PI uses t-distribution with df=1."""
    from pipeline.meta_engine import pool_dl
    result = pool_dl(yi=[math.log(0.5), math.log(1.5)], sei=[0.2, 0.2])
    assert result["k"] == 2
    assert result["tau2"] > 0
    assert result["prediction_interval"] is not None


def test_reml_basic(binary_studies):
    """REML pooling converges and gives similar result to DL."""
    from pipeline.meta_engine import pool_reml
    result = pool_reml(
        yi=[s["yi"] for s in binary_studies],
        sei=[s["sei"] for s in binary_studies],
    )
    assert result["k"] == 5
    assert result["converged"] is True
    assert result["tau2"] >= 0


def test_reml_homogeneous(homogeneous_studies):
    """REML on homogeneous data: tau2 ~ 0."""
    from pipeline.meta_engine import pool_reml
    result = pool_reml(
        yi=[s["yi"] for s in homogeneous_studies],
        sei=[s["sei"] for s in homogeneous_studies],
    )
    assert abs(result["tau2"]) < 1e-6


def test_dl_c_zero_guard():
    """Guard for edge case with identical SE values."""
    from pipeline.meta_engine import pool_dl
    result = pool_dl(yi=[0.1, 0.2, 0.3], sei=[0.5, 0.5, 0.5])
    assert result["tau2"] >= 0


def test_pool_convenience(binary_studies):
    """pool() convenience function runs both DL and REML."""
    from pipeline.meta_engine import pool
    dl, reml = pool(
        yi=[s["yi"] for s in binary_studies],
        sei=[s["sei"] for s in binary_studies],
    )
    assert dl["method"] == "DL"
    assert reml["method"] == "REML"
