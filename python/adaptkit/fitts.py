"""Fitts' law and endpoint-spread fits.

- Movement time:  MT = a + b * ID,  ID = log2(A / W + 1)  (Shannon form; MacKenzie, 1992)
- Endpoint spread: with Gaussian endpoints (1-D approximation), the chance of a
  first-attempt hit on a target of width W is  P(hit) = erf(W / (2 * sqrt(2) * sigma)).
  sigma is estimated by maximum likelihood from hits and misses across widths.
"""

import math

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.special import erf

SIGMA_BOUNDS = (1.0, 200.0)


def index_of_difficulty(amplitude, width):
    return np.log2(np.asarray(amplitude, dtype=float) / np.asarray(width, dtype=float) + 1)


def fit_mt(ids, mts):
    """Ordinary least squares MT = a + b*ID. Returns (a_ms, b_ms_per_bit, r2)."""
    x = np.asarray(ids, dtype=float)
    y = np.asarray(mts, dtype=float)
    if len(np.unique(x)) < 2:
        return math.nan, math.nan, math.nan
    b, a = np.polyfit(x, y, 1)
    pred = a + b * x
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else math.nan
    return float(a), float(b), float(r2)


def fit_mt_by_condition(amplitude, width, mt):
    """Fit on the median MT of each (A, W) condition, the usual way to reduce noise."""
    a_arr = np.asarray(amplitude, dtype=float)
    w_arr = np.asarray(width, dtype=float)
    mt_arr = np.asarray(mt, dtype=float)
    ids, meds = [], []
    for aw in sorted(set(zip(a_arr.tolist(), w_arr.tolist()))):
        mask = (a_arr == aw[0]) & (w_arr == aw[1])
        ids.append(math.log2(aw[0] / aw[1] + 1))
        meds.append(float(np.median(mt_arr[mask])))
    return fit_mt(ids, meds)


def hit_probability(width, sigma):
    return erf(np.asarray(width, dtype=float) / (2 * math.sqrt(2) * sigma))


def fit_sigma(width, hit, lapse=0.0):
    """Maximum-likelihood endpoint spread (px). Returns (sigma, at_bound).

    lapse = chance of a slip that misses even a large target, so that
    P(hit) = (1 - lapse) * erf(...). at_bound is True when the estimate sits at
    a bound (e.g. no misses at all: the data only says sigma is small, not how small).
    """
    w = np.asarray(width, dtype=float)
    h = np.asarray(hit, dtype=float)
    eps = 1e-12

    def nll(sigma):
        p = np.clip((1 - lapse) * hit_probability(w, sigma), eps, 1 - eps)
        return -float(np.sum(h * np.log(p) + (1 - h) * np.log(1 - p)))

    res = minimize_scalar(nll, bounds=SIGMA_BOUNDS, method="bounded", options={"xatol": 1e-3})
    sigma = float(res.x)
    at_bound = sigma < SIGMA_BOUNDS[0] + 0.01 or sigma > SIGMA_BOUNDS[1] - 0.01
    return sigma, at_bound
