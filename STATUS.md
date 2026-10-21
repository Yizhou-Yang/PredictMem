# Status — 2026-10-21 11:20 CST

## DeepSWE v1.1 (HY3, mini-swe-agent via Pier)

| Run | Result | Notes |
|---|---|---|
| 30 steps × 5 tasks | 0/5 | all hit the 30-step cap |
| 100 steps × 5 tasks | 1/5 | v100 sample |
| **100 steps × 113 tasks** | **17/113 = 15.04%** | any2, N=1, 5 workers |
| 250 steps × 22-task subset | running | process-fix validation (worktree capture) |

**Process defect found in the 113 run:** 54/113 trials produced a **0-byte patch** because the
task collect hook captured only `git diff <base> HEAD` (committed changes). 55 trials exited
`LimitsExceeded`; all 16 solves had non-empty patches. The 15.04% is therefore a lower bound.

Fix used for the 250-step subset: `git add -A && git diff --binary <base>` so uncommitted work
is captured. 22 tasks: 15 empty-patch capped + 2 non-empty capped + 5 saved-but-failed controls.

Artifacts: `results/hy3_deepswe_113_any2_20261021.json`, `results/HY3_DEEPSWE_113_2026-10-21.md`.

## AppWorld test_normal (HY3, DAEDALUS harness)

Existing HY3 numbers (validity-checked): baseline 82.62 MSR, ACE 82.62†, ExpeL 71.07†.
DAEDALUS memory and PredictMem were not valid (2 runs / unequal denominators; PredictMem not implemented).

### Now running on any2/any4 (2026-10-21)

| Arm | Namespace | Workers | Progress |
|---|---|---|---|
| DAEDALUS memory | `verified_20261021_mem12` | 12 | 5 runs × 168; ~100/840 at launch |
| **PredictMem** | `verified_20261021_pm` | 8 | 5 runs × 168; just started |

The memory arm was previously hardcoded to `parallel=4`; it is now 12. PredictMem uses 8.
Total 20 workers on any4 + 5 DeepSWE on any2 ≈ 25 concurrent HY3 calls (relay has no QPM limit).

### PredictMem arm

From-scratch implementation (see `docs/PREDICTMEM_ARM_DESIGN.md` and `harness/`):

- predictor -> surprise (semantic + LLM judge + execution) -> selective admission -> versioned store
- BM25 retrieval, warn/block gate
- config-driven ablations: no predictor / admit all / no versioning / no gate
- smoke: 1/1 on `82e2fac_1`, 10 events, 2 admitted records

Next: τ² 5×40 for both arms, then ablations, then update the paper's main table.

## τ² retail (HY3)

Existing HY3: baseline 51.50, ACE 44.00†, ExpeL 57.50†.
DAEDALUS memory: 5 runs but one run has 39/40 tasks (unequal denominators) -> not yet valid.
PredictMem: not implemented for τ² yet.

## Repo state

- `harness/predictmem/` — PredictMem arm source (reference copy)
- `harness/INTEGRATION.md` — exact patches to the vendored harness
- `docs/PREDICTMEM_ARM_DESIGN.md` — design spec
- PredictMem vendor commit on experiment host: `d1a687e`

## Controller run — 2026-10-21 (HY3)

First runs with `PredictiveController` (cost + chance constraint + fallback) replacing the
retrieval `EffectGate`:

| Arm | Result | Status |
|---|---|---|
| AppWorld `pm_appworld_ctrl7` | **80.06 MSR** (3 runs; pass^3 0.619, pass@3 0.923) | below DAEDALUS 84.88; resume of runs 3–4 dropped to ~29% and is not used |
| τ² `pm_tau2_t*` | **43.08 MSR** (39/39 tasks, 5 runs each) | below no-memory 51.50 and ExpeL 57.50† |
| DeepSWE `pm-deepswe-113f` | first 3: **2 solved** (33, 65 steps), 1 failed | 250 steps, 8 workers; run continues |

Negative-result evidence: AppWorld gate blocked **0/2624** events; memory injection is the
likely cause of the τ² drop and of the 29% resumed AppWorld rate. See
`results/CONTROLLER_RUN_2026-10-21.md` for the full bug log (control_eps, risk calibration,
`Prediction` scoping, JSON observations, Docker network exhaustion, τ² NL judge model).
