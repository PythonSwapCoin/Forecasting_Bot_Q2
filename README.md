# Forecasting Bot

A multi-agent forecasting system for Metaculus and ad-hoc questions. It combines structured prompts, staged research (historical + current), parallel LLM forecasters, and ensemble aggregation. All prompts live in `Bot/prompts.py`, so Metaculus and custom runs share the same templates.

## What it does
- Forecasts binary, numeric, and multiple-choice questions.
- Runs historical + current search, outside-view + inside-view prompt phases, and aggregates 5 forecaster models (OpenRouter-only).
- Supports Metaculus tournament automation (`Bot/main.py`), interactive custom questions (`Bot/custom_forecast.py`), and a Polymarket benchmark harness.

## Documentation
- `CODE_INDEX.md` - File map and entry points.
- `docs/FORECASTING_AGENT.md` - Architecture, mermaid diagrams, and methodology expansion ideas.

## Project layout
- `Bot/` — forecasting engine (prompts, LLM calls, search, forecasters).
- `custom_forecasts/` — saved outputs from `custom_forecast.py` and benchmark runs.
- `ui/` — ReactFlow-based visual inspector (`ui/index.html`).
- `new_benchmark_o1/`, `Q2_tournament_forecasts/` — tournament outputs/examples.

## Architecture at a glance
1. **Input & structuring**: Build a question dict (title, description, resolution, fine print, type).
2. **Dual research**: Historical and current search prompts → AskNews/Google/Perplexity summaries.
3. **Phase 1 (outside view)**: Forecasters process historical context.
4. **Phase 2 (inside view)**: Forecasters combine outside view + current context to finalize probabilities/CDFs.
5. **Ensemble**: Weighted averaging across 5 forecasters (see `llm_calls.py` + `model_config.py`).
6. **Output**: Forecast + rationale saved to disk (and optionally posted to Metaculus).

### ASCII: custom forecast flow
```
User CLI input
      |
      v
Bot/custom_forecast.py
  - build question structure
  - route by type (binary/numeric/mcq)
      |
      v
Bot/forecaster.py --> binary.py / numeric.py / multiple_choice.py
      |
      v
  Research (search.py)
    [Historical prompt] -> search -> summaries
    [Current prompt]    -> search -> summaries
      |
      v
  Phase 1: Outside-view prompt (BINARY_PROMPT_1 etc.)
      |
      v
  Phase 2: Inside-view prompt (BINARY_PROMPT_2 etc.)
      |
      v
  Ensemble aggregation -> final forecast + commentary
      |
      v
Write result to custom_forecasts/<run-id>/
```

## Setup
1. **Python**: 3.9+
2. **Install deps**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Environment** (`Bot/.env`):
   ```
   METACULUS_TOKEN=...
   OPENROUTER_API_KEY=...      # all LLM calls go through OpenRouter
   PERPLEXITY_API_KEY=...
   ASKNEWS_CLIENT_ID=...
   ASKNEWS_SECRET=...
   SERPER_KEY=...              # Google search via Serper
   ```

## Running
- **Custom question (interactive)**:
  ```bash
  cd Bot
  python custom_forecast.py
  ```
- **Polymarket benchmark (5 binary markets scored vs. market odds)**:
  ```bash
  cd Bot
  python custom_forecast.py --benchmark
  # edit Bot/polymarket_benchmark.py to update the 5 questions + probabilities
  ```
  Outputs are written to `custom_forecasts/polymarket_benchmark_<timestamp>/` with:
  - `summary.txt` and `summary.json` (overall scores + per-question stats)
  - `questions/` (one markdown file per question with raw forecaster outputs)
  - `scores_by_forecaster.csv` (per-question, per-forecaster probabilities/weights)
  - `errors.txt` (any contamination/missing forecasts)
- **Metaculus tournament run**:
  ```bash
  cd Bot
  python main.py
  ```
- **UI viewer (prompts, agents, benchmark lane)**:
  ```bash
  cd ui
  python -m http.server 8000
  # open http://localhost:8000/index.html
  ```

## Configuration highlights
- **Prompts**: all in `Bot/prompts.py` (shared by Metaculus + custom + benchmark flows).
- **Model routing**: `Bot/model_config.py` + `Bot/llm_calls.py` (forecaster_1..5 defaults; overridable via env). OpenRouter-only; no OpenAI SDK usage.
- **Research**: `Bot/search.py` handles historical/current queries, AskNews/Google/Perplexity, summarization.
- **Forecasters**: `binary.py`, `numeric.py`, `multiple_choice.py` orchestrate outside/inside prompts and the ensemble.

## Troubleshooting
- Missing API key → check `.env` in `Bot/`.
- Empty outputs → ensure search keys (SERPER/Perplexity/AskNews) are present.
- Rate limits → lower concurrency or swap to cheaper models in `model_config.py`.
- OpenRouter errors → confirm `OPENROUTER_API_KEY` and that model names match `model_config.py`.
