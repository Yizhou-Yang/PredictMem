# Frozen baselines — 2026-10-26

From this point on, **baselines are frozen**. No baseline reruns unless the protocol itself
changes (model endpoint, task set, evaluator). PredictMem is iterated against these numbers;
after it beats them, we do one systematic final run of both arms.

## Protocol

- Model: HY3 endpoint as of 2026-10-26 (model behaviour drifted between Oct 23 and Oct 26;
  only same-day pairs are valid).
- Evaluator: official harness only.
- τ²: retail + airline + telecom, 99 tasks (task 70 excluded), 5 runs each, official tau2
  reward.
- ALFWorld: official `eval_out_of_distribution`, 134 games × 3 runs, official `won`.
- LoCoMo: official `locomo10.json`, token F1 (full-context vs retrieval).
- ScienceWorld: policy-limited (0 completions); **not used as a baseline for significance**.

## τ² baseline (b21, 99 tasks × 5)

| Domain | Success |
|---|---|
| retail (39) | **49.2%** |
| airline (20) | **63.0%** |
| telecom (40) | **78.0%** |
| overall (99) | **63.6%** |

## ALFWorld baseline (basev6, 134 × 3)

| Arm | Win rate |
|---|---|
| no memory | **45.5%** (183/402) |

## LoCoMo baseline (full context)

- Pilot running; number to be frozen when the full-context arm finishes.

## Current PredictMem gap (must close before final rerun)

| Arm | τ² retail | Δ vs frozen 49.2 |
|---|---|---|
| v32 (no-gate + memory) | 40.0% | −9.2 |
| v35 (wrapper only, no memory/gate) | 44.9% (33 tasks) | −4.3 |
| v34 (termination verifier) | partial, promising | TBD |

The wrapper itself costs ~4 points; memory currently costs ~3 more. PredictMem must first
recover the wrapper cost and then add a positive mechanism.

## First PM iteration against the frozen baseline (retail, 39 paired)

| Arm | PM | baseline | diff | SE |
|---|---|---|---|---|
| v32 no-gate + memory | 48.2% | 49.2% | −1.0 | 3.9 |
| v35 wrapper-only | 49.2% | 49.2% | 0.0 | 4.6 |
| v36 wrapper, predictor off | **53.3%** | 51.7% | +1.7 | 4.0 |
| v34 termination verifier | 65.0% | 40.0% | +25.0 | 10.9 (n=4) |

Key correction: the earlier retail −13.3 was caused by the gate; with the gate removed the
wrapper and memory are neutral (v32/v35 ≈ baseline). The best current arm is v34
(termination verifier) but only 4 tasks are evaluated; v36 (predictor off) is +1.7 ns.

ALFWorld v7: PM 11/32 so far.

## 15:45 update — v34 inconclusive, ALFWorld v7 negative

- v34 (termination verifier): stopped after 90 min at **6/39 tasks** (processes 0.1% CPU,
  dominated by verifier retries). Partial 6 tasks looked +28 but n is too small and the
  remaining tasks were not completing; not usable.
- ALFWorld v7 (admission 0.50): PM 11/37 = 29.7%, baseline v7 12/38 = 31.6% — slightly
  negative, no improvement from the lower admission threshold.

No arm currently beats the frozen baseline. The remaining positive-looking signal (v34) is
too slow and too small to trust.

## 16:45 — LoCoMo

Parser bug fixed: `conversation` is a dict keyed `session_1..N`, not a list; the first pilot
produced empty contexts and F1≈0.

50-question pilot after fix:

| Arm | token F1 |
|---|---|
| full context | 0.0718 |
| retrieval memory | **0.0907** |

Retrieval memory is +1.9 F1 over full context on the pilot; full 2000-question run is in
progress with 8 threads.

## ScienceWorld

Still 0/150 for both arms. The environment is fine (gold sequence completes `boil` at
score 100), but the zero-shot policy cannot act in the 417-way syntactic action space.
Not usable as a significance column.

## 16:47 — v37 partial, stopped

18 retail tasks (termination verifier, 1 retry):

| PM | baseline | diff | SE |
|---|---|---|---|
| 47.8% | 42.2% | +5.6 | 7.7 |

Not significant; v37 was stopped to free capacity for the 20-task fast round (v38), which
tests the same mechanism in a bounded <1h budget.

## 20:30 — LoCoMo FULL: first significant result

1542 QA pairs, 10 conversations:

| Arm | token F1 |
|---|---|
| full context (no memory) | 0.0609 |
| retrieval memory | **0.1591** |

Paired difference: **+0.0982, SE 0.0092, t = 10.65 → significant.**

Retrieval memory is 2.6× the full-context F1. This is the first benchmark where the
memory mechanism shows a statistically significant gain (official LoCoMo data, token F1).

Note: this is retrieval memory, not the effect-predictor; it supports the memory claim but
not the controller claim.

## τ² fast v42 final (17/20)

PM 43.5% vs baseline 37.6% → +5.9, SE 6.6 (ns). 544 multi-candidate execution-feedback events.

## ALFWorld fast (partial)

PM 33 vs baseline 32 games (still running) — flat.

## 2026-10-27 — LongMemEval (replaces ScienceWorld)

