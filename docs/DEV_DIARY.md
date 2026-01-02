# Forecasting Bot Implementation Diary

This diary records what was implemented from `docs/IMPLEMENTATION_PLAN.md`, why choices were made, and any caveats for future work.

## 2025-01-01 11:30
- Added baseline configuration loader (`Bot/config.py`) with a default `baseline` profile. Flags default to replay/evidence lake off, diagnostics on. This gives a reproducible "all-new-features-off" setup.
- Added structured run metadata helper (`Bot/run_metadata.py`) capturing timestamp, git hash, model map, default weights, provider status, search stats, and file paths. Integrated into `Bot/custom_forecast.py` and `Bot/main.py` so each run writes `metadata.json`.
- Implemented provider diagnostics entry point (`Bot/diagnostics.py`) and CLI flags `--diagnostics`/`--diagnostics-live` on `custom_forecast.py`. Live checks are lightweight (model list call + tiny Serper call) to validate keys.
- Made research more graceful: `Bot/research_config.py` now exposes provider status; `Bot/search.py` logs provider availability once; `Bot/binary.py` no longer aborts when research fails, instead continues with empty context and logs warnings.
- Created initial pytest scaffold (`requirements.txt` adds pytest/pytest-asyncio, `tests/conftest.py`, `tests/test_config.py`, `tests/test_run_metadata.py`). Not yet run because pytest is not installed in the current env.

Open actions carried forward:
- Collect baseline outputs for each question type once API keys are available.
- Expand tests to cover parsing/aggregation and add smoke fixtures when replay mode is built.

## 2025-01-01 11:35
- Installed dependencies and ran `pytest -q`; base tests now pass. Legacy async OpenRouter tests were converted to contract tests, gated by `RUN_CONTRACT_TESTS`, and skipped by default.
- Ran diagnostics with live checks (`python Bot/custom_forecast.py --diagnostics --diagnostics-live`); OpenRouter is enabled and healthy. Serper key present but provider disabled by config (ENABLE_SERPER=False). AskNews/Bright Data remain disabled (no creds).
- Replaced deprecated `datetime.utcnow` usage in `run_metadata.py` to remove warnings.
- Communication summary to user (with next steps):
  - Reported config/metadata changes, diagnostics status, test gating for contract tests, and passing pytest run.
  - Highlighted next steps: enable providers as desired (e.g., `ENABLE_SERPER=true`, add AskNews/Bright Data creds), optionally run contract tests with `RUN_CONTRACT_TESTS=1 pytest -q`, and capture baseline forecasts for binary/numeric/MCQ with keys configured.
- Next: consider enabling Serper/AskNews when desired, and run baseline forecasts for each question type once providers are configured as intended.

## 2025-01-01  13:45
- Enabled Serper by default when a key is present (research config now auto-enables with SERPER_KEY); diagnostics now show Serper enabled. AskNews/Bright Data remain disabled pending creds.
- Added graceful research fallback to numeric and multiple-choice pipelines (parallel to binary): if research is missing, proceed with empty context and log warnings instead of aborting.
- Kept pytest suite green; contract tests remain skipped unless `RUN_CONTRACT_TESTS` is set.
- Communication summary to user (with next steps):
  - Reported enabling Serper, research fallback updates, diagnostics status, and passing tests.
  - Next steps: provide AskNews/Bright Data creds if desired, capture baseline forecasts for each question type, and expand tests/fixtures (replay mode) plus smoke suite.

## 2026-01-01 14:30
- Added parser/validation unit tests for binary (probability parsing), MCQ (probability parsing/normalization), and numeric (percentile parsing, monotonic CDF generation). All tests pass with `pytest -q`.
- Expanded README troubleshooting with provider-specific env vars, fallback guidance, and testing instructions.
- Updated CI workflow: added a `tests` job on push/PR/schedule, fixed secret naming to `OPENROUTER_API_KEY`, and gated the scheduled bot run on passing tests.

Open actions carried forward:
- Implement replay/offline mode plumbing and smoke suite (`ENABLE_REPLAY_MODE` + fixtures) so pipelines can run without network.
- Add structured research/evidence outputs and extend graceful fallback logging across pipelines.
- Enable additional providers (AskNews/Bright Data) if credentials are provided; run contract tests with `RUN_CONTRACT_TESTS=1` when keys are available.

