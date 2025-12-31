# Model Configuration

Configure which models each forecaster uses (via OpenRouter) without touching code.

## Defaults (forecaster 1-5)
- `anthropic/claude-haiku-4.5`
- `google/gemini-2.5-flash`
- `openai/gpt-5-chat`
- `openai/o4-mini`
- `x-ai/grok-4-fast`

## Configure via environment
Add to `Bot/.env`:
```
OPENROUTER_API_KEY=your_key

FORECASTER_1_MODEL=anthropic/claude-3.5-sonnet
FORECASTER_2_MODEL=google/gemini-2.5-pro
FORECASTER_3_MODEL=openai/gpt-4o
FORECASTER_4_MODEL=openai/gpt-4o-mini
FORECASTER_5_MODEL=meta-llama/llama-3.1-405b
```
Unset variables fall back to the defaults above.

## Configure in code
Edit `Bot/model_config.py`:
```python
DEFAULT_MODEL_CONFIG = {
    "forecaster_1": "...",
    "forecaster_2": "...",
    "forecaster_3": "...",
    "forecaster_4": "...",
    "forecaster_5": "...",
}
```

## How routing works
- `llm_calls.py` reads `model_config.py` and environment overrides.
- Prompts come from `prompts.py` and are combined with model-specific contexts (Claude vs GPT).
- Calls are issued via OpenRouter.

## Testing your config
```bash
cd Bot
python test_forecaster_models.py   # exercises all 5 forecasters
python custom_forecast.py          # end-to-end run with your model choices
```

## Tips
- Start with cheaper/lighter models for testing (e.g., `gpt-4o-mini`, `claude-haiku-4.5`).
- Keep at least one diversity model (e.g., Grok/Gemini) for ensemble robustness.
- Watch costs/rate limits on OpenRouter; reduce concurrency if you see throttling.
