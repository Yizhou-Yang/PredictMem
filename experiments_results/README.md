# experiments_results

Every number in the paper is recomputed from this tree.

```
traces/hy4/                  tau2 run directories (official evaluator output inside each)
traces/alfworld/hy4/         ALFWorld step logs, one JSON line per step
traces/memory/               LongMemEval and LoCoMo per-question rows
artifacts/                   packaged snapshots of the same runs
reports/                     analysis notes (failure analysis, iteration log, fair-split table)
outputs/                     raw inference directories for the public runs
_paper/main_table.json       the values printed in the paper
_paper/verify.py             recomputes those values from the traces
```

## Verify

```bash
python3 experiments_results/_paper/verify.py
```

It prints one line per table cell with the paper value, the value recomputed from the trace, and
`ok` or `MISMATCH`, then the reproduced share. The current tree reproduces **12/12** cells.

## Trace format

- tau2: `<experiment>_<domain>_t<task>/run_<k>/...` plus `evaluation.json` written by the
  official evaluator. Success is `aggregate.success_rate_mean`.
- ALFWorld: `<arm>_<shard>.jsonl`, one row per step with `run`, `game`, `action`, `won`. Aggregate
  per `(run, game)`, never per step.
- LongMemEval / LoCoMo: JSON rows with `q`, `gold`, `f1_base` (no memory) and `f1_mem`
  (PredictMem). LoCoMo rows additionally carry `predicted`, `agree`, `escalated`.

## Reports

`reports/` holds the per-question failure analysis, the iteration log with root causes, and the
fair-split table. They are analysis notes, not inputs to `verify.py`.
