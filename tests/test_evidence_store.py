import os
from pathlib import Path

from evidence import ResearchResult, EvidenceItem
from evidence_store import persist_research_result


def test_persist_research_result_writes_files(tmp_path, monkeypatch):
    monkeypatch.setenv("ENABLE_EVIDENCE_LAKE", "1")
    monkeypatch.setenv("EVIDENCE_LAKE_DIR", str(tmp_path))
    monkeypatch.delenv("EVIDENCE_RUN_ID", raising=False)

    result = ResearchResult(
        formatted="<Summary>example</Summary>",
        evidence=[EvidenceItem(provider="test", query="q1", url="http://example.com")],
    )
    persist_research_result("q-slug", result)

    run_dirs = list(tmp_path.iterdir())
    assert run_dirs, "run directory not created"
    run_dir = run_dirs[0]
    per_question = run_dir / "q-slug.json"
    assert per_question.exists(), "question file missing"

    index_path = run_dir / "index.jsonl"
    assert index_path.exists(), "index file missing"
    index_lines = index_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(index_lines) == 1
    assert "q-slug" in index_lines[0]


def test_persist_research_result_sqlite(tmp_path, monkeypatch):
    monkeypatch.setenv("ENABLE_EVIDENCE_LAKE", "1")
    monkeypatch.setenv("EVIDENCE_LAKE_BACKEND", "sqlite")
    sqlite_path = tmp_path / "evidence.db"
    monkeypatch.setenv("EVIDENCE_SQLITE_PATH", str(sqlite_path))

    result = ResearchResult(
        formatted="<Summary>example</Summary>",
        evidence=[
            EvidenceItem(provider="test", query="q1", url="http://example.com", content_hash="abc123"),
            EvidenceItem(provider="test", query="q1", url="http://example.com/dup", content_hash="abc123"),
        ],
    )
    persist_research_result("q-sql", result)

    assert sqlite_path.exists(), "sqlite file missing"
    import sqlite3

    conn = sqlite3.connect(sqlite_path)
    rows = conn.execute("SELECT COUNT(*) FROM evidence_items").fetchone()[0]
    assert rows == 1, "deduplication by content_hash failed"
    conn.close()
