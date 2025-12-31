# OpenRouter Setup Guide

Use OpenRouter as the single path for LLM calls. Forecaster models are configured via `model_config.py` and environment variables; prompts are shared from `prompts.py`.

## Why OpenRouter
- Single API for multiple providers (Claude, GPT, Gemini, Grok, etc.).
- Simple, single-path routing (no OpenAI SDK needed).
- Flexible, cheap model selection during testing.

## Prerequisites
- OpenRouter account + API key.
- `.env` in `Bot/` with:
  ```
  METACULUS_TOKEN=...         # optional for proxy calls
  OPENROUTER_API_KEY=...      # required for OpenRouter
  PERPLEXITY_API_KEY=...
  ASKNEWS_CLIENT_ID=...
  ASKNEWS_SECRET=...
  SERPER_KEY=...
  ```

## Setup
1. Create an account at [openrouter.ai](https://openrouter.ai/) and generate an API key.
2. Add `OPENROUTER_API_KEY` to `Bot/.env`.
3. Install deps: `pip install -r ../requirements.txt`.
4. Optional: override per-forecaster models via env (`FORECASTER_1_MODEL`, etc.) or edit `model_config.py`.

## How routing works
- All LLM calls use the configured forecaster models in `llm_calls.py` via OpenRouter.
- Prompts are always loaded from `prompts.py`, so behavior stays consistent across providers.

## Test your setup
```bash
cd Bot
python test_forecaster_models.py     # sanity-checks all 5 forecasters
python custom_forecast.py            # run an end-to-end custom forecast
```

## Choosing models
Defaults (at time of writing):
- Forecaster 1: `anthropic/claude-haiku-4.5`
- Forecaster 2: `google/gemini-2.5-flash`
- Forecaster 3: `openai/gpt-5-chat`
- Forecaster 4: `openai/o4-mini`
- Forecaster 5: `x-ai/grok-4-fast`

Override via env:
```
FORECASTER_1_MODEL=anthropic/claude-3.5-sonnet
FORECASTER_2_MODEL=google/gemini-2.5-pro
FORECASTER_3_MODEL=openai/gpt-4o
FORECASTER_4_MODEL=openai/gpt-4o-mini
FORECASTER_5_MODEL=meta-llama/llama-3.1-405b
```

## Troubleshooting
- **401/403**: check `OPENROUTER_API_KEY` and account balance.
- **Rate limits**: lower concurrency or pick lighter models.
- **Model not available**: swap to another model; see OpenRouter model list.
- **Proxy vs. OpenRouter confusion**: check logs from `llm_calls.py` to see which path was used.
