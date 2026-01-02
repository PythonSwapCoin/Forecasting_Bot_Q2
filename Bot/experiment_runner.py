"""
Lightweight experiment harness for running question suites across variants.

Usage examples:
  python Bot/experiment_runner.py --suite benchmarks/suites/smoke.jsonl --output results/exp.json
  python Bot/experiment_runner.py --suite benchmarks/suites/smoke.jsonl --matrix experiments/matrix.json

Matrix file format (JSON):
[
  {"name": "replay", "env": {"ENABLE_REPLAY_MODE": "1", "REPLAY_FIXTURES_DIR": "tests/fixtures/replay"}},
  {"name": "live", "env": {}}
]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from forecaster import binary_forecast, multiple_choice_forecast, numeric_forecast
from logging_utils import RunLogger, set_current_logger


def _load_suite(path: Path) -> List[Dict[str, Any]]:
    questions: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                questions.append(json.loads(line))
    return questions


@contextmanager
def _env_override(env: Dict[str, str]):
    old = {}
    try:
        for k, v in env.items():
            old[k] = os.environ.get(k)
            os.environ[k] = v
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _validate_binary(prob: float) -> None:
    if prob is None or prob < 0.0 or prob > 1.0:
        raise AssertionError(f"Binary probability invalid: {prob}")


def _validate_mcq(probs: Dict[str, float]) -> None:
    if not probs:
        raise AssertionError("MCQ probabilities missing")
    total = sum(probs.values())
    if abs(total - 1.0) > 0.05:
        raise AssertionError(f"MCQ probabilities do not sum to ~1 (total={total:.3f})")
    if any(p < 0 or p > 1 for p in probs.values()):
        raise AssertionError("MCQ probability out of range")


def _validate_numeric(cdf: List[float]) -> None:
    if len(cdf) != 201:
        raise AssertionError(f"CDF length unexpected: {len(cdf)}")
    if any(a > b for a, b in zip(cdf, cdf[1:])):
        raise AssertionError("CDF not monotonic")
    if cdf[0] < 0.0 or cdf[-1] > 1.0:
        raise AssertionError("CDF bounds violated")


@dataclass
class QuestionResult:
    question_id: str
    qtype: str
    status: str
    detail: str
    forecast: Any


async def _run_question(question: Dict[str, Any]) -> QuestionResult:
    logger = RunLogger(echo_errors=False, echo_probabilities=False, echo_info=False)
    set_current_logger(logger)

    qtype = question["type"]
    qid = question.get("id") or question.get("slug") or question.get("title")
    try:
        if qtype == "binary":
            prob, _comment = await binary_forecast(question)
            _validate_binary(prob)
            forecast = prob
        elif qtype == "numeric":
            cdf, _comment = await numeric_forecast(question)
            _validate_numeric(cdf)
            forecast = cdf
        elif qtype == "multiple_choice":
            probs, _comment = await multiple_choice_forecast(question)
            _validate_mcq(probs)
            forecast = probs
        else:
            return QuestionResult(qid, qtype, "error", f"Unsupported type {qtype}", None)
        return QuestionResult(qid, qtype, "ok", "passed", forecast)
    except Exception as exc:  # noqa: BLE001
        return QuestionResult(qid, qtype, "error", str(exc), None)


async def run_variant(variant: Dict[str, Any], questions: List[Dict[str, Any]]) -> Dict[str, Any]:
    name = variant.get("name", "default")
    env = variant.get("env", {})
    with _env_override(env):
        results: List[QuestionResult] = []
        for q in questions:
            results.append(await _run_question(q))
    summary = {
        "variant": name,
        "passed": all(r.status == "ok" for r in results),
        "results": [r.__dict__ for r in results],
        "env": env,
    }
    return summary


async def run_experiments(matrix: List[Dict[str, Any]], suite_path: Path) -> Dict[str, Any]:
    questions = _load_suite(suite_path)
    summaries = []
    for variant in matrix:
        summaries.append(await run_variant(variant, questions))
    overall = {
        "suite": str(suite_path),
        "variants": summaries,
    }
    return overall


def main() -> None:
    parser = argparse.ArgumentParser(description="Experiment runner for suites/config variants.")
    parser.add_argument("--suite", type=Path, default=Path("benchmarks/suites/smoke.jsonl"))
    parser.add_argument("--matrix", type=Path, help="JSON file describing variants with env overrides.")
    parser.add_argument("--output", type=Path, help="Path to write JSON summary.")
    args = parser.parse_args()

    if args.matrix and args.matrix.exists():
        matrix = json.loads(args.matrix.read_text(encoding="utf-8"))
    else:
        matrix = [{"name": "default", "env": {}}]

    summary = asyncio.run(run_experiments(matrix, args.suite))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
