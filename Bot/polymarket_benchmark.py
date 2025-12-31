#!/usr/bin/env python3
"""
Polymarket-style benchmark runner for the custom forecast pipeline.

Update POLYMARKET_QUESTIONS with 5 binary markets. Required fields:
- title (str)
- description (str)
- resolution_criteria (str)
- market_probability (float between 0 and 1, from Polymarket)
Optional fields:
- fine_print (str)
- context (str)  # any extra background you want baked into the prompt

Run:
    python polymarket_benchmark.py
or from custom_forecast:
    python custom_forecast.py --benchmark
"""

import asyncio
import datetime
import json
import os
import csv
import re
from typing import Any, Dict, List, Optional

from forecaster import binary_forecast
from model_config import get_model_config
from logging_utils import RunLogger, get_current_logger, set_current_logger


POLYMARKET_QUESTIONS: List[Dict[str, Any]] = [
    {
        "title": "Will Jose Antonio Kast win the 2025 Chilean presidential election?",
        "description": (
            "Market tracks whether Jose Antonio Kast is ultimately declared the winner "
            "of the Chilean presidential election scheduled for November 16, 2025, "
            "including any required second round."
        ),
        "resolution_criteria": (
            "Resolves YES if Jose Antonio Kast is reported as the official winner by "
            "the Chilean Electoral Service (Servel). Resolves NO otherwise, including "
            "if the winner is unknown by 2026-05-31 23:59 ET."
        ),
        "fine_print": (
            "A consensus of credible reporting is acceptable unless ambiguous, in which "
            "case Servel's official results take precedence. Includes any second-round "
            "vote if held."
        ),
        "market_probability": 0.97,
    },

    {
        "title": "Will NVIDIA be the world's largest company by market cap on December 31, 2025?",
        "description": (
            "Evaluates whether NVIDIA has the highest publicly reported global market "
            "capitalization at market close on 2025-12-31."
        ),
        "resolution_criteria": (
            "Resolves YES if NVIDIA is the largest by market cap as of market close "
            "on December 31, 2025, based on a consensus of credible reporting."
        ),
        "fine_print": (
            "If reporting is ambiguous, use official exchange-reported market caps. "
            "Comparisons must be made using the same date's closing data."
        ),
        "market_probability": 0.88,
    },

    {
        "title": "Will the Federal Reserve cut the target federal funds upper bound by 25 bps at the December 2025 meeting?",
        "description": (
            "Tracks whether the FOMC lowers the upper bound of the target federal funds "
            "rate by exactly 25 basis points relative to its level before the December "
            "9-10, 2025 meeting."
        ),
        "resolution_criteria": (
            "Resolves YES if the FOMC statement for the December 2025 meeting indicates "
            "a 25 bps decrease. Any non-25 bps move is resolved per Polymarket rounding rules: "
            "changes are rounded up to the nearest 25 bps bracket."
        ),
        "fine_print": (
            "If no statement is released by the end of the next scheduled meeting, resolves to "
            "NO CHANGE and therefore NO for this contract. Source: Federal Reserve official releases."
        ),
        "market_probability": 0.94,
    },

    {
        "title": "Will TIME's 2025 Person of the Year be Artificial Intelligence?",
        "description": (
            "Evaluates whether 'Artificial Intelligence' is explicitly named as TIME's "
            "2025 Person of the Year on the official cover."
        ),
        "resolution_criteria": (
            "Resolves YES if 'Artificial Intelligence' is the Person of the Year, either "
            "alone or jointly with other entities not listed in this market. If multiple "
            "listed entities receive the title, ordering rules apply."
        ),
        "fine_print": (
            "Resolution is based only on TIME's official cover. If no announcement is made "
            "by 2026-01-31 23:59 ET, the market resolves NO."
        ),
        "market_probability": 0.42,
    },
]



