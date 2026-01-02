import asyncio
from pathlib import Path

from experiment_runner import run_experiments


def test_experiment_runner_replay(monkeypatch):
    monkeypatch.setenv("ENABLE_REPLAY_MODE", "1")
    monkeypatch.setenv("REPLAY_FIXTURES_DIR", "tests/fixtures/replay")
    matrix = [
        {"name": "replay", "env": {"ENABLE_REPLAY_MODE": "1", "REPLAY_FIXTURES_DIR": "tests/fixtures/replay"}}
    ]
    summary = asyncio.run(run_experiments(matrix, Path("benchmarks/suites/smoke.jsonl")))
    assert summary["variants"][0]["passed"] is True
