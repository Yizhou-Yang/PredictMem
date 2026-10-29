# Raw traces — hy4-preview, 2026-10-29

All runs use `hy4-preview` via the taiji relay.

| File | Contents |
|---|---|
| `tau2_baseline_b22.tar.gz` | τ² no-memory baseline, 99 test tasks ×5 runs, official tau2 traces |
| `tau2_pm_v63_v64.tar.gz` | PredictMem replay: retail (v63), airline+telecom (v64), 5 runs each |
| `tau2_competitors.tar.gz` | ACE and ExpeL inference traces for retail/airline/telecom |
| `alfworld_results.tar.gz` | ALFWorld PM/base/ACE/ExpeL/DAEDALUS jsonl (per step) |
| `lme_rows.json` | LongMemEval per-question predictions and F1 (500 questions) |
| `locomo_rows.json` | LoCoMo per-question predictions and F1 (1542 questions) |
| `lme_competitors.out` / `locomo_competitors.out` | adapted ACE/ExpeL/DAEDALUS run logs |

Extract with `tar xzf <file>`; each τ² directory contains `run_*/` traces plus `evaluation.json`.

Summary tables: `results/FAIR_SPLIT_TABLE_2026-10-29.md`.
