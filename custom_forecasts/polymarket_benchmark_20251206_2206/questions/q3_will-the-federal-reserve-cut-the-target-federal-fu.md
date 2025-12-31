# Q3: Will the Federal Reserve cut the target federal funds upper bound by 25 bps at the December 2025 meeting?

- Market probability: 0.940
- Model forecast: 0.350
- Brier: 0.3481
- MAE: 0.5900
- Status: ok
- Contamination: False

## Per-forecaster probabilities
- Forecaster 1 [anthropic/claude-haiku-4.5]: 0.19 (weight=1)
- Forecaster 2 [google/gemini-2.5-flash]: 0.15 (weight=1)
- Forecaster 3 [openai/gpt-5-mini]: 0.35 (weight=1)
- Forecaster 4 [openai/o4-mini]: 0.6 (weight=2)
- Forecaster 5 [x-ai/grok-4-fast]: 0.28 (weight=2)

## Resolution
Resolves YES if the FOMC statement for the December 2025 meeting indicates a 25 bps decrease. Any non-25 bps move is resolved per Polymarket rounding rules: changes are rounded up to the nearest 25 bps bracket.

## Context
Tracks whether the FOMC lowers the upper bound of the target federal funds rate by exactly 25 basis points relative to its level before the December 9-10, 2025 meeting.

Full raw outputs/logs: raw_outputs/q3_will-the-federal-reserve-cut-the-target-federal-fu_raw.txt
