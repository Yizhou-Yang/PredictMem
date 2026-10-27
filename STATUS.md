# Status — 2026-10-23

## Final benchmark suite (locked)

The paper uses exactly four benchmarks. Every column uses the **official harness and
official evaluator**; only the agent policy (PredictMem or the no-memory baseline) is ours.

| # | Benchmark | Official harness / evaluator | Metric |
|---|---|---|---|
| 1 | τ²-Bench (retail / airline / telecom) | Sierra `tau2-bench` runner + evaluator | mean success over 5 runs |
| 2 | ALFWorld | official `alfworld` 0.5.0, `eval_out_of_distribution` (134 games) | win rate over 3 runs |
| 3 | LongMemEval (cleaned, S) | official `longmemeval_s_cleaned.json` (500 questions) | token F1 |
| 4 | LoCoMo long-term dialogue | official LoCoMo data (snap-research/locomo), token F1 | official F1 |

No other benchmark is part of the paper. AppWorld, DeepSWE and Terminal-Bench are removed
from the main text, tables, and docs; their run artifacts remain on the experiment hosts only.

## Current official results

| Benchmark | No memory | PredictMem | Status |
|---|---|---|---|
| τ² (3 domains) | 62.5% (72 paired) | 50.6% (72 paired) | current-code interim; design under revision |
| ALFWorld | 40.8% (125/306) | 39.7% (old per-turn injection) | needs rerun with stuck-only memory |
| LongMemEval | 2.38 | **57.16** (50q pilot) | full 500 running |
| LoCoMo | — | — | runner + pilot in progress |

## Method state (2026-10-23)

- Memory is injected **only when the agent is stuck** (three identical tool outputs, once per
  task), not on every turn; per-turn injection measured −12 points on τ².
- Repeat-action blocking is removed from every agent.
- Risk is evidence-based: predicted failure (`expected_success=false`), failure keywords in the
  predicted effect, or destructive state changes raise risk above ε; the raw LLM risk label
  alone is not trusted (it is always `low` in the logs).
- `predict_consequential_only` is enabled only to skip read-only `get_/list_/search_` calls.

## Open issues

- Component ablations (full / no predictor / admit-all / no versioning / no gate) have not been
  run on the final suite; component significance is not established.
- ScienceWorld's agent policy still completes only a few tasks; the column is not
  discriminative until the policy is stronger.
- τ² current-code paired result is negative (PredictMem below no-memory); do not report it as
  a gain.

## Reproduce

See `results/OFFICIAL_4BENCH_2026-10-22.md` and `results/NIGHT_QUEUE_2026-10-22.md` for the
exact configs and commands.
