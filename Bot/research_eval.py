"""
Lightweight retrieval evaluation for research reports.

Usage:
  python Bot/research_eval.py --report evidence_lake/<run>/research_reports/<slug>__current.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List


def _load_dataset(path: Path) -> Dict[str, dict]:
    lookup: Dict[str, dict] = {}
    if not path.exists():
        return lookup
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            lookup[row["id"]] = row
    return lookup


def _load_report(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def score_retrieval(report: dict, key_facts: List[str]) -> Dict[str, object]:
    corpus: List[str] = []
    for ev in report.get("evidence", []):
        if isinstance(ev, dict):
            corpus.append(ev.get("snippet") or "")
            corpus.append(ev.get("title") or "")
    corpus.append(report.get("formatted", ""))
    lower_corpus = [c.lower() for c in corpus if c]
    hits = []
    for fact in key_facts:
        fact_l = fact.lower()
        if any(fact_l in c for c in lower_corpus):
            hits.append(fact)
    recall = len(hits) / len(key_facts) if key_facts else 0.0
    return {"found": hits, "missing": [f for f in key_facts if f not in hits], "recall": recall}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=str, default="benchmarks/research_eval.jsonl")
    parser.add_argument("--report", type=str, required=True, help="Path to research_report JSON")
    parser.add_argument("--question-id", type=str, help="Question id to lookup key facts")
    args = parser.parse_args()

    dataset = _load_dataset(Path(args.dataset))
    report = _load_report(Path(args.report))
    question_id = args.question_id or report.get("question_slug") or "unknown"
    key_facts = dataset.get(question_id, {}).get("key_facts", [])
    scores = score_retrieval(report, key_facts)
    output = {
        "question_id": question_id,
        "report": args.report,
        "dataset": args.dataset,
        "key_facts": key_facts,
        "scores": scores,
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
