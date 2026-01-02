# Forecasting Bot

A multi-agent forecasting system for Metaculus and ad-hoc questions. It combines structured prompts, staged research (historical + current), parallel LLM forecasters, and ensemble aggregation. All prompts live in `Bot/prompts.py`, so Metaculus and custom runs share the same templates.

## What it does
- Forecasts binary, numeric, and multiple-choice questions.
- Runs historical + current search, outside-view + inside-view prompt phases, and aggregates 5 forecaster models (OpenRouter-only).
- Supports Metaculus tournament automation (`Bot/main.py`), interactive custom questions (`Bot/custom_forecast.py`), offline baseline snapshots, and replay-mode benchmarks.

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
- **Baseline snapshot (offline, uses replay fixtures)**:
  ```bash
  cd Bot
  python custom_forecast.py --baseline-snapshot
  ```
  Writes `custom_forecasts/baseline_<timestamp>/` with per-question outputs + metadata.
- **Benchmark runner (replay-friendly)**:
  ```bash
  cd Bot
  python custom_forecast.py --benchmark                  # defaults to benchmarks/questions.jsonl
  python custom_forecast.py --benchmark path/to/file.jsonl
  ```
  Outputs are written to `benchmarks/runs/run_<timestamp>/` with per-question logs and `summary.json`.
- **Metaculus tournament run**:
  ```bash
  cd Bot
  python main.py   # defaults to single-shot submissions (TOURNAMENT_SINGLE_SHOT=true)
  ```
- **Diagnostics / key check**:
  ```bash
  cd Bot
  python custom_forecast.py --diagnostics           # env/flag snapshot
  python custom_forecast.py --diagnostics --diagnostics-live  # add lightweight API pings
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
- Missing API key -> populate `OPENROUTER_API_KEY` (LLMs), `SERPER_KEY` (Google), `ASKNEWS_CLIENT_ID`/`ASKNEWS_SECRET` (news), `METACULUS_TOKEN` (proxy). Disable a provider with `ENABLE_SERPER=false`, `ENABLE_ASKNEWS=false`, etc. Fallbacks to Perplexity trigger warnings instead of hard failures; provider status is logged once per run.
- Empty/slow outputs -> ensure search keys are present; if unavailable, set `FALLBACK_TO_PERPLEXITY=true` and cap `PERPLEXITY_CALL_LIMIT` to keep runs cheap. Evidence lake writes can be disabled with `ENABLE_EVIDENCE_LAKE=0`.
- Rate limits / bad models -> lower concurrency or switch to cheaper models in `Bot/model_config.py`; most calls route through OpenRouter (no `OPENAI_API_KEY` is used). Multi-sampling/aggregation knobs live in `Bot/config.py` (`FORECAST_RUNS_PER_MODEL`, `AGGREGATION_MODE`, probability caps).
- Diagnostics -> `python Bot/custom_forecast.py --diagnostics` (add `--diagnostics-live` for lightweight API pings) to see key presence + provider enablement. Provider status is also logged once per run.
- Evidence lake -> enable with `ENABLE_EVIDENCE_LAKE=1`; defaults to file-based JSON + `index.jsonl`, optional SQLite backend via `EVIDENCE_LAKE_BACKEND=sqlite`.
- Tests -> install deps, run `pytest -q`; contract/API tests stay skipped unless `RUN_CONTRACT_TESTS=1` is set with valid keys. CI runs offline tests and optional contract tests when `OPENROUTER_API_KEY` is present.
- Tournament guardrails -> `Bot/main.py` defaults to single-shot submissions (`TOURNAMENT_SINGLE_SHOT=true`) and caps reruns with `NUM_RUNS_PER_QUESTION`; keep `SKIP_PREVIOUSLY_FORECASTED_QUESTIONS=true` to avoid duplicates.
