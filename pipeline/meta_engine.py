"""
DerSimonian-Laird (DL) and REML random-effects meta-analysis engine.

Implements:
- pool_dl(): DerSimonian-Laird estimator for tau2
- pool_reml(): Restricted Maximum Likelihood via Fisher scoring (Viechtbauer 2005)
- pool(): Convenience function running both methods

All confidence intervals use scipy.stats for critical values (no hardcoded z=1.96).
Prediction intervals use t-distribution with df=k-2.
"""

from __future__ import annotations

import math
from typing import Optional

from scipy import stats


def _compute_pooled_and_ci(
    yi: list[float],
    vi: list[float],
    tau2: float,
    conf_level: float = 0.95,
) -> dict:
    """Compute random-effects pooled estimate, SE, CI, and PI given tau2.

    Parameters
    ----------
    yi : effect sizes
    vi : sampling variances (sei^2)
    tau2 : between-study variance
    conf_level : confidence level for intervals

    Returns
    -------
    dict with pooled, se, ci_lower, ci_upper, prediction_interval
    """
    k = len(yi)
    alpha = 1.0 - conf_level
    z_crit = stats.norm.ppf(1.0 - alpha / 2.0)

    # Random-effects weights
    w_re = [1.0 / (v + tau2) for v in vi]
    sum_w_re = sum(w_re)

    pooled = sum(w * y for w, y in zip(w_re, yi)) / sum_w_re
    se = math.sqrt(1.0 / sum_w_re)

    ci_lower = pooled - z_crit * se
    ci_upper = pooled + z_crit * se

    # Prediction interval (requires k >= 2)
    prediction_interval: Optional[dict] = None
    if k >= 2:
        df_pi = max(k - 2, 1)  # k=2 uses df=1
        t_crit = stats.t.ppf(1.0 - alpha / 2.0, df=df_pi)
        pi_se = math.sqrt(tau2 + se ** 2)
        prediction_interval = {
            "pi_lower": pooled - t_crit * pi_se,
            "pi_upper": pooled + t_crit * pi_se,
        }

    return {
        "pooled": pooled,
        "se": se,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "prediction_interval": prediction_interval,
    }


def pool_dl(
    yi: list[float],
    sei: list[float],
    conf_level: float = 0.95,
) -> dict:
    """DerSimonian-Laird random-effects meta-analysis.

    Parameters
    ----------
    yi : list of effect sizes (e.g., log-OR)
    sei : list of standard errors
    conf_level : confidence level (default 0.95)

    Returns
    -------
    dict with keys: method, pooled, ci_lower, ci_upper, se, tau2, i2,
                    q_stat, q_pvalue, k, prediction_interval, converged
    """
    k = len(yi)
    vi = [s ** 2 for s in sei]

    # k=1: trivial case
    if k == 1:
        se = sei[0]
        alpha = 1.0 - conf_level
        z_crit = stats.norm.ppf(1.0 - alpha / 2.0)
        return {
            "method": "DL",
            "pooled": yi[0],
            "ci_lower": yi[0] - z_crit * se,
            "ci_upper": yi[0] + z_crit * se,
            "se": se,
            "tau2": 0.0,
            "i2": 0.0,
            "q_stat": 0.0,
            "q_pvalue": 1.0,
            "k": 1,
            "prediction_interval": None,
            "converged": True,
        }

    # Fixed-effect weights
    w = [1.0 / v for v in vi]
    sum_w = sum(w)

    # Fixed-effect pooled estimate
    mu_fe = sum(wi * y for wi, y in zip(w, yi)) / sum_w

    # Cochran's Q
    q_stat = sum(wi * (y - mu_fe) ** 2 for wi, y in zip(w, yi))

    # DL tau2
    c = sum_w - sum(wi ** 2 for wi in w) / sum_w
    if c > 0:
        tau2 = max(0.0, (q_stat - (k - 1)) / c)
    else:
        tau2 = 0.0

    # I-squared
    if q_stat > 0:
        i2 = max(0.0, (q_stat - (k - 1)) / q_stat * 100.0)
    else:
        i2 = 0.0

    # Q p-value (chi-squared with df = k-1)
    q_pvalue = 1.0 - stats.chi2.cdf(q_stat, df=k - 1)

    # Pooled estimate with RE weights
    result = _compute_pooled_and_ci(yi, vi, tau2, conf_level)

    return {
        "method": "DL",
        "pooled": result["pooled"],
        "ci_lower": result["ci_lower"],
        "ci_upper": result["ci_upper"],
        "se": result["se"],
        "tau2": tau2,
        "i2": i2,
        "q_stat": q_stat,
        "q_pvalue": q_pvalue,
        "k": k,
        "prediction_interval": result["prediction_interval"],
        "converged": True,
    }


