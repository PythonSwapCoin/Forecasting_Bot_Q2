"""
Baseline snapshot runner (Phase 0.3).

Runs a minimal offline suite for each question type using replay fixtures and
stores the outputs, logs, and metadata under `custom_forecasts/baseline_<ts>/`.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import os
from pathlib import Path
from typing import Dict, Any, List

from forecaster import binary_forecast, multiple_choice_forecast, numeric_forecast
from logging_utils import RunLogger, set_current_logger, get_current_logger
from run_metadata import collect_runtime_metadata, write_metadata
from smoke_suite import _load_suite, SMOKE_SUITE_PATH
from config import load_run_config


def _ensure_replay_defaults() -> None:
    os.environ.setdefault("ENABLE_REPLAY_MODE", "1")
    os.environ.setdefault("REPLAY_FIXTURES_DIR", "tests/fixtures/replay")


async def _run_single(question: Dict[str, Any], out_dir: Path) -> Dict[str, Any]:
    logger = RunLogger(echo_errors=True, echo_probabilities=True, echo_info=False)
    previous = get_current_logger()
    set_current_logger(logger)
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = {"status": "ok"}
    t0 = datetime.datetime.now(datetime.timezone.utc)
    try:
        if question["type"] == "binary":
            prob, comment = await binary_forecast(question)
            outputs["forecast"] = prob
        elif question["type"] == "numeric":
            cdf, comment = await numeric_forecast(question)
            outputs["forecast"] = cdf
        else:
            probs, comment = await multiple_choice_forecast(question)
            outputs["forecast"] = probs
        outputs["comment"] = comment
    except Exception as exc:  # noqa: BLE001
        outputs["status"] = "error"
        outputs["error"] = str(exc)
        comment = f"Error: {exc}"
    finally:
        set_current_logger(previous)
    t1 = datetime.datetime.now(datetime.timezone.utc)

    (out_dir / "forecast.txt").write_text(str(outputs.get("forecast")), encoding="utf-8")
    (out_dir / "comment.md").write_text(comment, encoding="utf-8")
    (out_dir / "run.log").write_text("\n".join(logger.buffer), encoding="utf-8")
    outputs["runtime_seconds"] = (t1 - t0).total_seconds()
    outputs["log_path"] = str(out_dir / "run.log")
    return outputs


async def run_baseline_snapshot(suite_path: Path = SMOKE_SUITE_PATH) -> Dict[str, Any]:
    _ensure_replay_defaults()
    run_config = load_run_config()
    questions = _load_suite(suite_path)
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    root = Path("custom_forecasts") / f"baseline_{ts}"
    root.mkdir(parents=True, exist_ok=True)

    results: List[Dict[str, Any]] = []
    for q in questions:
        slug = q.get("slug") or q.get("id") or q["title"]
        q_dir = root / slug
        outputs = await _run_single(q, q_dir)
        outputs["question"] = slug
        results.append(outputs)

    metadata = collect_runtime_metadata(
        run_kind="baseline_snapshot",
        run_config=run_config,
        question={"title": "baseline_suite", "type": "mixed"},
        logger=RunLogger(),  # blank logger for metadata
        extra={"suite": str(suite_path), "output_dir": str(root)},
    )
    write_metadata(str(root / "metadata.json"), metadata)
    summary = {"suite": str(suite_path), "output_dir": str(root), "results": results}
    (root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    asyncio.run(run_baseline_snapshot())
