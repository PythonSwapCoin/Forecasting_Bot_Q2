"""
Replay/record helpers for offline runs and smoke tests.

When ENABLE_REPLAY_MODE=1 is set (or REPLAY_RECORD=1), network calls are
replaced with fixtures stored under REPLAY_FIXTURES_DIR (default:
``tests/fixtures/replay``). Two fixture files are used:
  - ``llm.json``: map of replay_key -> {"response": "...", "meta": {...}}
  - ``search.json``: map of replay_key -> ResearchResult dict

If REPLAY_RECORD=1 is set, missing keys are recorded after the real call
completes. If replay is enabled without record, missing keys raise to avoid
silent live calls during offline test runs.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from evidence import ResearchResult


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class ReplayConfig:
    enabled: bool
    record: bool
    fixtures_dir: Path
    strict: bool = True  # error on missing when enabled+not recording

    @classmethod
    def from_env(cls) -> "ReplayConfig":
        enabled = _env_bool("ENABLE_REPLAY_MODE", False) or _env_bool("REPLAY_RECORD", False)
        record = _env_bool("REPLAY_RECORD", False)
        fixtures_dir = Path(os.getenv("REPLAY_FIXTURES_DIR", "tests/fixtures/replay"))
        strict = not record
        return cls(enabled=enabled, record=record, fixtures_dir=fixtures_dir, strict=strict)


def _slugify(text: str) -> str:
    safe = "".join(c.lower() if c.isalnum() else "-" for c in text).strip("-")
    if len(safe) > 80:
        safe = safe[:80].rstrip("-")
    return safe or "question"


def make_replay_key(question: Dict[str, Any], suffix: str) -> str:
    slug = question.get("slug") or _slugify(question.get("title", "question"))
    return f"{slug}:{suffix}"


class ReplayStore:
    def __init__(self, config: ReplayConfig):
        self.config = config
        self.fixtures_dir = config.fixtures_dir
        self.llm_path = self.fixtures_dir / "llm.json"
        self.search_path = self.fixtures_dir / "search.json"
        self._llm_cache: Dict[str, Any] = {}
        self._search_cache: Dict[str, Any] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self.fixtures_dir.mkdir(parents=True, exist_ok=True)
        if self.llm_path.exists():
            try:
                self._llm_cache = json.loads(self.llm_path.read_text(encoding="utf-8"))
            except Exception:
                self._llm_cache = {}
        if self.search_path.exists():
            try:
                self._search_cache = json.loads(self.search_path.read_text(encoding="utf-8"))
            except Exception:
                self._search_cache = {}
        self._loaded = True

    def llm_response(self, key: str) -> Optional[str]:
        self._ensure_loaded()
        item = self._llm_cache.get(key)
        if isinstance(item, dict):
            return item.get("response")
        if isinstance(item, str):
            return item
        return None

    def search_result(self, key: str) -> Optional[ResearchResult]:
        self._ensure_loaded()
        data = self._search_cache.get(key)
        if data is None:
            return None
        if isinstance(data, ResearchResult):
            return data
        try:
            return ResearchResult.from_dict(data)
        except Exception:
            return None

    def record_llm(self, key: str, response: str, meta: Optional[Dict[str, Any]] = None) -> None:
        self._ensure_loaded()
        payload: Dict[str, Any] = {"response": response}
        if meta:
            payload["meta"] = meta
        self._llm_cache[key] = payload
        self.llm_path.write_text(json.dumps(self._llm_cache, indent=2), encoding="utf-8")

    def record_search(self, key: str, result: ResearchResult) -> None:
        self._ensure_loaded()
        self._search_cache[key] = result.to_dict()
        self.search_path.write_text(json.dumps(self._search_cache, indent=2), encoding="utf-8")


_store: Optional[ReplayStore] = None


def get_store() -> ReplayStore:
    global _store
    if _store is None:
        _store = ReplayStore(ReplayConfig.from_env())
    return _store


def replay_enabled() -> bool:
    return get_store().config.enabled


def replay_strict() -> bool:
    store = get_store()
    return store.config.enabled and store.config.strict and not store.config.record


def default_llm_key(prompt: str, model: str) -> str:
    digest = hashlib.sha256((model + "::" + prompt).encode("utf-8")).hexdigest()[:12]
    return f"llm:{model}:{digest}"


async def maybe_replay_llm(
    replay_key: Optional[str],
    prompt: str,
    model: str,
    caller: Callable[[], Any],
) -> str:
    """
    Return replayed LLM response when enabled; otherwise execute caller().

    If recording, caller() will be executed and stored under replay_key (or
    prompt hash).
    """
    store = get_store()
    key = replay_key or default_llm_key(prompt, model)

    if store.config.enabled:
        cached = store.llm_response(key)
        if cached is not None:
            return cached
        if store.config.record:
            result = await caller()
            store.record_llm(key, result, meta={"model": model, "prompt_hash": default_llm_key(prompt, model)})
            return result
        if store.config.strict:
            raise RuntimeError(f"Replay enabled but no fixture for key '{key}'")

    # Replay disabled; call live
    result = await caller()
    return result


def maybe_replay_search(replay_key: Optional[str]) -> Optional[ResearchResult]:
    store = get_store()
    if not store.config.enabled:
        return None
    if not replay_key:
        if store.config.strict:
            raise RuntimeError("Replay search requested without a key")
        return None
    cached = store.search_result(replay_key)
    if cached is None and store.config.strict and not store.config.record:
        raise RuntimeError(f"Replay enabled but no search fixture for key '{replay_key}'")
    return cached


def record_search_result(replay_key: Optional[str], result: ResearchResult) -> None:
    store = get_store()
    if store.config.enabled and store.config.record and replay_key:
        store.record_search(replay_key, result)

