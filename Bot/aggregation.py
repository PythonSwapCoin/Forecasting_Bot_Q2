"""
Aggregation and robustness helpers (Phase 5/8 scaffolding).
"""

from __future__ import annotations

import numpy as np
from typing import Iterable, List, Optional, Sequence


def cap_probability(p: float, lo: float = 0.02, hi: float = 0.98) -> float:
    return max(lo, min(hi, p))


def remove_outliers(values: Sequence[float], z_threshold: float = 3.0) -> List[float]:
    if not values:
        return []
    arr = np.array(values, dtype=float)
    mean = np.mean(arr)
    std = np.std(arr)
    if std == 0:
        return list(arr)
    mask = np.abs(arr - mean) <= z_threshold * std
    return list(arr[mask])


def aggregate_binary(
    probs: Sequence[float],
    weights: Optional[Sequence[float]] = None,
    mode: str = "weighted_mean",
    trim_ratio: float = 0.1,
) -> Optional[float]:
    vals = np.array([p for p in probs if p is not None], dtype=float)
    if len(vals) == 0:
        return None
    if weights is None or len(weights) != len(vals):
        weights = np.ones_like(vals)
    weights = np.array(weights, dtype=float)
    weights = weights / weights.sum()

    if mode == "median":
        return float(np.median(vals))
    if mode == "trimmed_mean":
        sorted_vals = np.sort(vals)
        k = int(len(sorted_vals) * trim_ratio)
        trimmed = sorted_vals[k : len(sorted_vals) - k] if len(sorted_vals) > 2 * k else sorted_vals
        return float(np.mean(trimmed))
    # default: weighted mean
    return float(np.average(vals, weights=weights))


def aggregate_mcq(
    distributions: Sequence[dict],
    weights: Optional[Sequence[float]] = None,
    mode: str = "weighted_mean",
) -> dict:
    if not distributions:
        return {}
    keys = set().union(*distributions)
    weights_arr = np.array(weights if weights else [1.0] * len(distributions), dtype=float)
    weights_arr = weights_arr / weights_arr.sum()
    combined = {}
    for k in keys:
        vals = np.array([dist.get(k, 0.0) for dist in distributions], dtype=float)
        if mode == "median":
            combined[k] = float(np.median(vals))
        else:
            combined[k] = float(np.average(vals, weights=weights_arr))
    total = sum(combined.values()) or 1.0
    return {k: max(0.0, v) / total for k, v in combined.items()}
