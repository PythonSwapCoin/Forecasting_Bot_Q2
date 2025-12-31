# Code Index

This index is a map of the main forecasting pipeline, supporting utilities, and data outputs.

## Top-level
- `README.md` - High-level overview, setup, and run commands.
- `requirements.txt` - Python dependencies.
- `ui/index.html` - ReactFlow-based viewer for inspecting runs.
- `custom_forecasts/` - Output from `Bot/custom_forecast.py` and benchmarks.
- `Q2_tournament_forecasts/` - Output from Metaculus tournament runs.
- `new_benchmark_o1/` - Example benchmark outputs.

## Core forecasting engine (`Bot/`)
- `main.py` - Metaculus tournament runner (fetches questions, forecasts, posts results).
- `custom_forecast.py` - Interactive custom-question runner and benchmark entry point.
- `forecaster.py` - Thin wrapper routing by question type.
- `binary.py` - Binary pipeline: research, outside view, inside view, ensemble.
- `numeric.py` - Numeric pipeline: research, two-stage prompts, CDF generation.
- `multiple_choice.py` - MCQ pipeline: research, two-stage prompts, ensemble.
- `prompts.py` - All system prompts and query templates used by every pipeline.
- `search.py` - Research orchestration: query parsing, web search, AskNews, Perplexity, agentic search.
- `llm_calls.py` - LLM API clients (Metaculus proxy + OpenRouter).
- `model_config.py` - Model routing and per-forecaster overrides.
- `research_config.py` - Feature flags and search defaults.
- `logging_utils.py` - Buffered logger for run logs, errors, and search stats.
- `polymarket_benchmark.py` - Benchmark harness (binary markets vs. market odds).

## Supporting utilities (`Bot/`)
- `FastContentExtractor.py`, `HTMLContentExtractor.py` - Web content extraction helpers.
- `Dataset.py` - Dataset helper for benchmarks.
- `browser.py` - Browser/Scraping helper for research.
- `benchmark.py` - Benchmark helper utilities.
- `configure_models.py` - Model configuration helper script.

## Tests and examples
- `Bot/test_forecaster_models.py`, `Bot/test_openrouter.py`, `Bot/test_search_fix.py` - Light test utilities.
- `Bot/example_custom_forecast.py` - Example custom forecast runner.
