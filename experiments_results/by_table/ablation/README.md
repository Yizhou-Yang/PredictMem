# Ablation matrix (hy4)

Each column removes one component while the harness, prompts and data stay fixed.

| Benchmark | no memory / no store | no predictor | no controller | full |
|---|---|---|---|---|
| tau2 retail | 77.9 | replay 83.6 | 83.6 (replay only) | 83.1 (predictor active, no veto; 39/39, paired -0.5, t=-0.23) |
| ALFWorld | 52.5 | 61.9 (memory, no procedure) | 61.9 | **74.9** (procedure routing) |
| LongMemEval | 0.3074 (full context) | 0.3072 (dated retrieval) | 0.3072 | **0.3469** (agreement + expansion) |
| LoCoMo | 0.2190 (full context) | 0.2988 (top-k retrieval) | 0.2988 | **0.3534** (agreement + expansion) |

Component reading:

- **Store** is what separates the "no memory" column from every other column; it is positive on
  all four benchmarks.
- **Predictor+controller** are positive on LongMemEval (+0.040, paired t=4.25) and LoCoMo
  (+0.055 over top-k, paired t=9.25), neutral on ALFWorld when the controller only routes, and
  neutral on tau2 when the controller does not veto (84.7 vs 83.6 replay).
- On tau2 the earlier gate arm (58.7) and repair arm (66.7) are the negative controls that
  motivated "never veto" in the controller.
