"""
Diagnostics for API keys and provider health.

Usage:
    python diagnostics.py
    python custom_forecast.py --diagnostics
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from typing import Dict, Any

import aiohttp

from research_config import get_research_provider_status


async def _check_openrouter(session: aiohttp.ClientSession, api_key: str) -> str:
    url = "https://openrouter.ai/api/v1/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        async with session.get(url, headers=headers, timeout=20) as resp:
            if resp.status == 200:
                return "ok"
            text = await resp.text()
            return f"status {resp.status}: {text[:120]}"
    except Exception as e:
        return f"error: {e}"


async def _check_serper(session: aiohttp.ClientSession, api_key: str) -> str:
    # Avoid burning a quota-heavy call; use a lightweight metadata request.
    url = "https://google.serper.dev/search"
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    payload = {"q": "healthcheck", "num": 1}
    try:
        async with session.post(url, headers=headers, json=payload, timeout=20) as resp:
            if resp.status == 200:
                return "ok"
            text = await resp.text()
            return f"status {resp.status}: {text[:120]}"
    except Exception as e:
        return f"error: {e}"


async def run_diagnostics(live_checks: bool = False) -> Dict[str, Any]:
    statuses = get_research_provider_status()
    results: Dict[str, Any] = {"providers": statuses, "live_checks": {}}

    if not live_checks:
        return results

    async with aiohttp.ClientSession() as session:
        if statuses.get("openrouter", {}).get("has_key"):
            api_key = os.getenv("OPENROUTER_API_KEY", "")
            results["live_checks"]["openrouter"] = await _check_openrouter(session, api_key=api_key)
        if statuses.get("serper", {}).get("enabled") and statuses["serper"].get("has_key"):
            serper_key = os.getenv("SERPER_KEY", "")
            results["live_checks"]["serper"] = await _check_serper(session, api_key=serper_key)

    return results


def print_results(results: Dict[str, Any]) -> None:
    print("\nDiagnostics summary")
    print("=" * 40)
    for name, info in results.get("providers", {}).items():
        status = "enabled" if info.get("enabled") else "disabled"
        reason = info.get("reason") or ""
        has_key = "yes" if info.get("has_key") else "no"
        print(f"{name:12s} status={status:8s} key={has_key:3s} {reason}")

    live = results.get("live_checks", {})
    if live:
        print("\nLive checks")
        for name, outcome in live.items():
            print(f"{name:12s} -> {outcome}")
    print("")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run provider diagnostics.")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Perform lightweight live calls (uses minimal API quota).",
    )
    args = parser.parse_args()
    results = asyncio.run(run_diagnostics(live_checks=args.live))
    print_results(results)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
