"""
Lightweight schemas for structured research outputs.

These are intentionally simple so they can be serialized to/from replay fixtures
and stored alongside run metadata. Fields are optional; providers should fill in
what they know rather than aiming for completeness.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class EvidenceItem:
    provider: str
    query: str
    query_intent: Optional[str] = None  # historical/current/fact_check/etc
    url: Optional[str] = None
    title: Optional[str] = None
    snippet: Optional[str] = None
    published_at: Optional[str] = None
    retrieved_at: Optional[str] = None
    content_hash: Optional[str] = None
    publisher: Optional[str] = None
    language: Optional[str] = None
    raw_html_path: Optional[str] = None
    extracted_text_path: Optional[str] = None
    quality_score: Optional[float] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        # Drop empty fields to keep fixtures small
        return {k: v for k, v in data.items() if v not in (None, [], {}, "")}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidenceItem":
        return cls(
            provider=data.get("provider", ""),
            query=data.get("query", ""),
            query_intent=data.get("query_intent"),
            url=data.get("url"),
            title=data.get("title"),
            snippet=data.get("snippet"),
            published_at=data.get("published_at"),
            retrieved_at=data.get("retrieved_at"),
            content_hash=data.get("content_hash"),
            publisher=data.get("publisher"),
            language=data.get("language"),
            raw_html_path=data.get("raw_html_path"),
            extracted_text_path=data.get("extracted_text_path"),
            quality_score=data.get("quality_score"),
            tags=list(data.get("tags", []) or []),
            metadata=dict(data.get("metadata", {}) or {}),
        )


@dataclass
class ResearchResult:
    """Container for structured research + prompt-ready text."""

    formatted: str
    evidence: List[EvidenceItem] = field(default_factory=list)
    report: Dict[str, Any] = field(default_factory=dict)
    queries: List[str] = field(default_factory=list)
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "formatted": self.formatted,
            "evidence": [e.to_dict() for e in self.evidence],
            "report": self.report,
            "queries": self.queries,
            "diagnostics": self.diagnostics,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResearchResult":
        return cls(
            formatted=data.get("formatted", ""),
            evidence=[EvidenceItem.from_dict(e) for e in data.get("evidence", [])],
            report=data.get("report", {}) or {},
            queries=list(data.get("queries", []) or []),
            diagnostics=data.get("diagnostics", {}) or {},
        )

    @property
    def has_evidence(self) -> bool:
        return bool(self.evidence) or bool(self.formatted.strip())

    def __str__(self) -> str:
        return self.formatted
