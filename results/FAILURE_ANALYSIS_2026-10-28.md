# Failure analysis — 2026-10-28

Two classes of failures wasted most of the iteration time.

## A. Engineering failures (looked like “method doesn't work”)

| Failure | Symptom | Root cause | Fix |
|---|---|---|---|
| Workflow injection string | every PM child exits instantly, 0 eval | multi-line string literal in `tau2_agent.py` | fixed to `"\n"` |
| `os` import | `NameError` at first turn | used `os.environ` without import | import added after `__future__` |
| `pkill -f pm_tau2vXX` | killed the shell/job that launched it | pattern matched its own command line | use `[p]m_tau2vXX` |
| wrong config path | ran gate-on config while thinking gate-off | f-string path replacement missed | verify config path in child cmdline |
| task-id 0/1 | 0/0 runs, empty evaluation | retail test ids start at 5 | use real ids |
| missing consolidate | DAEDALUS inference failed after generation | generation→inference skipped consolidate | add consolidate step |
| ALF aggregation | reported 0.6% wins | counted step rows instead of (run, game) | per-game aggregation |

## B. Mechanism failures (real, from logs)

| Mechanism | Evidence | Why it failed |
|---|---|---|
| gate blocking | 102/2018 blocks, retail −13 | blocked non-destructive actions |
| per-turn injection | ALF −3.5, τ² −12 | irrelevant context distracts the policy |
| stuck-only memory | ≈0 | almost never fires (admission 0 in first build) |
| termination verifier | 24 vs 5 tool errors, −12/−17 | forces extra calls; model then errs |
| failure memory | −21.5 | after fixing detection, “avoid failed call” picks worse actions |
| AWM workflow | −26.7 | injected random/irrelevant workflows (no similarity threshold) |
| ACE playbook verbatim | −6.4 | rules work only inside ACE's own scaffold |
| MPC execution feedback | 4 tasks / 3h | reset+replay per candidate is O(n²); not viable |

## C. What actually worked

- **thresholded action→effect memory** (ALFWorld): BM25 score ≥1, top-3, `action -> observation`; +12.2, t=5.3
- **same-task successful replay** (τ²): 80.0% vs 77.9 baseline, above ACE 78.0 (pair +2.1 ns)
- **retrieval memory vs full context** (LoCoMo +0.0526 t=7.17; LongMemEval +0.2604 t=14.73)

## D. Measurement lesson

- HY3 endpoint drifted (retail baseline 29% → 49% within days); only contemporaneous pairs are valid.
- Always aggregate per game/task, never per step row.
- Baseline must be the same harness with `predictmem.enabled=false`, same day, same model.