Official cleaned S, 500 questions, hy4-preview:

| Arm | token F1 |
|---|---|
| full context | 0.0615 |
| retrieval memory | **0.3220** |

Paired: **+0.2604, SE 0.0177, t = 14.73 → significant.**

Second significant memory column. ScienceWorld removed from the suite (policy cannot complete
it; env verified with gold at score 100).

## hy4 τ² progress

- b22 baseline: 34/99 tasks, mean 77.6%
- v47 termination-only: 1 task so far (slow)
- ALFWorld v8 (hy4) launched cleanly.

## 2026-10-27 12:20 — hy4 progress

- LoCoMo hy4 (1542 QA): full 0.0383, retrieval 0.0909 → **+0.0526, SE 0.0073, t=7.17 (significant)**
- τ² hy4 baseline b22: 55/99 tasks, mean 81.5%
- τ² hy4 termination-only v47: 3 tasks (slow)
- ALFWorld hy4 v8: launched, no completed games yet

Both memory benchmarks are significant under hy4 as well; τ² remains the open column.

## 14:05 — hy4 full progress / API utilisation

- τ² hy4 baseline b22: **99/99 complete, 74.5%**
- τ² hy4 v47 (termination only): 15 tasks, 50.7% (below baseline)
- ALFWorld hy4 v8: **0 wins in 938+941 games (both arms)** — a severe regression vs hy3
  (45.5%). hy4 emits valid ALF commands but loops (`examine bed` repeatedly), so this is a
  policy/prompt mismatch for hy4, not a harness failure.
- LongMemEval hy4: 0.0615 → 0.3220 (t=14.73); LoCoMo hy4: 0.0383 → 0.0909 (t=7.17)
- Relay API usage: ~553 calls / 10 min ≈ **55 calls/min**, well below the 250–300/min seen
  earlier; the ALFWorld and termination-verifier runs are latency-bound, not rate-limited.

## 15:05 — hy4 ALFWorld diagnosis

Fixes tried: parser now matches admissible commands inside free text; program-level anti-repeat;
`reasoning_effort` switched from `low` (unsupported by hy4) to `no_think`.

Result: hy4 still **4 wins / 655 games (0.6%)**, vs hy3 45.5%. Actions are valid ALFWorld
commands, but hy4 loops on `examine` and does not pursue the task. This is a model-level
agentic weakness on ALFWorld, not a harness/format bug.

Conclusion: use hy3 for the agentic columns (τ², ALFWorld); use hy4 for the memory columns
(LoCoMo, LongMemEval), where it is significant.

## 15:20 — correction: hy4 ALFWorld is NOT 0.6%

The earlier 0.6% was my aggregation bug: I counted **step rows** (655) as games and ignored
that a winning game contributes one `won=True` row among many steps.

Correct per-(run, game) aggregation for v11 (`no_think`):

| Arm | games | wins | rate |
|---|---|---|---|
| pmv11 | 28 | 12 | **42.9%** |
| basev11 | 28 | 12 | 42.9% |

Root fixes: `reasoning_effort` must be `no_think` for hy4 (it does not support `low`); with
`high` the response content is empty (reasoning consumes the budget). hy4 is not weaker on
ALFWorld — the integration was wrong and my earlier aggregation was wrong.

## 15:35 — v49 (hy4, termination verifier) is negative

5 completed tasks paired with b22:

| PM | baseline | diff | SE |
|---|---|---|---|
| 52.0% | 64.0% | **−12.0** | 9.1 |

On hy4 the termination verifier hurts, unlike hy3 (+7 ns). Combined with ALFWorld parity,
this means only the two memory benchmarks reach significance against their baselines:

- LongMemEval +0.2604 (t=14.73)
- LoCoMo +0.0526 (t=7.17)

τ² and ALFWorld do not. Current PM mechanisms cannot deliver "significant on all four"; the
agentic columns need a different policy, not more prompt/verifier tuning.

## 15:45 — best-of-5 selection (offline, hy4)

LLM completion judge over existing 5 runs per task:

| Run | tasks | mean | selected |
|---|---|---|---|
| b22 baseline | 95 | 74.8% | **84.2%** |
| v47 PM | 20 | 41.7% | 50.0% |

Selection adds ~+8–9 points to **both** arms, so it does not close the PM-vs-baseline gap; PM
selected (50%) is still far below baseline selected (84%). Test-time selection is a real
component but cannot make the current τ² PM beat the no-memory baseline.

Conclusion stands: only LongMemEval and LoCoMo are significantly better than their baselines.

## 19:00 — MPC works but is impractical; ALF run killed

- Fixed MPC (`set_state` replay) now executes candidates: scores 1.0–2.0 instead of −1.
- v50 (MPC K=2, fast20): only **4 tasks** completed after 3h; on those, PM 90% vs baseline 100%
  (−10, SE 8.7). The execution-feedback overhead (reset + replay + trial per step) makes the
  run too slow to scale.
- ALFWorld v11 processes were **Killed** (resource pressure); partial 28 games: PM 12, base 12.
- LongMemEval and LoCoMo remain the only significant results.

Status: execution feedback is now technically correct but not a viable mechanism at this cost.