def pool_reml(
    yi: list[float],
    sei: list[float],
    conf_level: float = 0.95,
    max_iter: int = 100,
    tol: float = 1e-8,
) -> dict:
    """REML random-effects meta-analysis via Fisher scoring.

    Uses the correct REML Fisher scoring formula from Viechtbauer (2005):
        score = 0.5 * (sum(w_i^2 * (y_i - mu)^2) - sum(w_i))
        information = 0.5 * sum(w_i^2)
        delta = score / information
        tau2_new = max(0, tau2 + delta)

    CRITICAL: The score numerator is sum(w_i^2 * (y_i - mu)^2) - sum(w_i),
    NOT - sum(w_i^2 * v_i).

    Falls back to DL if REML does not converge.

    Parameters
    ----------
    yi : list of effect sizes
    sei : list of standard errors
    conf_level : confidence level (default 0.95)
    max_iter : maximum Fisher scoring iterations (default 100)
    tol : convergence tolerance (default 1e-8)

    Returns
    -------
    dict with same keys as pool_dl, method="REML"
    """
    k = len(yi)
    vi = [s ** 2 for s in sei]

    # k=1: trivial case — same as DL
    if k == 1:
        dl_result = pool_dl(yi, sei, conf_level)
        dl_result["method"] = "REML"
        return dl_result

    # Start from DL estimate
    dl_result = pool_dl(yi, sei, conf_level)
    tau2 = dl_result["tau2"]

    converged = False
    for _ in range(max_iter):
        # Current weights
        w = [1.0 / (v + tau2) for v in vi]
        sum_w = sum(w)

        # Current pooled estimate
        mu = sum(wi * y for wi, y in zip(w, yi)) / sum_w

        # Fisher scoring (Viechtbauer 2005)
        # Score: derivative of REML log-likelihood w.r.t. tau2
        sum_w2_resid2 = sum(wi ** 2 * (y - mu) ** 2 for wi, y in zip(w, yi))
        sum_w_val = sum(w)  # same as sum_w
        score = 0.5 * (sum_w2_resid2 - sum_w_val)

        # Expected information
        sum_w2 = sum(wi ** 2 for wi in w)
        info = 0.5 * sum_w2

        if info == 0:
            break

        delta = score / info
        tau2_new = max(0.0, tau2 + delta)

        # Convergence check: either delta is tiny, or we are at the
        # boundary (tau2=0) and the update wants to go further negative
        # (constrained optimum at 0).
        if abs(delta) < tol or (tau2_new == 0.0 and tau2 == 0.0 and delta < 0):
            tau2 = tau2_new
            converged = True
            break

        tau2 = tau2_new

    if not converged:
        # Fall back to DL
        dl_result["method"] = "REML"
        dl_result["converged"] = False
        return dl_result

    # Compute Q and I2 using fixed-effect weights (same as DL)
    w_fe = [1.0 / v for v in vi]
    sum_w_fe = sum(w_fe)
    mu_fe = sum(wi * y for wi, y in zip(w_fe, yi)) / sum_w_fe
    q_stat = sum(wi * (y - mu_fe) ** 2 for wi, y in zip(w_fe, yi))

    if q_stat > 0:
        i2 = max(0.0, (q_stat - (k - 1)) / q_stat * 100.0)
    else:
        i2 = 0.0

    q_pvalue = 1.0 - stats.chi2.cdf(q_stat, df=k - 1)

    # Pooled estimate with REML tau2
    result = _compute_pooled_and_ci(yi, vi, tau2, conf_level)

    return {
        "method": "REML",
        "pooled": result["pooled"],
        "ci_lower": result["ci_lower"],
        "ci_upper": result["ci_upper"],
        "se": result["se"],
        "tau2": tau2,
        "i2": i2,
        "q_stat": q_stat,
        "q_pvalue": q_pvalue,
        "k": k,
        "prediction_interval": result["prediction_interval"],
        "converged": converged,
    }


def pool(
    yi: list[float],
    sei: list[float],
    conf_level: float = 0.95,
) -> tuple[dict, dict]:
    """Run both DL and REML pooling and return results as a tuple.

    Parameters
    ----------
    yi : list of effect sizes
    sei : list of standard errors
    conf_level : confidence level (default 0.95)

    Returns
    -------
    (dl_result, reml_result) tuple of dicts
    """
    dl_result = pool_dl(yi, sei, conf_level)
    reml_result = pool_reml(yi, sei, conf_level)
    return dl_result, reml_result
