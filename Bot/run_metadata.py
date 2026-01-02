"""
Helpers for collecting and writing run metadata for forecasts and diagnostics.
"""

from __future__ import annotations

import datetime
import json
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Optional

from logging_utils import RunLogger
from model_config import get_model_config
from research_config import get_research_provider_status

try:
    from config import RunConfig
except Exception:
    # Keep import flexible if executed as a module without package context
    RunConfig = None  # type: ignore


DEFAULT_WEIGHTS = {
    "binary": [1, 1, 1, 2, 2],
    "numeric": [1, 1, 1, 1, 1],
    "multiple_choice": [1, 1, 1, 1, 1],
}


def _git_commit_hash() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def collect_runtime_metadata(
    *,
    run_kind: str,
    run_config: Optional["RunConfig"] = None,
    question: Optional[Dict[str, Any]] = None,
    logger: Optional[RunLogger] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build a structured metadata dictionary for a forecast run.
    """
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    provider_status = get_research_provider_status()
    models = get_model_config()

    metadata: Dict[str, Any] = {
        "timestamp_utc": now,
        "run_kind": run_kind,
        "git_commit": _git_commit_hash(),
        "models": models,
        "default_weights": DEFAULT_WEIGHTS,
        "providers": provider_status,
        "question": question or {},
    }

    if run_config is not None:
        try:
            metadata["config"] = asdict(run_config)
        except Exception:
            metadata["config"] = str(run_config)

    if logger is not None:
        try:
            metadata["search_counts"] = logger.get_search_counts()
            attempted, success = logger.get_serper_url_stats()
            metadata["serper_url_stats"] = {"attempted": attempted, "success": success}
            metadata["errors"] = logger.error_lines()
        except Exception:
            metadata["logger"] = "unavailable"

    if extra:
        metadata.update(extra)

    return metadata


def write_metadata(path: str | Path, metadata: Dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
