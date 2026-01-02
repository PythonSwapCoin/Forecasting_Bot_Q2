"""
Utilities to compute lightweight retrieval KPIs from structured evidence.
"""

from __future__ import annotations

import datetime
import hashlib
from collections import Counter
from typing import Dict, List
from urllib.parse import urlparse

from evidence import EvidenceItem

HIGH_TRUST_SUFFIXES = (".gov", ".mil", ".int")
MID_TRUST_SUFFIXES = (".edu", ".org")
LOW_TRUST_HINTS = ("blogspot", "substack", "medium.com")


def canonicalize_url(url: str | None) -> str:
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower().strip("/")
        path = (parsed.path or "").rstrip("/")
        return f"{host}{path}"
    except Exception:
        return url or ""


def _domain(url: str | None) -> str:
    canon = canonicalize_url(url)
    return canon.split("/")[0] if canon else ""


def _domain_reputation(domain: str) -> float:
    if not domain:
        return 0.2
    if domain.endswith(HIGH_TRUST_SUFFIXES):
        return 1.0
    if domain.endswith(MID_TRUST_SUFFIXES):
        return 0.8
    if any(hint in domain for hint in LOW_TRUST_HINTS):
        return 0.3
    return 0.6


def compute_quality_score(item: EvidenceItem) -> float:
    base = _domain_reputation(_domain(item.url))
    if item.published_at:
        try:
            published = datetime.datetime.fromisoformat(item.published_at.replace("Z", "+00:00"))
            age_days = (datetime.datetime.now(datetime.timezone.utc) - published).days
            if age_days < 45:
                base += 0.1
        except Exception:
            pass
    return round(max(0.0, min(1.0, base)), 3)


def compute_retrieval_kpis(evidence: List[EvidenceItem]) -> Dict[str, object]:
    """
    Return a compact KPI dictionary for a set of evidence items.
    """
    if not evidence:
        return {
            "total_items": 0,
            "unique_urls": 0,
            "unique_domains": 0,
            "duplicates": 0,
            "recent_items": 0,
            "domain_counts": {},
            "avg_quality": 0.0,
            "timeliness_span_days": None,
            "contradictions": [],
        }

    urls = [canonicalize_url(e.url) for e in evidence if e.url]
    url_domains = [_domain(u) for u in urls if u]
    url_counter = Counter(url_domains)
    hashes = [e.content_hash for e in evidence if e.content_hash]
    duplicates = 0
    if hashes:
        duplicates = len(hashes) - len(set(hashes))
    elif urls:
        duplicates = len(urls) - len(set(urls))

    recent_items = sum(1 for e in evidence if e.published_at)
    published_dates = []
    for e in evidence:
        if e.published_at:
            try:
                published_dates.append(datetime.datetime.fromisoformat(e.published_at.replace("Z", "+00:00")))
            except Exception:
                continue
    span = None
    if len(published_dates) >= 2:
        span = (max(published_dates) - min(published_dates)).days

    # Quality scoring
    quality_scores = []
    for e in evidence:
        score = e.quality_score if e.quality_score is not None else compute_quality_score(e)
        e.quality_score = score
        quality_scores.append(score)

    return {
        "total_items": len(evidence),
        "unique_urls": len(set(urls)),
        "unique_domains": len(set(url_domains)),
        "duplicates": max(0, duplicates),
        "recent_items": recent_items,
        "domain_counts": dict(url_counter),
        "avg_quality": round(float(sum(quality_scores) / len(quality_scores)), 3) if quality_scores else 0.0,
        "timeliness_span_days": span,
        "contradictions": [],  # placeholder until claim checking exists
    }


def hash_snippet(snippet: str | None) -> str | None:
    """Compute a stable content hash for deduplication."""
    if not snippet:
        return None
    digest = hashlib.sha256(snippet.encode("utf-8", errors="ignore")).hexdigest()
    return digest
