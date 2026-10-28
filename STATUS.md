# Status — 2026-10-28 (hy4-only)

## Suite

τ² (retail/airline/telecom), ALFWorld, LongMemEval, LoCoMo. hy3 archived; all new runs use
`hy4-preview`.

## Results (hy4)

| Benchmark | no-memory baseline | PredictMem | significant? |
|---|---|---|---|
| τ² retail | 77.9% (39 tasks) | **80.0%** (v62 replay) | no (+2.1, ns) |
| ALFWorld | 49.4% (395 games) | **61.5%** (395) | **yes, t=5.1** |
| LongMemEval | 0.0615 | **0.3220** (t=14.73) | **yes** |
| LoCoMo | 0.0383 | **0.0909** (t=7.17) | **yes** |

## Competitor baselines (τ² retail, hy4, 40×5)

| Arm | Success |
|---|---|
| **ACE** | **78.0%** |
| ExpeL | 74.5% |
| no-memory | 74.5% |
| DAEDALUS | pending (pool generation running; 7/12 sessions at 03:00) |
| PredictMem | 67.4% (negative) |

## What failed (from logs)

- gate blocking: −13 points
- per-turn memory injection: −12/ALF −3.5
- termination verifier: hy4 −12
- failure memory: −21.5 (τ²), started firing only after content-error fix
- AWM workflow injection: −26.7 (τ² holdout)
- execution-feedback MPC: technically fixed but too slow (4 tasks / 3h)

Memory helps only when the task is **long-context QA** (LoCoMo, LongMemEval) where retrieval
beats truncation. On agentic benchmarks the current memory/control layer is harmful.

## Next

1. Let DAEDALUS generation finish (12 sessions), then memory inference.
2. Do not scale the negative mechanisms; report them honestly.
3. To beat ACE (78%) on τ² we need a different policy, not more memory tuning.
