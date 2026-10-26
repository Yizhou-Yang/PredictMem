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

## 20:20 — Reflexion (v40) final + execution-feedback (v42) partial

| Arm | n | PM | baseline | diff | SE |
|---|---|---|---|---|---|
| v40 Reflexion-lite | 20 | 45.0% | 42.0% | +3.0 | 6.7 |
| v42 multi-candidate + exec feedback | 17 | 43.5% | 37.6% | +5.9 | 6.6 |

v40: reflection fired 18 times, +3.0 ns.
v42: 544 candidate-selection events; +5.9 partial, still not significant.

## 21:50 — v43 (MPC + termination) partial final

18/20 tasks:

| PM | baseline | diff | SE | t |
|---|---|---|---|---|
| 48.9% | 41.1% | +7.8 | 9.4 | 0.82 |

The early +25 (n=8) again shrank with the remaining tasks: completion-order bias. Still not
significant. v44 raises the candidate count from 3 to 5 to see whether execution-feedback
selection quality improves.

## 23:32 — v44 (5-candidate MPC + termination) final

| n | PM | baseline | diff | SE | t |
|---|---|---|---|---|---|
| 20 | 49.0% | 42.0% | **+7.0** | 6.8 | 1.03 |

Not significant. Per the pre-registered rule (diff > 8 to scale), the τ² mechanism iteration
stops here. Best τ² arms:

| Arm | diff | t |
|---|---|---|
| v44 5-cand MPC + termination | +7.0 | 1.0 |
| v43 MPC + termination | +7.8 | 0.8 |
| v42 MPC | +4.0 | 0.7 |
| v40 Reflexion | +3.0 | 0.4 |

No τ² arm reaches significance; the effect is consistently +4..+8 with SE 6-9.
