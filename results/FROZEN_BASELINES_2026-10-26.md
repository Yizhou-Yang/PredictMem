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
