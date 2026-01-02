"""
Minimal structured fact extraction from evidence snippets.

This is deterministic and intended for replay-safe enrichment, not full IE.
"""

from __future__ import annotations

import re
from typing import Dict, List

from evidence import EvidenceItem

NUMBER_PATTERN = re.compile(r"(-?\d+(?:\.\d+)?)(?:\s*(percent|%|million|billion|trillion|k|m|bn|tn)?)", re.IGNORECASE)
YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")


def extract_fact_candidates(evidence_items: List[EvidenceItem], max_facts: int = 25) -> List[Dict[str, object]]:
    facts: List[Dict[str, object]] = []
    for item in evidence_items:
        snippet = item.snippet or ""
        for match in NUMBER_PATTERN.finditer(snippet):
            val_text, unit = match.groups()
            facts.append(
                {
                    "entity": item.title or item.query,
                    "value_text": val_text,
                    "unit": unit or "",
                    "source_url": item.url,
                    "provider": item.provider,
                    "published_at": item.published_at,
                }
            )
            if len(facts) >= max_facts:
                return facts
        for year in YEAR_PATTERN.findall(snippet):
            facts.append(
                {
                    "entity": item.title or item.query,
                    "value_text": "".join(year),
                    "unit": "year",
                    "source_url": item.url,
                    "provider": item.provider,
                    "published_at": item.published_at,
                }
            )
            if len(facts) >= max_facts:
                return facts
    return facts
