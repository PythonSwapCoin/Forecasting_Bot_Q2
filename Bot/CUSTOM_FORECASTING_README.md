# Custom Question Forecasting

Interactively forecast non-Metaculus questions using the same multi-stage pipeline as the tournament bot. Prompts, research, and forecaster orchestration are shared with the main system via `prompts.py`.

## What it does
- Builds a structured question (title, description, resolution, fine print, type).
- Runs historical + current research from `search.py`:
  - Primary LLM research via OpenRouter (Perplexity Sonar Deep Research).
  - Serper (Google/News) optional; URL attempt/success counts are tracked.
  - AskNews/Exa are optional; if no credentials are set they’re skipped cleanly.
- Executes two-phase prompting (outside view → inside view) per question type.
- Aggregates 5 forecaster models (configurable in `model_config.py`) with **equal weights** and writes results to `custom_forecasts/`.

## How it works (phases)
1. **User input** (`Bot/custom_forecast.py`): choose type (binary/numeric/multiple_choice) and provide details.
2. **Question struct**: normalized dict for downstream modules.
3. **Dual research** (`search.py`):
   - Historical prompt → queries → LLM research (Perplexity via OpenRouter) ± Serper summaries.
   - Current prompt → queries → LLM research (Perplexity via OpenRouter) ± Serper summaries.
4. **Phase 1 (outside view)**:
   - Binary: `BINARY_PROMPT_1`
   - Numeric: `NUMERIC_PROMPT_1`
   - MCQ: `MULTIPLE_CHOICE_PROMPT_1`
5. **Phase 2 (inside view)**:
   - Binary: `BINARY_PROMPT_2`
   - Numeric: `NUMERIC_PROMPT_2`
   - MCQ: `MULTIPLE_CHOICE_PROMPT_2`
6. **Ensemble** (`llm_calls.py`, `model_config.py`): 5 forecasters with equal-weight averaging by default.
7. **Output**: write forecast + rationale to `../custom_forecasts/<title>.txt`.

## Quick start (interactive)
```bash
cd Bot
python custom_forecast.py
```
Follow the prompts for type/title/description/resolution/fine print and any type-specific fields.

## Polymarket benchmark (5 binary markets)
Run the built-in benchmark to score the binary pipeline against five frozen Polymarket probabilities:
```bash
cd Bot
python custom_forecast.py --benchmark
```
Edit `Bot/polymarket_benchmark.py` to update the five markets. Each entry supports:
- `title` (str)
- `description` (str)
- `resolution_criteria` (str)
- `market_probability` (float 0-1 from Polymarket)
- optional `fine_print` / `context`

The run writes `custom_forecasts/polymarket_benchmark_<timestamp>.txt` with Brier and MAE per question.
Benchmarks also emit:
- `errors.txt`: contamination/errors per question.
- `run.log`: full buffered logs.
- Serper stats (attempted vs succeeded URLs) and search counts in summary.

## Programmatic use
Use `forecaster.py` helpers directly:
```python
import asyncio
from forecaster import binary_forecast

question = {
    "title": "Will XYZ IPO in 2025?",
    "description": "...",
    "resolution_criteria": "...",
    "fine_print": "",
    "type": "binary",
}

async def main():
    forecast, comment = await binary_forecast(question)
    print(forecast, comment[:500])

asyncio.run(main())
```

## Dependencies
- Python 3.9+
- `.env` in `Bot/` with:
  - `OPENROUTER_API_KEY`
  - `SERPER_KEY` (Google/News search, optional)
  - `PERPLEXITY_API_KEY` not required if using OpenRouter
  - `ASKNEWS_CLIENT_ID`, `ASKNEWS_SECRET` optional (skipped if missing)
  - `EXA_API_KEY` optional (skipped if missing)

Install packages:
```bash
pip install -r ../requirements.txt
```

## Tips for good questions
- Clear resolution criteria and timeframe.
- Provide background/fine print for context.
- For numeric: sensible bounds and units; optional zero point.
- For MCQ: >=2 options, mutually exclusive.

## Changing prompts and models quickly
- Prompts live in `Bot/prompts.py`. The shared system context is `FORECASTER_SYSTEM_CONTEXT` (aliased as `claude_context`/`gpt_context` for backward compatibility). Edit that string to adjust the forecaster persona once.
- Model choices live in `Bot/model_config.py` (defaults) and can be overridden via env vars `FORECASTER_1_MODEL` … `FORECASTER_5_MODEL`, or run `python configure_models.py` for a guided selector.
- Binary forecaster weights are set in `binary.py` (equal by default); adjust the `weights` list there if you need custom weighting.

## Troubleshooting
- **Missing keys**: verify `.env` under `Bot/`.
- **Empty research**: ensure `OPENROUTER_API_KEY` is set; set `SERPER_KEY` if you want Google/News fallback.
- **Write issues**: ensure `custom_forecasts/` is writable.
