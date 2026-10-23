# Official 4-benchmark suite — 2026-10-22

Paper table uses these four benchmarks. Every environment/evaluator is the official one;
only the agent policy is ours (PredictMem or the no-memory baseline).

| # | Benchmark | Official harness | Cost | Role |
|---|---|---|---|---|
| 1 | τ²-bench (retail/airline/telecom) | Sierra `tau2-bench` runner + evaluator (vendored) | ~5h | tool policy + control |
| 2 | ALFWorld | official `alfworld` 0.5.0 (GitHub), `eval_out_of_distribution` 134 games | ~2h | action–effect |
| 3 | ScienceWorld | official `scienceworld` 1.2.3, official task list + `lastStepScore` | ~2h | action–effect |
| 4 | BFCL v3 multi-turn long-context | official `bfcl-eval 2026.3.23`, `bfcl generate` + `bfcl evaluate` | done | tool calling / long context |

AppWorld, DeepSWE and Terminal-Bench are not part of the paper.

## Results so far

### τ² (official evaluator, 5 runs/task, 99 tasks)

| Domain | n | PredictMem | no-memory | diff |
|---|---|---|---|---|
| retail | 39 | 48.7% | 43.6% | +5.1 |
| airline | 20 | 65.0% | 63.0% | +2.0 |
| telecom | 40 | 85.0% | 87.0% | −2.0 |
| overall | 99 | — | — | **+1.6** (sd 0.246) |

Not significant. These numbers were produced **before** the memory-retrieval hook was wired
(`_get_retrieved_memories` was defined but never called in the tool agents), so they are effectively
baseline + no-op predictor calls and should be treated as run-variance, not a method result.

### ALFWorld

- baseline (no memory): **40.8%** (125/306 over 3 runs).
- action-rerank (k=3 + critic) run in progress; early games are mixed.

### ScienceWorld

- PredictMem: 2/142 completed games; baseline 3/143.
- Both ~1–2% — the policy cannot complete the tasks, so the benchmark currently has no
  discriminative power for the method. Needs a stronger policy before it can support a claim.

### BFCL (official)

- `multi_turn_long_context`: **59.50%** (partial, 199/200 entries).
- This is a model capability column, not a PredictMem-vs-baseline comparison; the official
  harness has no memory hook.

## Caveats

- The earlier τ² +2.8/+5.1 numbers must be relabeled: they are not controller effects.
- The real integration (retrieval into `_generate_turn` / `self.retrieve`) is now wired and is
  being re-run; only those runs can be used for the paper.
- ScienceWorld needs a policy fix before its numbers mean anything.

## Reproduce

```bash
# tau2, per task, 5 runs
.venv/bin/python -m daedalus.scripts.inference --config configs/pm_tau2_retail.yaml \
  --task-id <id> --num-runs 5 --parallel 1 --experiment-name pm_tau2v13_retail_t<id>

# BFCL official
bfcl generate --model hy3 --test-category multi_turn_long_context --skip-server-setup
bfcl evaluate --model hy3 --test-category multi_turn_long_context --partial-eval
```
