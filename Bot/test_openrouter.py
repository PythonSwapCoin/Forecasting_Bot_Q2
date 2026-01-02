#!/usr/bin/env python3
"""
Contract test for OpenRouter integration.

This hits live OpenRouter endpoints. It is skipped unless RUN_CONTRACT_TESTS is set.
"""

import asyncio
import os

import pytest
from dotenv import load_dotenv

from llm_calls import call_claude_with_fallback, call_openrouter_claude, call_openrouter_gpt

load_dotenv()


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("RUN_CONTRACT_TESTS", "0").strip().lower() not in {"1", "true", "yes", "on"},
    reason="Contract test skipped unless RUN_CONTRACT_TESTS=1",
)
async def test_openrouter():
    """Call Claude and GPT via OpenRouter with a trivial math prompt."""

    if not os.getenv("OPENROUTER_API_KEY"):
        pytest.skip("OPENROUTER_API_KEY not set")

    test_prompt = "What is 2+2? Answer with just the number."

    claude_response = await call_openrouter_claude(test_prompt)
    gpt_response = await call_openrouter_gpt(test_prompt)
    fallback_response = await call_claude_with_fallback(test_prompt)

    assert claude_response
    assert gpt_response
    assert fallback_response


if __name__ == "__main__":
    asyncio.run(test_openrouter())
