"""
Benchmark runner for leakage-aware backtesting (Phase 3).
"""

from __future__ import annotations

import asyncio
import datetime
import json
import math
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

from config import load_run_config
from forecaster import binary_forecast, multiple_choice_forecast, numeric_forecast
from logging_utils import RunLogger, set_current_logger
from run_metadata import collect_runtime_metadata, write_metadata


def _load_dataset(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _brier(prob: float, outcome: float) -> float:
    prob = max(0.0, min(1.0, prob))
    return (prob - outcome) ** 2


def _log_loss(prob: float, outcome: float) -> float:
    prob = max(1e-15, min(1 - 1e-15, prob))
    if outcome >= 1:
        return -math.log(prob)
    return -math.log(1 - prob)


def _mcq_brier(probs: Dict[str, float], answer: str) -> float:
    total = 0.0
    for opt, p in probs.items():
        total += (p - (1.0 if opt == answer else 0.0)) ** 2
    return total / max(1, len(probs))


def _mcq_cross_entropy(probs: Dict[str, float], answer: str) -> float:
    p = max(1e-15, min(1 - 1e-15, probs.get(answer, 0.0)))
    return -math.log(p)


def _cdf_mean(cdf: List[float], lower: float, upper: float) -> float:
    grid = np.linspace(lower, upper, num=len(cdf))
    pdf = np.diff([0.0] + cdf)
    pdf = np.maximum(pdf, 0.0)
    pdf = pdf / max(1e-9, pdf.sum())
    return float(np.sum(grid * pdf))


def _crps(cdf: List[float], lower: float, upper: float, actual: float) -> float:
    grid = np.linspace(lower, upper, num=len(cdf))
    actual_cdf = np.where(grid >= actual, 1.0, 0.0)
    diffs = np.array(cdf) - actual_cdf
    return float(np.trapz(diffs ** 2, grid))


def _mae(pred: float, actual: float) -> float:
    return abs(pred - actual)


def _ensure_replay_defaults() -> None:
    os.environ.setdefault("ENABLE_REPLAY_MODE", "1")
    os.environ.setdefault("REPLAY_FIXTURES_DIR", "tests/fixtures/replay")


def _check_leakage(evidence: List[Dict[str, Any]], cutoff: str | None) -> bool:
    if not cutoff:
        return False
    try:
        cutoff_dt = datetime.datetime.fromisoformat(cutoff)
    except Exception:
        return False
    for item in evidence:
        published = item.get("published_at") or item.get("retrieved_at")
        if not published:
            continue
        try:
            pub_dt = datetime.datetime.fromisoformat(published.replace("Z", "+00:00"))
            if pub_dt > cutoff_dt:
                return True
        except Exception:
            continue
    return False


def _calc_ece(predictions: List[float], outcomes: List[float], bins: int = 10) -> float:
    if not predictions:
        return 0.0
    bin_totals = [0] * bins
    bin_sums = [0.0] * bins
    bin_outcomes = [0.0] * bins
    for p, o in zip(predictions, outcomes):
        idx = min(bins - 1, int(p * bins))
        bin_totals[idx] += 1
        bin_sums[idx] += p
        bin_outcomes[idx] += o
    ece = 0.0
    for total, sum_p, sum_o in zip(bin_totals, bin_sums, bin_outcomes):
        if total == 0:
            continue
        avg_p = sum_p / total
        avg_o = sum_o / total
        ece += (total / len(predictions)) * abs(avg_p - avg_o)
    return float(ece)


def _catastrophic_miss(prob: float, outcome: float, threshold: float = 0.9) -> bool:
    return (prob >= threshold and outcome == 0) or (prob <= 1 - threshold and outcome == 1)


async def _run_question(question: Dict[str, Any], out_dir: Path, evidence_cutoff_override: str | None = None) -> Dict[str, Any]:
    logger = RunLogger(echo_errors=True, echo_probabilities=False, echo_info=False)
    set_current_logger(logger)
    out_dir.mkdir(parents=True, exist_ok=True)
    qtype = question["type"]
    resolved_value = question.get("resolved_value")
    evidence_cutoff = evidence_cutoff_override or question.get("evidence_cutoff")
    start = datetime.datetime.now(datetime.timezone.utc)
    forecast = None
    comment = ""

    if evidence_cutoff:
        question["resolution_date"] = evidence_cutoff

    try:
        if qtype == "binary":
            forecast, comment, details = await binary_forecast(question, return_details=True)
            prob = float(forecast)
            metrics = {
                "brier": _brier(prob, float(resolved_value)),
                "log_loss": _log_loss(prob, float(resolved_value)),
                "catastrophic_miss": _catastrophic_miss(prob, float(resolved_value)),
            }
        elif qtype == "multiple_choice":
            forecast, comment = await multiple_choice_forecast(question)
            metrics = {
                "brier": _mcq_brier(forecast, str(resolved_value)),
                "cross_entropy": _mcq_cross_entropy(forecast, str(resolved_value)),
            }
        else:
            forecast, comment = await numeric_forecast(question)
            lower = float(question["scaling"]["range_min"])
            upper = float(question["scaling"]["range_max"])
            mean_pred = _cdf_mean(forecast, lower, upper)
            metrics = {
                "mae": _mae(mean_pred, float(resolved_value)),
                "crps": _crps(forecast, lower, upper, float(resolved_value)),
                "mean_prediction": mean_pred,
            }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "error",
            "error": str(exc),
            "question": question.get("id") or question.get("title"),
        }

    elapsed = (datetime.datetime.now(datetime.timezone.utc) - start).total_seconds()
    (out_dir / "forecast.json").write_text(json.dumps(forecast, indent=2), encoding="utf-8")
    (out_dir / "comment.md").write_text(comment, encoding="utf-8")
    (out_dir / "run.log").write_text("\n".join(logger.buffer), encoding="utf-8")
    research_evidence = []
    if isinstance(question.get("research"), dict):
        research_evidence = question["research"].get("evidence", [])
    if isinstance(question.get("research_reports"), list) and not research_evidence:
        # try first report if present
        first = question["research_reports"][0] if question["research_reports"] else {}
        research_evidence = first.get("evidence", [])
    leakage = _check_leakage(research_evidence, evidence_cutoff)
    return {
        "status": "ok",
        "question": question.get("id") or question.get("title"),
        "forecast": forecast,
        "metrics": metrics,
        "metric_name": list(metrics.keys())[0] if metrics else None,
        "question_type": qtype,
        "runtime_seconds": elapsed,
        "leaky": leakage,
        "evidence_cutoff": evidence_cutoff,
    }