## 2026-01-01 16:12
- Implemented replay/offline mode scaffolding: added `ReplayStore`/fixtures (`tests/fixtures/replay`), replay-aware LLM/search calls, and `EvidenceItem`/`ResearchResult` structured research outputs in `search.py`.
- Added offline smoke suite (`Bot/smoke_suite.py`) plus CLI flag `--smoke` on `custom_forecast.py`; created replay fixtures and suite definitions in `benchmarks/suites/smoke.jsonl`. New pytest coverage (`test_smoke_suite.py`) validates invariants offline.
- Built lightweight experiment harness (`Bot/experiment_runner.py`) to run suites across env variants (with matrix support) and added pytest guard (`test_experiment_runner.py`).
- Updated pipelines (binary/numeric/MCQ) to use replay keys and structured research, plus replay-safe LLM calls without API keys; fixed MCQ logging when no writer is provided.
- All tests passing (`pytest -q`), with warnings only from external AskNews SDK; next steps include expanding live search structuring and evidence lake/backfill.

## 2026-01-01 17:05
- Added file-based evidence lake writer (`Bot/evidence_store.py`) gated by `ENABLE_EVIDENCE_LAKE`/`EVIDENCE_LAKE_DIR`; `process_search_queries` now persists structured `ResearchResult` per question slug when enabled.
- Hooked evidence lake persistence into replay-aware search results; kept replay fixtures/tests green (`pytest -q`).
- Next steps: enrich live search outputs with richer `EvidenceItem` fields (title/date/snippet hashes), add SQLite/indexed storage option, and propagate evidence lake references into run metadata/outputs.

## 2026-01-01 17:40
- Enriched evidence lake persistence with per-item index (`evidence_lake/<run_id>/index.jsonl`) and ensured runtime env flags control writing. Evidence lake now uses UTC timestamps without deprecated calls.
- Added unit coverage for evidence lake persistence (`tests/test_evidence_store.py`); full pytest suite passing.
- Evidence items now include provider/source metadata and are saved when `ENABLE_EVIDENCE_LAKE=1`.

## 2026-01-01 18:00
- Implemented baseline snapshot runner (`Bot/baseline_snapshot.py`) and wired `--baseline-snapshot` / `--benchmark` CLI options to `custom_forecast.py`; new replay-friendly benchmark dataset lives in `benchmarks/questions.jsonl` with outputs saved to `benchmarks/runs/`.
- Added leakage-aware benchmark harness (`Bot/benchmark_runner.py`) plus CI contract-test job gating scheduled runs; README troubleshooting now covers fallbacks, diagnostics, and guardrails.
- Extended `EvidenceItem` fields (title/date/hash/publisher/paths), added retrieval KPIs, and upgraded evidence lake to support SQLite+dedup; search logging now hashes snippets and stores retrieved timestamps.
- Introduced aggregation scaffolding (trimmed/median modes and probability caps) used in binary/MCQ pipelines, optional priors/critique hooks, and new research metrics helpers; tests expanded for evidence lake SQLite and retrieval KPIs (all passing with replay).

## 2026-01-01 19:30
- Added multi-sampling support (`FORECAST_RUNS_PER_MODEL`) across binary/numeric/MCQ pipelines with aggregation modes and probability caps respected; replay mode forces single-sample to reuse fixtures.
- Hardened replay compatibility for prompt2 keys and kept smoke/experiment runners green (`pytest -q` passing).

## 2026-01-01 20:30
- Phase 3 completed: benchmark runner now reports per-type metrics (binary Brier/log loss + catastrophic miss rate, MCQ cross-entropy/Brier, numeric CRPS/MAE), binary ECE calibration, runtime stats, leakage flags, and richer CLI options (`--output-dir`, `--profile`, `--evidence-cutoff`, `--live`). Benchmark dataset now includes resolution dates; `benchmarks/README.md` documents schema/metrics plus usage.
- Phase 4 core implemented: deterministic search planning/formalization (`build_search_plan`) feeds fallback queries; structured research now returns deduped `EvidenceItem` objects with quality scores, KPIs, fact candidates, and per-question `research_report` persisted to the evidence lake. Added follow-up query loop when coverage/diversity is low (skipped in replay) and quality scoring for domains/timeliness.
- Evidence lake/reporting: added `persist_research_report`, replay runs now emit reports, and research evidence is attached to question details for leakage-aware benchmarking. Introduced lightweight fact extraction (`fact_extraction.py`) and retrieval evaluation scaffolding (`benchmarks/research_eval.jsonl`, `Bot/research_eval.py`).
- Tests extended for retrieval KPIs/quality, search planning, fact extraction, and research eval; full pytest suite passing (19 tests, 2 skipped, 1 warning from AskNews SDK).
