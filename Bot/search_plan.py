"""
Lightweight question formalization and search plan builder.

This is deterministic (no model calls) and is used to:
- generate fallback queries when LLMs do not emit search plans
- record what we intended to look for (for audit + research_report)
"""

from __future__ import annotations

import re
from typing import Dict, List, Set

STOPWORDS: Set[str] = {
    "the",
    "will",
    "of",
    "in",
    "to",
    "and",
    "a",
    "an",
    "by",
    "for",
    "on",
    "at",
    "is",
    "are",
    "be",
    "with",
    "that",
}


def _extract_entities(text: str) -> List[str]:
    tokens = re.findall(r"[A-Z][A-Za-z0-9&'-]+", text or "")
    entities: List[str] = []
    for tok in tokens:
        t = tok.lower()
        if t in STOPWORDS:
            continue
        if t not in entities:
            entities.append(tok)
    return entities[:6]


def formalize_question(question: Dict[str, object]) -> Dict[str, object]:
    title = str(question.get("title", "")).strip()
    resolution = str(question.get("resolution_criteria", "")).strip()
    fine_print = str(question.get("fine_print", "") or "").strip()
    deadline = question.get("resolution_date") or question.get("evidence_cutoff")
    entities = _extract_entities(title + " " + resolution)
    unit = question.get("unit")
    return {
        "event": title,
        "deadline": deadline,
        "entities": entities,
        "fine_print": fine_print,
        "unit": unit,
    }


def build_search_plan(question: Dict[str, object]) -> Dict[str, object]:
    formal = formalize_question(question)
    title = formal["event"]
    deadline = formal.get("deadline")
    entities = formal.get("entities") or []
    base = title if title else "question"

    def _add_deadline(q: str) -> str:
        return f"{q} before {deadline}" if deadline else q

    historical_queries = [
        _add_deadline(f"historical trend of {base}"),
        _add_deadline(f"reference class statistics for {base}"),
    ]
    current_queries = [
        f"latest news about {base}",
        f"recent updates on {base}",
    ]
    counter_queries = [
        f"reasons {base} might NOT happen",
        f"risks to {base}",
    ]
    data_queries = [
        f"official data for {ent}" for ent in entities[:3]
    ]
    missing_fact_queries = [
        f"key uncertainties for {base}",
        f"{base} forecast assumptions",
    ]

    plan_queries = {
        "historical": historical_queries,
        "current": current_queries,
        "counter": counter_queries,
        "data": data_queries,
        "missing": missing_fact_queries,
    }

    all_queries: List[str] = []
    for qs in plan_queries.values():
        for q in qs:
            if q not in all_queries:
                all_queries.append(q)

    return {
        "formalization": formal,
        "historical_queries": historical_queries,
        "current_queries": current_queries,
        "counter_queries": counter_queries,
        "data_queries": data_queries,
        "missing_fact_queries": missing_fact_queries,
        "all_queries": all_queries,
    }