async def run_benchmark(dataset_path: Path, output_root: Path | None = None, evidence_cutoff: str | None = None) -> Dict[str, Any]:
    if not os.getenv("ENABLE_REPLAY_MODE"):
        _ensure_replay_defaults()
    run_config = load_run_config()
    questions = _load_dataset(dataset_path)
    question_lookup = {q.get("id") or q.get("slug") or q["title"]: q for q in questions}
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_dir = output_root or Path("benchmarks") / "runs" / f"run_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    per_question: List[Dict[str, Any]] = []
    for q in questions:
        slug = q.get("slug") or q.get("id") or q["title"]
        q_dir = out_dir / slug
        res = await _run_question(q, q_dir, evidence_cutoff_override=evidence_cutoff)
        per_question.append(res)

    ok_results = [r for r in per_question if r.get("status") == "ok"]
    type_metrics: Dict[str, List[Dict[str, float]]] = defaultdict(list)
    for r in ok_results:
        type_metrics[r["question_type"]].append(r.get("metrics", {}))

    averages: Dict[str, Dict[str, float]] = {}
    for qtype, rows in type_metrics.items():
        agg: Dict[str, List[float]] = defaultdict(list)
        for row in rows:
            for k, v in (row or {}).items():
                if isinstance(v, (int, float)):
                    agg[k].append(float(v))
        averages[qtype] = {k: float(np.mean(v)) for k, v in agg.items() if v}

    calibration = {}
    binary_probs = [float(r["forecast"]) for r in ok_results if r["question_type"] == "binary"]
    binary_outcomes = []
    for r in ok_results:
        if r["question_type"] != "binary":
            continue
        q = question_lookup.get(r["question"])
        if q and q.get("resolved_value") is not None:
            binary_outcomes.append(float(q["resolved_value"]))
    if binary_probs and binary_outcomes:
        calibration["binary_ece"] = _calc_ece(binary_probs, binary_outcomes)

    runtimes = [r.get("runtime_seconds") for r in ok_results if r.get("runtime_seconds") is not None]
    avg_runtime = float(np.mean(runtimes)) if runtimes else None
    leaky_count = sum(1 for r in per_question if r.get("leaky"))

    summary = {
        "dataset": str(dataset_path),
        "output_dir": str(out_dir),
        "averages": averages,
        "calibration": calibration,
        "average_runtime_seconds": avg_runtime,
        "leaky_questions": leaky_count,
        "total_questions": len(per_question),
        "questions": per_question,
    }
    meta = collect_runtime_metadata(
        run_kind="benchmark",
        run_config=run_config,
        question={"title": "benchmark", "type": "mixed"},
        logger=RunLogger(),
        extra={"dataset": str(dataset_path), "output_dir": str(out_dir)},
    )
    write_metadata(str(out_dir / "metadata.json"), meta)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=str, default="benchmarks/questions.jsonl", help="Path to benchmark dataset jsonl")
    parser.add_argument("--output-dir", type=str, help="Optional output directory for this run")
    parser.add_argument("--evidence-cutoff", type=str, help="Override evidence cutoff ISO date for all questions")
    parser.add_argument(
        "--profile",
        type=str,
        help="Run config profile (sets RUN_CONFIG_PROFILE before loading config)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Do not force replay defaults (use live providers/config as-is)",
    )
    args = parser.parse_args()
    if args.profile:
        os.environ["RUN_CONFIG_PROFILE"] = args.profile
    if args.live:
        os.environ["ENABLE_REPLAY_MODE"] = "0"
    out_dir = Path(args.output_dir) if args.output_dir else None
    asyncio.run(run_benchmark(Path(args.dataset), output_root=out_dir, evidence_cutoff=args.evidence_cutoff))
