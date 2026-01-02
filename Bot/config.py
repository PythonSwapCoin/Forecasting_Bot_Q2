"""
Run configuration helpers and a baseline profile with all new features disabled.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, asdict
from typing import Any, Dict

from dotenv import load_dotenv

from research_config import (
    DEFAULT_RESEARCH_SOURCE,
    FALLBACK_TO_PERPLEXITY,
    PERPLEXITY_CALL_LIMIT,
    get_research_flags,
    get_research_provider_status,
)

load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class RunConfig:
    profile: str = "baseline"
    enable_replay_mode: bool = False
    replay_fixtures_dir: str = "tests/fixtures/replay"
    replay_record: bool = False
    enable_evidence_lake: bool = False
    enable_smoke_tests: bool = False
    enable_diagnostics: bool = True
    research_source: str = DEFAULT_RESEARCH_SOURCE
    research_flags: Dict[str, Any] = None  # populated at load time
    research_provider_status: Dict[str, Any] = None  # populated at load time
    perplexity_call_limit: int = PERPLEXITY_CALL_LIMIT
    fallback_to_perplexity: bool = FALLBACK_TO_PERPLEXITY
    forecast_runs_per_model: int = 1
    aggregation_mode: str = "weighted_mean"
    aggregation_trim_ratio: float = 0.1
    probability_cap_low: float = 0.02
    probability_cap_high: float = 0.98
    enable_priors: bool = False
    enable_critique: bool = False
    prior_weight: float = 0.2
    forecaster_count: int = 5
    max_historical_queries: int = 5
    max_current_queries: int = 5

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        return data


def load_run_config() -> RunConfig:
    """Load the current run configuration (baseline by default)."""
    profile = os.getenv("RUN_CONFIG_PROFILE", "baseline")
    cfg = RunConfig(
        profile=profile,
        enable_replay_mode=_env_bool("ENABLE_REPLAY_MODE", False),
        replay_fixtures_dir=os.getenv("REPLAY_FIXTURES_DIR", "tests/fixtures/replay"),
        replay_record=_env_bool("REPLAY_RECORD", False),
        enable_evidence_lake=_env_bool("ENABLE_EVIDENCE_LAKE", False),
        enable_smoke_tests=_env_bool("ENABLE_SMOKE_TESTS", False),
        enable_diagnostics=_env_bool("ENABLE_DIAGNOSTICS", True),
        research_source=DEFAULT_RESEARCH_SOURCE,
        research_flags=get_research_flags(),
        research_provider_status=get_research_provider_status(),
        perplexity_call_limit=PERPLEXITY_CALL_LIMIT,
        fallback_to_perplexity=FALLBACK_TO_PERPLEXITY,
        forecast_runs_per_model=int(os.getenv("FORECAST_RUNS_PER_MODEL", "1")),
        aggregation_mode=os.getenv("AGGREGATION_MODE", "weighted_mean"),
        aggregation_trim_ratio=float(os.getenv("AGGREGATION_TRIM_RATIO", "0.1")),
        probability_cap_low=float(os.getenv("PROBABILITY_CAP_LOW", "0.02")),
        probability_cap_high=float(os.getenv("PROBABILITY_CAP_HIGH", "0.98")),
        enable_priors=_env_bool("ENABLE_PRIORS", False),
        enable_critique=_env_bool("ENABLE_CRITIQUE", False),
        prior_weight=float(os.getenv("PRIOR_WEIGHT", "0.2")),
        forecaster_count=max(1, min(5, int(os.getenv("FORECASTER_COUNT", "5")))),
        max_historical_queries=max(1, int(os.getenv("MAX_HISTORICAL_QUERIES", "5"))),
        max_current_queries=max(1, int(os.getenv("MAX_CURRENT_QUERIES", "5"))),
    )
    return cfg


def baseline_config_dict() -> Dict[str, Any]:
    """Convenience accessor for serialization."""
    return load_run_config().to_dict()
