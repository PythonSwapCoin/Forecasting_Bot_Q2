import asyncio
import os

from smoke_suite import SMOKE_SUITE_PATH, run_smoke_suite


def test_smoke_suite_replay(monkeypatch):
    monkeypatch.setenv("ENABLE_REPLAY_MODE", "1")
    monkeypatch.setenv("REPLAY_FIXTURES_DIR", "tests/fixtures/replay")
    summary = asyncio.run(run_smoke_suite(SMOKE_SUITE_PATH))
    assert summary["passed"] is True
    assert len(summary["results"]) == 3
