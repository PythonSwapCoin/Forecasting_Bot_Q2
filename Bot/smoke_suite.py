"""
Offline smoke suite runner using replay fixtures.

Runs one binary, one numeric, and one MCQ question from a suite file (default:
benchmarks/suites/smoke.jsonl) and enforces basic invariants:
- binary probability in [0, 1]
- MCQ probabilities sum to ~1 and each in [0, 1]
- numeric CDF monotonic, bounded, and length 201
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from forecaster import binary_forecast, multiple_choice_forecast, numeric_forecast
from logging_utils import RunLogger, set_current_logger
from config import load_run_config


SMOKE_SUITE_PATH = Path("benchmarks/suites/smoke.jsonl")


def _load_suite(path: Path) -> List[Dict[str, Any]]:
    questions: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                questions.append(json.loads(line))
    return questions


def _check_binary(prob: float) -> None:
    if prob is None:
        raise AssertionError("Binary forecast missing")
    if not (0.0 <= prob <= 1.0):
        raise AssertionError(f"Binary probability out of range: {prob}")


def _check_mcq(probs: Dict[str, float]) -> None:
    if not probs:
        raise AssertionError("MCQ forecast missing")
    for opt, p in probs.items():
        if p < 0.0 or p > 1.0:
            raise AssertionError(f"MCQ probability out of range for {opt}: {p}")
    total = sum(probs.values())
    if abs(total - 1.0) > 0.05:
        raise AssertionError(f"MCQ probabilities do not sum to ~1 (got {total:.3f})")


def _check_numeric(cdf: List[float]) -> None:
    if len(cdf) != 201:
        raise AssertionError(f"Numeric CDF length unexpected: {len(cdf)}")
    if cdf[0] < 0.0 or cdf[-1] > 1.0:
        raise AssertionError("Numeric CDF bounds violated")
    if any(a > b for a, b in zip(cdf, cdf[1:])):
        raise AssertionError("Numeric CDF not monotonic")


@dataclass
class SmokeResult:
    question_id: str
    status: str
    detail: str


async def _run_question(question: Dict[str, Any]) -> SmokeResult:
    logger = RunLogger(echo_errors=False, echo_probabilities=False, echo_info=False)
    set_current_logger(logger)

    qtype = question["type"]
    slug = question.get("slug") or question.get("id") or question["title"]
    try:
        if qtype == "binary":
            prob, _comment = await binary_forecast(question)
            _check_binary(prob)
        elif qtype == "numeric":
            cdf, _comment = await numeric_forecast(question)
            _check_numeric(cdf)
        elif qtype == "multiple_choice":
            probs, _comment = await multiple_choice_forecast(question)
            _check_mcq(probs)
        else:
            return SmokeResult(slug, "error", f"Unsupported type {qtype}")
        return SmokeResult(slug, "ok", "passed")
    except Exception as exc:  # noqa: BLE001
        return SmokeResult(slug, "error", str(exc))


async def run_smoke_suite(path: Path = SMOKE_SUITE_PATH) -> Dict[str, Any]:
    questions = _load_suite(path)
    results: List[SmokeResult] = []
    for q in questions:
        results.append(await _run_question(q))

    summary = {
        "suite": str(path),
        "results": [r.__dict__ for r in results],
        "passed": all(r.status == "ok" for r in results),
    }
    return summary


if __name__ == "__main__":
    # Simple manual runner
    cfg = load_run_config()
    print(f"Run config: {cfg}")
    summary = asyncio.run(run_smoke_suite())
    print(json.dumps(summary, indent=2))
