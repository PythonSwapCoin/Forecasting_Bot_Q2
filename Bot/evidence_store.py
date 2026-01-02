"""
Lightweight evidence lake writer (file-based).

Controlled via:
  - ENABLE_EVIDENCE_LAKE (bool, default false)
  - EVIDENCE_LAKE_DIR (path, default: evidence_lake/)
  - EVIDENCE_RUN_ID (optional stable ID; otherwise timestamped)
  - EVIDENCE_APPEND (bool; when false overwrite per question slug)
  - EVIDENCE_LAKE_BACKEND (files|sqlite, default files)
  - EVIDENCE_SQLITE_PATH (default: evidence_lake/evidence.db)
"""

from __future__ import annotations

import datetime
import json
import os
import sqlite3
from pathlib import Path
from typing import Optional

from evidence import ResearchResult


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _lake_dir() -> Path:
    return Path(os.getenv("EVIDENCE_LAKE_DIR", "evidence_lake"))


def _append_enabled() -> bool:
    return _env_bool("EVIDENCE_APPEND", True)


def _backend() -> str:
    raw = os.getenv("EVIDENCE_LAKE_BACKEND", "files").strip().lower()
    return raw if raw in {"files", "sqlite"} else "files"


def _sqlite_path() -> Path:
    return Path(os.getenv("EVIDENCE_SQLITE_PATH", _lake_dir() / "evidence.db"))


_RUN_ID: Optional[str] = None


def _run_id() -> str:
    global _RUN_ID
    if _RUN_ID:
        return _RUN_ID
    _RUN_ID = os.getenv("EVIDENCE_RUN_ID")
    if not _RUN_ID:
        _RUN_ID = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    return _RUN_ID


def _append_index(run_dir: Path, question_slug: str, result: ResearchResult) -> None:
    """Append evidence items to a simple index.jsonl for quick inspection."""
    index_path = run_dir / "index.jsonl"
    lines = []
    for item in result.evidence:
        payload = item.to_dict()
        payload.update(
            {
                "question_slug": question_slug,
                "run_id": _run_id(),
            }
        )
        lines.append(json.dumps(payload))
    if not lines:
        return
    mode = "a" if index_path.exists() else "w"
    with index_path.open(mode, encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")


def _ensure_sqlite_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS evidence_items (
            evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            question_slug TEXT NOT NULL,
            provider TEXT,
            query TEXT,
            query_intent TEXT,
            url TEXT,
            title TEXT,
            published_at TEXT,
            retrieved_at TEXT,
            content_hash TEXT,
            snippet TEXT,
            publisher TEXT,
            language TEXT,
            raw_html_path TEXT,
            extracted_text_path TEXT,
            metadata_json TEXT,
            UNIQUE(content_hash)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_evidence_run ON evidence_items(run_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_evidence_url ON evidence_items(url)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_evidence_hash ON evidence_items(content_hash)")
    conn.commit()


def _persist_sqlite(question_slug: str, result: ResearchResult) -> None:
    path = _sqlite_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    _ensure_sqlite_schema(conn)
    conn.execute(
        "INSERT OR IGNORE INTO runs(run_id, created_at) VALUES(?, ?)",
        (_run_id(), datetime.datetime.now(datetime.timezone.utc).isoformat()),
    )
    if not result.evidence:
        conn.close()
        return
    rows = []
    for item in result.evidence:
        rows.append(
            (
                _run_id(),
                question_slug,
                item.provider,
                item.query,
                item.query_intent,
                item.url,
                item.title,
                item.published_at,
                item.retrieved_at,
                item.content_hash,
                item.snippet,
                item.publisher,
                item.language,
                item.raw_html_path,
                item.extracted_text_path,
                json.dumps(item.metadata or {}),
            )
        )
    conn.executemany(
        """
        INSERT OR IGNORE INTO evidence_items(
            run_id, question_slug, provider, query, query_intent, url, title, published_at,
            retrieved_at, content_hash, snippet, publisher, language, raw_html_path,
            extracted_text_path, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    conn.close()


def persist_research_result(question_slug: str, result: ResearchResult) -> None:
    """Persist a ResearchResult to the evidence lake if enabled."""
    if not _env_bool("ENABLE_EVIDENCE_LAKE", False):
        return
    safe_slug = question_slug or "question"
    run_dir = _lake_dir() / _run_id()
    run_dir.mkdir(parents=True, exist_ok=True)
    if _backend() == "sqlite":
        _persist_sqlite(safe_slug, result)
    else:
        path = run_dir / f"{safe_slug}.json"
        payload = result.to_dict()
        payload["question_slug"] = safe_slug
        payload["saved_at_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if _append_enabled() and path.exists():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(existing, dict):
                    history = existing.get("history") or []
                    if isinstance(history, list):
                        history.append(payload)
                        existing["history"] = history
                        payload = existing
            except Exception:
                pass
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        _append_index(run_dir, safe_slug, result)


def persist_research_report(question_slug: str, bucket: str, report: dict) -> None:
    """Write a per-question research_report.json alongside evidence lake outputs."""
    if not _env_bool("ENABLE_EVIDENCE_LAKE", False):
        return
    safe_slug = question_slug or "question"
    run_dir = _lake_dir() / _run_id() / "research_reports"
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = dict(report or {})
    payload.update(
        {
            "question_slug": safe_slug,
            "bucket": bucket,
            "saved_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
    )
    path = run_dir / f"{safe_slug}__{bucket}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
