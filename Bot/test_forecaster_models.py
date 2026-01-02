#!/usr/bin/env python3
"""
Contract test for configurable forecaster models.

This hits live OpenRouter endpoints. It is skipped unless RUN_CONTRACT_TESTS is set.
"""

import asyncio
import os

import pytest
from dotenv import load_dotenv

from llm_calls import (
    call_forecaster_1,
    call_forecaster_2,
    call_forecaster_3,
    call_forecaster_4,
    call_forecaster_5,
)
from model_config import print_current_config

load_dotenv()


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("RUN_CONTRACT_TESTS", "0").strip().lower() not in {"1", "true", "yes", "on"},
    reason="Contract test skipped unless RUN_CONTRACT_TESTS=1",
)
async def test_forecaster_models():
    """Call each forecaster model with a trivial math prompt."""

    if not os.getenv("OPENROUTER_API_KEY"):
        pytest.skip("OPENROUTER_API_KEY not set")

    print_current_config()
    test_prompt = "What is 2+2? Answer with just the number."

    forecasters = [
        ("Forecaster 1", call_forecaster_1),
        ("Forecaster 2", call_forecaster_2),
        ("Forecaster 3", call_forecaster_3),
        ("Forecaster 4", call_forecaster_4),
        ("Forecaster 5", call_forecaster_5),
    ]

    results = []
    for name, forecaster_func in forecasters:
        try:
            response = await forecaster_func(test_prompt)
            results.append((name, True, response.strip()))
        except Exception as e:
            results.append((name, False, str(e)))

    successful = sum(1 for _, success, _ in results if success)
    assert successful == len(results), f"{len(results) - successful} forecasters failed: {results}"


if __name__ == "__main__":
    asyncio.run(test_forecaster_models())
