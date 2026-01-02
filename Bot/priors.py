"""
Minimal prior utilities (market/base-rate stubs).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def _load_static_priors(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def get_binary_prior(question: Dict[str, Any]) -> Tuple[Optional[float], Dict[str, Any]]:
    """
    Retrieve a simple binary prior, if available:
      - question["market_prob"] (0-1)
      - env DEFAULT_PRIOR_PROB
      - priors/static_priors.json keyed by slug/id
    """
    meta: Dict[str, Any] = {}
    if "market_prob" in question:
        try:
            prob = float(question["market_prob"])
            meta["source"] = "market"
            return max(0.0, min(1.0, prob)), meta
        except Exception:
            pass
    env_prior = os.getenv("DEFAULT_PRIOR_PROB")
    if env_prior:
        try:
            meta["source"] = "env_default"
            return max(0.0, min(1.0, float(env_prior))), meta
        except Exception:
            pass
    static_priors = _load_static_priors(Path("priors/static_priors.json"))
    key = question.get("slug") or question.get("id") or question.get("title")
    if key and key in static_priors:
        try:
            meta["source"] = "static"
            return max(0.0, min(1.0, float(static_priors[key]))), meta
        except Exception:
            pass
    return None, {}


def blend_prior(forecast: float, prior: float, weight: float = 0.2) -> float:
    """Blend forecast with prior using a simple convex combination."""
    weight = max(0.0, min(1.0, weight))
    return forecast * (1 - weight) + prior * weight
