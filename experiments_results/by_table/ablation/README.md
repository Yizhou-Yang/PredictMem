# Ablation matrix

Each column removes one component while keeping the harness fixed.

| Benchmark | no memory | no predictor (store + controller) | no controller (store only) | full |
|---|---|---|---|---|
| tau2 retail | 77.9 | replay 83.6 | gate-only 58.7 | full 65.5; predictor-active no-gate v83 running |
| ALFWorld | 52.5 | 61.9 (pmv14, no procedure) | 61.9 | **74.9** (procedure) |
| LongMemEval | 0.3074 (full context) | 0.3021 (flat retrieval) | 0.3021 | **0.3469** (agreement) |
| LoCoMo | 0.2190 (full context) | 0.2988 (top-k retrieval) | 0.2988 | 0.2988 (agreement; 0.3534 with expansion, unverified) |

## What is still missing

1. tau2: the predictor-active arm on all 39 tasks (v83) — currently 10 paired tasks, 73.3 vs
   replay 74.0.
2. ALFWorld: a no-controller arm is the same as no-procedure because the controller only routes.
3. LongMemEval / LoCoMo: a "no store" arm is the full-context baseline, already reported.
4. Significance: tau2 paired t=1.83 (borderline); LoCoMo +0.08 needs a paired test.
