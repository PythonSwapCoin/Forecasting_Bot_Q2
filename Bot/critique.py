"""
Critique/debate scaffolding (Phase 7).
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from llm_calls import call_openrouter_gpt
from prompts import CRITIQUE_PROMPT


async def run_binary_critique(
    forecast: float,
    rationale: str,
    evidence_summary: str,
    model: str = "openai/gpt-4o-mini",
) -> Dict[str, Any]:
    """
    Run a lightweight critique pass. Returns parsed critique dict.
    """
    payload = CRITIQUE_PROMPT.format(
        probability=forecast,
        rationale=rationale[:3000],
        evidence=evidence_summary[:3000],
    )
    try:
        response = await call_openrouter_gpt(payload, model=model)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}
    try:
        data = json.loads(response)
        return data if isinstance(data, dict) else {"raw": response}
    except Exception:
        return {"raw": response}