def _as_question(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a benchmark entry into the binary forecast schema."""
    return {
        "title": entry["title"],
        "description": entry.get("description", ""),
        "resolution_criteria": entry.get("resolution_criteria", ""),
        "fine_print": entry.get("fine_print", ""),
        "type": "binary",
    }


def _brier(pred: float, truth: float) -> float:
    return (pred - truth) ** 2


def _mae(pred: float, truth: float) -> float:
    return abs(pred - truth)


def _slugify(text: str) -> str:
    """Make a filesystem-friendly slug."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    # Keep filenames short for Windows path limits
    if len(slug) > 50:
        slug = slug[:50].rstrip("-")
    return slug or "question"


async def run_polymarket_benchmark(questions: Optional[List[Dict[str, Any]]] = None) -> str:
    """
    Run the binary pipeline over the provided Polymarket questions and score against market odds.

    Returns:
        Path to the saved benchmark folder.
    """
    questions = questions or POLYMARKET_QUESTIONS
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    output_root = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "custom_forecasts",
            f"polymarket_benchmark_{timestamp}",
        )
    )
    os.makedirs(output_root, exist_ok=True)
    questions_dir = os.path.join(output_root, "questions")
    raw_dir = os.path.join(output_root, "raw_outputs")
    os.makedirs(questions_dir, exist_ok=True)
    os.makedirs(raw_dir, exist_ok=True)

    results = []
    forecaster_rows: List[Dict[str, Any]] = []
    error_entries: List[str] = []
    model_map = get_model_config()
    run_logs: List[str] = []
    logger = RunLogger(buffer=run_logs, echo_errors=True, echo_probabilities=True, echo_info=False)
    previous_logger = get_current_logger()
    set_current_logger(logger)
    forecaster_metrics = {i: {"brier_sum": 0.0, "mae_sum": 0.0, "n": 0} for i in range(1, 6)}

    try:
        # Helper to write small text files
        def write_text(path: str, content: str) -> None:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

        header_lines = [
            "=" * 70,
            "POLYMARKET BENCHMARK",
            f"Created: {timestamp}",
            f"Questions: {len(questions)}",
            "Model config (forecasters 1-5):",
            *(f"  Forecaster {i}: {model_map.get(f'forecaster_{i}', 'unknown')}" for i in range(1, 6)),
            "=" * 70,
            "",
        ]

        for idx, entry in enumerate(questions, start=1):
            question = _as_question(entry)
            market_prob = float(entry.get("market_probability", 0.5))

            # Capture logs for this question only
            local_logs: List[str] = []
            error_count_before = len(logger.error_lines())

            def log(line: str, level: str = "info"):
                local_logs.append(line)
                logger.log(line, level=level)

            log(f"--- Q{idx}: {question['title']} ---")
            log(f"Market probability: {market_prob:.3f}")
            log(f"Resolution: {question['resolution_criteria']}")
            log(f"Context: {question['description']}")

            try:
                forecast, comment, details = await binary_forecast(
                    question, write=log, return_details=True
                )
            except Exception as e:
                err_msg = f"[ERROR] Benchmark forecast failed: {e}"
                log(err_msg, level="error")
                details = {"probabilities_pct": [], "weights": [], "raw_outputs": [], "errors": [str(e)]}
                comment = err_msg
                forecast = None
            if forecast and forecast > 1:
                forecast = forecast / 100.0

            per_forecaster_pct = details.get("probabilities_pct", [])
            per_forecaster_decimal = [
                (p / 100.0) if p is not None else None for p in per_forecaster_pct
            ]
            weights = details.get("weights", [])
            raw_outputs = details.get("raw_outputs", [])
            question_errors = details.get("errors", [])

            pred = float(forecast) if forecast is not None else 0.0
            brier = _brier(pred, market_prob)
            mae = _mae(pred, market_prob)
            status = "ok"
            contamination = False
            new_errors = logger.error_lines()[error_count_before:]
            if new_errors:
                question_errors.extend(new_errors)
            if any(p is None for p in per_forecaster_decimal):
                status = "incomplete"
                contamination = True
            if question_errors or forecast is None:
                status = "error"
                contamination = True

            results.append(
                {
                    "title": question["title"],
                    "forecast": pred,
                    "market": market_prob,
                    "brier": brier,
                    "mae": mae,
                    "per_forecaster": per_forecaster_decimal,
                    "weights": weights,
                    "status": status,
                    "contamination": contamination,
                }
            )

            # Collect per-forecaster rows for CSV
            for i, prob in enumerate(per_forecaster_decimal):
                forecaster_rows.append(
                    {
                        "question_idx": idx,
                        "question": question["title"],
                        "forecaster": i + 1,
                        "model": model_map.get(f"forecaster_{i+1}", "unknown"),
                        "probability": prob,
                        "weight": weights[i] if i < len(weights) else None,
                        "status": status,
                        "contamination": contamination,
                    }
                )
                if prob is not None:
                    forecaster_metrics[i + 1]["brier_sum"] += _brier(prob, market_prob)
                    forecaster_metrics[i + 1]["mae_sum"] += _mae(prob, market_prob)
                    forecaster_metrics[i + 1]["n"] += 1

            if status != "ok" or contamination:
                error_entries.append(
                    f"Q{idx} ({question['title']}): status={status}, contamination={contamination}"
                )
            if question_errors:
                for err in question_errors:
                    error_entries.append(f"Q{idx}: {err}")

            # Write per-question file
            slug = _slugify(question["title"])
            question_path = os.path.join(questions_dir, f"q{idx}_{slug}.md")
            per_q_lines = [
                f"# Q{idx}: {question['title']}",
                "",
                f"- Market probability: {market_prob:.3f}",
                f"- Model forecast: {pred:.3f}",
                f"- Brier: {brier:.4f}",
                f"- MAE: {mae:.4f}",
                f"- Status: {status}",
                f"- Contamination: {contamination}",
                "",
                "## Per-forecaster probabilities",
            ]
            for i, prob in enumerate(per_forecaster_decimal):
                wt = weights[i] if i < len(weights) else "?"
                model = model_map.get(f"forecaster_{i+1}", "unknown")
                per_q_lines.append(f"- Forecaster {i+1} [{model}]: {prob if prob is not None else 'N/A'} (weight={wt})")
            per_q_lines.append("")
            per_q_lines.append("## Resolution")
            per_q_lines.append(question["resolution_criteria"])
            per_q_lines.append("")
            per_q_lines.append("## Context")
            per_q_lines.append(question["description"])
            per_q_lines.append("")
            per_q_lines.append(f"Full raw outputs/logs: raw_outputs/q{idx}_{slug}_raw.txt")
            per_q_lines.append("")
            write_text(question_path, "\n".join(per_q_lines))

            # Write verbose raw outputs separately to keep question files short
            raw_lines = [
                f"# Q{idx}: {question['title']} - Raw Outputs",
                "",
                "## Pipeline log",
                "```\n" + "\n".join(local_logs) + "\n```",
                "",
                "## Forecaster raw outputs",
            ]
            for i, output in enumerate(raw_outputs):
                model = model_map.get(f"forecaster_{i+1}", "unknown")
                raw_lines.extend(
                    [
                        f"### Forecaster {i+1} [{model}]",
                        "```\n" + str(output) + "\n```",
                        "",
                    ]
                )
            raw_lines.extend(
                [
                    "## Full comment",
                    comment,
                    "",
                ]
            )
            raw_path = os.path.join(raw_dir, f"q{idx}_{slug}_raw.txt")
            write_text(raw_path, "\n".join(raw_lines))

        # Overall summaries
        avg_brier = sum(item["brier"] for item in results) / len(results)
        avg_mae = sum(item["mae"] for item in results) / len(results)

        # Aggregate per-forecaster query counts from logs
        forecaster_query_counts = {}
        for _, msg in logger.entries:
            match = re.search(r"Forecaster\s+(\d+):\s+Query=", msg)
            if match:
                fid = int(match.group(1))
                forecaster_query_counts[f"forecaster_{fid}"] = forecaster_query_counts.get(f"forecaster_{fid}", 0) + 1

        summary_json = {
            "run": {
                "timestamp": timestamp,
                "questions": len(results),
                "avg_brier": round(avg_brier, 4),
                "avg_mae": round(avg_mae, 4),
                "models": {f"forecaster_{i}": model_map.get(f"forecaster_{i}", "unknown") for i in range(1, 6)},
                "search_api_counts": logger.get_search_counts(),
                "serper_urls": {
                    "attempted": logger.get_serper_url_stats()[0],
                    "success": logger.get_serper_url_stats()[1],
                },
            },
            "questions": [
                {
                    "title": item["title"],
                    "forecast": round(item["forecast"], 4),
                    "market": round(item["market"], 4),
                    "brier": round(item["brier"], 4),
                    "mae": round(item["mae"], 4),
                    "per_forecaster": item["per_forecaster"],
                    "weights": item["weights"],
                    "status": item["status"],
                    "contamination": item["contamination"],
                }
                for item in results
            ],
            "per_forecaster": {
                f"forecaster_{i}": {
                    "model": model_map.get(f"forecaster_{i}", "unknown"),
                    "avg_brier": round(vals["brier_sum"] / vals["n"], 4) if vals["n"] else None,
                    "avg_mae": round(vals["mae_sum"] / vals["n"], 4) if vals["n"] else None,
                    "n": vals["n"],
                }
                for i, vals in forecaster_metrics.items()
            },
            "forecaster_query_counts": forecaster_query_counts,
        }
        write_text(os.path.join(output_root, "summary.json"), json.dumps(summary_json, indent=2))

        # Write compact summary.txt
        summary_lines = header_lines.copy()
        summary_lines.append("SCOREBOARD")
        for item in results:
            summary_lines.append(
                f"- {item['title']} | forecast={item['forecast']:.3f} | market={item['market']:.3f} | "
                f"Brier={item['brier']:.4f} | MAE={item['mae']:.4f} | status={item['status']} | "
                f"f1={item['per_forecaster'][0] if item['per_forecaster'][0] is not None else 'N/A'} "
                f"f2={item['per_forecaster'][1] if item['per_forecaster'][1] is not None else 'N/A'} "
                f"f3={item['per_forecaster'][2] if item['per_forecaster'][2] is not None else 'N/A'} "
                f"f4={item['per_forecaster'][3] if item['per_forecaster'][3] is not None else 'N/A'} "
                f"f5={item['per_forecaster'][4] if item['per_forecaster'][4] is not None else 'N/A'}"
            )
        summary_lines.extend(
            [
                "",
                f"Average Brier: {avg_brier:.4f}",
                f"Average MAE: {avg_mae:.4f}",
                "",
                "Search counts:",
                *(
                    f"- {api}: {count}"
                    for api, count in (logger.get_search_counts() or {"none": 0}).items()
                ),
                "",
                "Serper URL success rate:",
                f"- attempted: {logger.get_serper_url_stats()[0]}",
                f"- success: {logger.get_serper_url_stats()[1]}",
                f"- success_pct: {((logger.get_serper_url_stats()[1] / logger.get_serper_url_stats()[0]) * 100):.1f}%" if logger.get_serper_url_stats()[0] else "- success_pct: N/A",
                "",
                "Forecaster query counts:",
                *(
                    f"- Forecaster {fid}: {forecaster_query_counts.get(f'forecaster_{fid}', 0)}"
                    for fid in range(1, 6)
                ),
                "",
                "Per-forecaster averages:",
                *(
                    f"- Forecaster {i} [{model_map.get(f'forecaster_{i}', 'unknown')}]: "
                    f"Brier={forecaster_metrics[i]['brier_sum'] / forecaster_metrics[i]['n']:.4f} "
                    f"MAE={forecaster_metrics[i]['mae_sum'] / forecaster_metrics[i]['n']:.4f} "
                    f"(n={forecaster_metrics[i]['n']})"
                    if forecaster_metrics[i]["n"] else
                    f"- Forecaster {i} [{model_map.get(f'forecaster_{i}', 'unknown')}]: no valid predictions"
                    for i in range(1, 6)
                ),
                "",
                "Files:",
                f"- summary.json: machine-readable scores",
                f"- questions/: per-question details & raw outputs",
                "- scores_by_forecaster.csv: per-forecaster probabilities",
                "- errors.txt: any issues or contamination flags",
            ]
        )
        write_text(os.path.join(output_root, "summary.txt"), "\n".join(summary_lines))

        # Write errors (if any)
        if not error_entries:
            error_entries.append("No errors or contamination detected.")
        write_text(os.path.join(output_root, "errors.txt"), "\n".join(error_entries))

        # Per-forecaster CSV
        csv_path = os.path.join(output_root, "scores_by_forecaster.csv")
        with open(csv_path, "w", encoding="utf-8", newline="") as csvfile:
            fieldnames = ["question_idx", "question", "forecaster", "model", "probability", "weight", "status", "contamination"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in forecaster_rows:
                writer.writerow(row)

        # Run log
        write_text(os.path.join(output_root, "run.log"), "\n".join(logger.buffer))

        logger.info(f"Benchmark artifacts written to: {output_root}")
        return output_root
    finally:
        set_current_logger(previous_logger)


if __name__ == "__main__":
    asyncio.run(run_polymarket_benchmark())
