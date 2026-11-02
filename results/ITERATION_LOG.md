# Iteration log: problems, root causes, fixes

Every iteration records the failure, the root cause found in logs, the fix, and the check that
prevents a repeat. Read this before launching a new arm.

## 1. Gate block ends the episode (root cause of all negative predictor results)

- Symptom: any run with the gate enabled scores far below replay-only (τ² 65.5 vs 83.6;
  gate-only 58.7; ALF 61.9 vs ~80).
- Root cause: on a blocked call the agent cleared `tool_calls` and emitted text. In tau2 a
  message without a tool call terminates the episode, so every "block" was a give-up.
- Fix: fallback is **regenerate, never terminate**. If regeneration returns no call, execute
  the original call. Blocking is disabled whenever `PM_REPAIR=1`.
- Check: after a repair event there must still be a tool call; assert no `gate.block` event in
  the run.

## 2. Component silently disabled by config

- Symptom: "predictor has no signal" (risk flat 0.101/0.107) and `risk_repair` count 0.
- Root cause: runs used `termcomb` configs with `no_predictor=true`; events were literally
  `(predictor disabled)` / `(read-only action; predictor skipped)`. The analysis was done on
  disabled predictions.
- Fix: every run validates the effective config before launch.
- Check: `grep no_predictor` / `no_gate` in the config; count non-placeholder predictions
  before analysing calibration.

## 3. Wrong aggregation (step rows as games)

- Symptom: ALFWorld reported 0.6% wins.
- Root cause: counted step rows with `won=True` instead of per `(run, game)` aggregation.
- Fix: group by `(run, game)`, take the final `won`.
- Check: `len(games)` equals 134 × runs.

## 4. Rerank / MPC candidates were empty

- Symptom: `rerank_candidates: 1`, `mpc_candidates: 1`, no selection.
- Root cause: extra sampling returned no `tool_calls`; code silently used the original call.
- Fix: log candidate count; require `len(candidates) >= 2` or skip the mechanism.
- Check: `rerank_candidates > 1` in events before claiming a rerank result.

## 5. Fallback semantics on QA (abstain)

- Symptom: LongMemEval F1 0.179 with 370/500 abstain, then 0.0 with 500/500.
- Root cause: the LLM predictor always judged evidence unsupported; abstain replaced answers.
- Fix: risk from retrieval overlap (`top BM25 overlap >= 2`), abstain only when no hit.
- Check: abstain rate must be reported with F1.

## 6. Engineering errors that wasted whole runs

| Error | Root cause | Check |
|---|---|---|
| `SyntaxError` in prompt string | multi-line literal in Python | `python -c "import module"` before launch |
| `NameError: os` | missing import | import test |
| `pkill -f pm_vX` killed its own shell | pattern matched the launcher | use `[p]m_vX` |
| DAEDALUS inference failed | generation → inference skipped `consolidate` | run consolidate; verify pool exists |
| DeepSeek `model not found` | driver hardcoded base_url 8743 | `PM_BASE_URL` respected |
| DeepSeek `hy3` error at evaluation | tau2 NL-judge default hardcoded | `TAU2_NL_JUDGE_MODEL` |

## 7. Model drift

- hy3 retail baseline moved 29% → 49% within days. Only contemporaneous pairs are valid.
- Fix: always launch baseline and treatment in the same batch; never compare across days.

## Pre-launch checklist

1. Config path exists; `no_predictor` / `no_gate` / `top_k` match the intended arm.
2. Module imports and the config parses.
3. Base URL and model match the relay (`8743` hy4, `8745` deepseek).
4. Runs / concurrency / timeout fit the budget.
5. Metric aggregation is per task or per game, never per step.
6. If the arm uses predictor/controller, count non-placeholder predictions and repair/block
   events **before** interpreting the score.
7. Record the run in this file with its result.
