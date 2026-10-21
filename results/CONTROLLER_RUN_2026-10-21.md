# PredictMem controller run — 2026-10-21 (HY3 only)

This note records the first end-to-end runs of the **control-theoretic PredictMem**
(`PredictiveController`, chance constraint, cost, fallback) after switching AppWorld and τ²
off the earlier retrieval `EffectGate`. Results are reported as they are, including negative
ones. Nothing here uses task reward, verifier output, or gold data inside the loop.

## AppWorld test_normal — `pm_appworld_ctrl7`

- Harness: DAEDALUS vendored, HY3 relay, `control_eps=0.25`, `horizon=1`, memory off, PredictMem on.
- 24 workers, 5 runs intended.
- **Partial evaluation (3 runs): MSR 0.8006, pass^3 0.619, pass@3 0.923**
  (tasks per run: `[168, 168, 166]`).
- The launch was ended by the 90-minute stall detector ("no task finished in 90 min with 365
  outstanding"). Runs 3–4 were resumed with the same experiment name; at 22:18 CST the resume
  had 251/504 completed with `ok=72` (**29%**), which is far below the 80% of runs 0–2.
  The resumed portion is **not** used as a result until the cause is understood.

Comparison (HY3, 5 runs unless noted): no-memory **82.62**, DAEDALUS memory **84.88**,
ACE **82.62†**, ExpeL **71.07†**. The 3-run 80.06 is below DAEDALUS.

## τ² retail — per-task isolation, 39/39

- `pm_tau2_t<id>` experiments, 5 runs per task, one process per task (the τ² process pool
  crashes after ~9 tasks at any concurrency; per-task isolation avoids it).
- **39/39 tasks complete, MSR 0.4308.**
- Task `70` excluded: both PredictMem and the baseline fail with `model not found`; it is a
  harness/task issue, not a method result.
- The NL-assertion judge was hardcoded to `gpt-4.1-2025-04-14` in `tau2/config.py`; patched to
  `openai/hy3`. Before the patch, tasks 36+ failed during evaluation with `model not found`.

Comparison (HY3): no-memory **51.50**, ExpeL **57.50†**, ACE **44.00†**.
**PredictMem 0.4308 is below no-memory.**

## DeepSWE v1.1 — 250 steps, PredictMem plugin

- Job `pm-deepswe-113f`, 8 workers, `PIER_PREDICTMEM=1`,
  `model.model_class=predictmem_pier.model.PredictMemModel`.
- First 6 results: **4 solved (reward 1; 33, 65, 87, 102 steps), 2 failed (46, 68 steps)**.
  These are the earliest (easier) tasks; 4/6 is a pilot, not a rate. The run continues.
- Earlier `pm-deepswe-113e` produced **113/113 infra failures**: Docker had 34 stale networks
  and could not allocate an IPv4 pool. Pruned to 4 and relaunched as 113f.
- Base mini-swe-agent reference: **17/113 = 15.04%** at 100 steps, N=1, lower bound (54 empty
  patches from the old collect hook).

## Seed of the negative result

- AppWorld gate blocks: **0 / 2624 events** in run_0 (admitted 473, ~18%). The chance constraint
  almost never fires; most admissions come from surprise.
- The resumed AppWorld runs, which start with a store already populated by earlier runs, drop to
  ~29% success. τ² (memory injected from turn 0) is also below no-memory.
- Working hypothesis: **effect-record injection is context pollution**, not a control benefit;
  the write signal is label-free as designed, but retrieval adds tokens without improving the
  solver's decisions. A per-run isolated store and a no-injection control are needed before
  claiming any gain.

## Bugs fixed during this run (all reproducible)

1. `control_eps` was `gate.tau_block=0.75` (too lax) → independent `control_eps=0.25`.
2. Risk labels mapped to 0.1/0.5/0.9, so `medium=0.5 > 0.25` blocked nearly every action
   (AppWorld success fell to 2/17) → calibrated to 0.02/0.15/0.60.
3. Predictor failure returned `risk=medium`, which then blocked every step → fail-open with
   `predictor_unavailable`.
4. `Prediction` was imported inside `_before_execute`, making it a local variable and raising
   `UnboundLocalError`; one AppWorld launch scored 0/168 → module-level import.
5. `task_pool._STALL_TIMEOUT_S` 1500 → 5400 s (controller tasks exceed 25 min).
6. Pier plugin: mini-swe-agent tool results are JSON (`{"returncode", "output"}`), not
   `<returncode>` XML; the observation was never parsed and `turn` stayed 0 → JSON parsing.
7. Pier plugin: command extraction now prefers `extra.actions` (the executed command) over the
   raw tool-call template, which could be the literal `{code}` placeholder.
8. Docker network pool exhaustion on any2 (34 networks) killed all 113 tasks at environment
   setup → prune before launch, monitor count.
9. τ² NL assertion judge hardcoded to `gpt-4.1-2025-04-14` → `openai/hy3`.

## Reproduce

```bash
# AppWorld controller
.venv/bin/python -m daedalus.scripts.inference \
  --config configs/pm_appworld_controller.yaml \
  --experiment-name pm_appworld_ctrl7 --num-runs 5 --parallel 24

# τ² per task
for id in $(python -c 'from tau2.runner import get_tasks; print(" ".join(t.id for t in get_tasks("retail", task_split_name="test") if t.id != "70"))'); do
  .venv/bin/python -m daedalus.scripts.inference \
    --config configs/pm_tau2_controller.yaml \
    --task-id "$id" --num-runs 5 --parallel 1 --experiment-name "pm_tau2_t$id"
done
```

Artifacts: `outputs/inference/appworld/predictmem/pm_appworld_ctrl7/evaluation.json`,
`outputs/inference/tau2/predictmem/pm_tau2_t*/evaluation.json`,
`/data/pier/jobs/pm-deepswe-113f/*/result.json` (any2).

## Addendum — 22:40 CST

- **τ² no-injection control** (`predictmem.top_k=0`, 10 concurrent, per-task):
  **13/39 tasks complete, partial MSR 0.3692**. The subset differs from the 39-task 0.4308,
  so this is not a like-for-like comparison yet; on the completed subset, removing injection
  does **not** improve the score. The "injection pollution" hypothesis is therefore not
  supported so far.
- **DeepSWE 113f**: **6/113 results, 4 solved** (reward 1 at 33, 65, 87, 102 steps; two failures at
  46 and 68 steps). The six are the earliest (easier) tasks, so 4/6 is a pilot, not a rate.
  Containers run 250-step episodes at ~50 s/step (~3.5 h per task); 8 workers cannot finish 113
  tasks in this session.
- **AppWorld resume**: stalled again at 256/504 (`ok=74`); the available AppWorld number
  remains the 3-run **80.06**.
- No benchmark currently beats its baseline. The claim "SOTA" is not supported by these runs.
