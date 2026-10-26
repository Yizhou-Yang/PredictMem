# Fast iteration protocol (≤3h per PM round)

Purpose: iterate PredictMem quickly on reduced official subsets. Once PM beats the frozen
baseline on the fast subsets, run the full suite; baselines are added/re-run only at the end.

All subsets use the official harness/evaluator and the same HY3 endpoint.

| Benchmark | Fast subset | Runs | Expected time |
|---|---|---|---|
| τ² retail | first **20** test tasks (task 70 excluded) | 5 | ~1h at 16 workers |
| ALFWorld | **60** games (`--max-games 60`) | 3 | ~40 min at 8 shards |
| LoCoMo | first **500** QA pairs | 1 | ~30 min at 8 threads |
| ScienceWorld | 10 tasks | 1 | not usable (policy 0) |

## Reference points on the fast subsets

- τ² retail 20: frozen baseline b21 on the same 20 tasks (subset of the 39-task run).
- ALFWorld 60: frozen baseline basev6 on the same games.
- LoCoMo 500: full-context arm, same questions.

## Rules

1. Only PM is run during iteration; baseline numbers are extracted from the frozen runs on
   the identical subset (no baseline reruns).
2. A PM variant must beat the frozen subset baseline with a positive paired difference and
   SE small enough to be meaningful before it is scaled.
3. After the fast protocol passes, run the full suite once for PM and once for the baseline,
   on the same day.

## 17:46 — τ² fast (v38) partial

14/20 tasks done (termination verifier + no-gate + memory):

| PM | baseline (same tasks) | diff | SE |
|---|---|---|---|
| 48.6% | 37.1% | **+11.4** | 9.0 |

Positive trend, not yet significant (t≈1.3); 6 tasks still running.

## 18:42 — τ² fast (v38) final

19/20 tasks (the last task was still running; 2 processes):

| PM | baseline (same 19) | diff | SE |
|---|---|---|---|
| **45.3%** | 41.1% | **+4.2** | 8.2 |

The early +11.3 shrank to +4.2 as the remaining tasks arrived: the first-completed tasks were
easier and biased upward. Against the full fast20 baseline (42.0%) the gain is ~+3.3 points,
not significant. The termination-verifier mechanism is not strong enough on its own.
