# Raw traces (readable, per run)

All numbers in `results/FAIR_SPLIT_TABLE_2026-10-29.md` are computed from these files.

## Structure

```
traces/
  hy4/
    baseline/<domain>_t<task>/run_<k>/*.json    τ² no-memory, official evaluator
    pm_replay/<domain>_t<task>/run_<k>/*.json    PredictMem (same-task successful replay)
    competitors/hy4_{ace,expel}_<domain>_infer/run_<k>/*.json
  alfworld/hy4/<arm>_<shard>.jsonl               one JSON per step; `won` at episode end
  memory/lme_rows.json                           LongMemEval per-question predictions/F1
  memory/locomo_rows.json                        LoCoMo per-question predictions/F1
  memory/*_competitors.out                       adapted ACE/ExpeL/DAEDALUS logs
```

Each τ² run directory contains the full official simulation trace and `evaluation.json`.
Recompute a cell with any JSON reader; no private tooling is required.

## Reproduce the summaries

- τ²: read `evaluation.json` per task, average over tasks and 5 runs.
- ALFWorld: group `*.jsonl` by `(run, game)`, take the last `won` value; do not count step rows.
- LongMemEval / LoCoMo: average `f1_base` (no memory) and `f1_mem` (PredictMem) in the JSON rows.

Competitor banks and adaptation scripts are recorded in `results/FAIR_SPLIT_TABLE_2026-10-29.md`.
