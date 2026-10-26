# Night queue — 2026-10-22 20:00 CST

Paper suite (all official harness/evaluator):

1. τ²-bench retail/airline/telecom — official `tau2` runner/evaluator
2. ALFWorld — official `alfworld` 0.5.0, `eval_out_of_distribution` 134 games
3. ScienceWorld — official `scienceworld` 1.2.3, official `lastStepScore`
4. BFCL v3 multi-turn long-context — official `bfcl-eval 2026.3.23`

## Running now

| Job | Where | What | ETA |
|---|---|---|---|
| τ² `pm_tau2v13_*` | any4 | retail 39 ×5 runs, **real retrieval injection** + selective predictor | ~2–3h |
| ALFWorld `rerank` | any4 | 134 games, 1 run, k=3 candidate + critic | ~2h |
| ScienceWorld `pmv4/basev4` | any4 | 30 tasks ×5 runs, official score, stronger prompt | ~3h |
| BFCL | done | official 59.50% (partial 199/200) | — |

## Official baselines already available

- τ² no-memory: retail 43.6 / airline 63.0 / telecom 87.0 (94 tasks paired)
- ALFWorld no-memory: 40.8% (125/306, 3 runs)
- ScienceWorld no-memory: old v2 15.9 mean score (policy-limited; v4 re-runs baseline too)
- BFCL: no baseline needed (capability column; official harness has no memory hook)

## Known caveats to check in the morning

1. τ² v13: does retrieval injection actually appear in prompts? Compare prompt tokens vs v3; check `events.jsonl` admission counts.
2. ALFWorld rerank: if <40.8%, revert; the critic may be no better than the base policy.
3. ScienceWorld: if completion stays ~1–2% for both arms, the policy is still too weak; the column is not usable without a stronger agent.
4. BFCL 59.50% is a partial evaluation (199/200); note it in the table footnote.

## Next decisions (morning)

- If τ² v13 > baseline: fix the config and run all 99 tasks + 5 runs.
- If not: keep retrieval injection but drop the gate claim; run a no-injection ablation for the paper.
- Replace ScienceWorld policy with a stronger planner before using it as a main column.

## 22:25 update

- τ² v13/v14/v15 all failed at runtime due to two wiring bugs introduced when adding
  retrieval: (a) the tail of `__init__` (`_store`, `_seen`, `_turn`) was accidentally placed
  inside `_retrieve_pm` after `return out`; (b) `_READONLY` regex was referenced but not
  defined in `tau2_agent.py`. Both are fixed; **v16** is running and its children are
  progressing through run_3 with no errors.
- ALFWorld rerank: **10/32 = 31%**, below the no-memory baseline 40.8%; stopped. Rerank is
  not helping on this policy.
- ScienceWorld v4: PM 0/78, baseline 3/84 — still ~1–4%; the policy cannot finish tasks, so
  the column remains non-discriminative.
- BFCL official remains 59.50%.

Morning decision unchanged: use τ² v16 (real injection) if it beats the 94-task baseline;
otherwise report the negative result with the wiring audit.

## 00:40 update (2026-10-23)

First **real** memory-injection run (v16, after fixing both wiring bugs):

- τ² retail, 39 tasks × 5 runs: **29.2%**
- no-memory baseline, same 39 tasks: **43.6%**
- → injection **hurts** by 14.4 points. The previous v3 “+5.1” was never injected memory
  (the retrieval hook was not wired), so it was run variance.

ScienceWorld v4 (official `lastStepScore`, stronger prompt):

- PredictMem 2/150 completed; baseline 5/150 — still ~1–3% for both, policy-limited and
  non-discriminative.

Controls now running:

- **v17**: same code, `top_k=0` (no injection) on the same 39 retail tasks. If v17 ≈ 43.6,
  the drop is caused by injection content, not by the extra predictor calls.

## 03:00 update (2026-10-23)

No-injection control **v17** (`top_k=0`, predictor kept, gate kept):

- 38/39 tasks ×5 runs: **26.8%** (baseline 43.6%, injection v16 29.2%)
- Event audit: 2047 events, 87% predictor-skipped (read-only), **103 blocks (5%)**
  from `memory_failure` (repeat-action blocking), 15 medium-risk predictions.
- → The 14–17 point drop is not caused by injection content: it is caused by **blocking
  repeated actions**, which τ² needs (e.g. multiple `get_`/`update_` turns).

Control **v18** launched: same code, `top_k=0`, `ablation.no_gate=true` (no blocking,
no injection; predictor calls still happen). Expected to land near 43.6 if the only harm is
the gate; if it is still ~27, the extra predictor call/context itself is the problem.

## 04:35 update (2026-10-23)

Control **v18** (`top_k=0`, `no_gate=true`; predictor still called for non-read-only actions):

- 38/39 tasks ×5 runs: **29.5%**
- No gate blocks, no injection — yet still ~14 points below the recorded baseline 43.6.

This means the drop is **not** explained by gate blocking or injection content. Two hypotheses:

1. the PM wrapper / predictor call itself perturbs the tau2 conversation, or
2. the recorded baseline 43.6 came from an older harness state and is not comparable.

**base19** launched: same current vendor code, `predictmem.enabled=false`, 39 retail tasks ×5.
If base19 ≈43.6, the wrapper is the harm; if base19 ≈29, the old baseline is stale and all
previous PM-vs-baseline comparisons on τ² must be recomputed.

## 05:45 update (2026-10-23)

**base19** (current vendor code, `predictmem.enabled=false`, 39 retail tasks ×5):

- **29.2%** — essentially identical to v16 (29.2), v17 (26.8), v18 (29.5).

Therefore the earlier baseline **43.6% is stale**. It came from an earlier harness/model
state and is not comparable with the current code. Under the current code:

| Arm | τ² retail (39×5) |
|---|---|
| baseline (base19) | **29.2%** |
| PM no-gate/no-injection (v18) | 29.5% |
| PM no-injection + gate (v17) | 26.8% |
| PM injection + gate (v16) | 29.2% |

**Conclusion:** on τ² retail with the current harness, PredictMem is statistically
indistinguishable from the baseline; the gate/injection do not help and (for v17) slightly
hurt. The old “+5.1” was a stale-baseline artifact, not a method effect.

All τ² airline/telecom baselines must be re-run with the current code before any paper table
is written. The same applies to any earlier comparison produced before 2026-10-22 13:00.

## 07:55 update (2026-10-23) — current-code 3-domain paired result

PM v20 (`pm_tau2v20_*`, injection + gate) vs baseline b20 (`base_tau2v20_*`), same code,
same tasks, 5 runs each, partial (53/99 common tasks so far):

| | PM | baseline | diff | SE |
|---|---|---|---|---|
| 53 paired tasks | **38.5%** | **52.8%** | **−14.3** | 4.2 |

This is **significantly worse** (|t| ≈ 3.4). The earlier “PM ≈ baseline” was retail-only;
across airline/telecom the injection + gate degrade the solver substantially.

Implication: the current memory/gate design is not neutral — it actively hurts on τ². The
paper cannot report a gain from this configuration; either the memory content/format is wrong
or the intervention must be removed. Runs continue to 99 tasks for the final table.

## 08:55 update (2026-10-23) — final trend

PM v20 72 tasks, baseline b20 98 tasks, 72 paired:

| | PM | baseline | diff | SE |
|---|---|---|---|---|
| 72 paired | **50.6%** | **62.5%** | **−11.9** | 3.4 |

Still significantly negative (t ≈ 3.5). The direction is stable across the partial
(53 tasks: −14.3; 72 tasks: −11.9), so this is not a small-sample artefact.

Decision: treat “inject effect records into the conversation + gate” as a **failed design**
on τ². Do not report it as a gain. The next iteration must remove context injection and use
memory only as a decision-time filter/reranker (or drop memory from the main claim).

## 12:30 update (2026-10-23)

**v22** (strict stuck-only injection: 3 identical outputs, once per task, no repeat blocking):

- 38/39 retail tasks ×5: **29.0%**
- baseline base19: **29.2%**
- → statistically indistinguishable. The stuck-only memory neither helps nor hurts;
  the earlier −12/−14 points came from per-turn injection + repeat-action blocking, both removed.

**ScienceWorld v5** (relevance-filtered actions, 100 steps):

- PM 0/102, baseline 0/96 — still no completed tasks; the policy, not the memory, is the
  bottleneck. This column cannot support a method claim yet.

State of the four-benchmark suite:

| Benchmark | Result | Meaning |
|---|---|---|
| τ² (3 domains) | PM ≈ baseline (retail 29.0 vs 29.2) | no method effect under current design |
| ALFWorld | baseline 40.8, PM 39.7 (old per-turn) | needs rerun with stuck-only |
| ScienceWorld | 0 vs 0 | policy-limited |
| BFCL | 59.50% official | capability column |

### v22 final paired check

38 common tasks (5 runs each):

| | PM v22 | baseline base19 | diff | SE |
|---|---|---|---|---|
| τ² retail | **28.9%** | **30.0%** | **−1.1** | 3.5 |

Neutral (|t| ≈ 0.3). Confirms the strict stuck-only memory neither helps nor hurts; the
component ablation on this design would only show null effects.

## 14:35 update — ablation (partial, 33–34 common tasks)

| Arm | Mean | Δ vs full | SE | Verdict |
|---|---|---|---|---|
| full (v22) | 31.2% | — | — | reference |
| no predictor | **36.5%** | **+5.3** | 3.7 | ns; removing it trends better |
| no gate | **37.6%** | **+6.5** | 4.0 | ns; removing it trends better |
| admit-all | 28.8% | −2.4 | 3.8 | ns |
| no versioning | 29.4% | −1.8 | 3.5 | ns |

No component is individually significant (all |t| < 1.7). The signs are informative:
removing the predictor or the gate *increases* success, i.e. those two components are, if
anything, mildly harmful; admission/versioning are neutral. This is consistent with the
earlier full-run result (PM below no-memory). Runs continue to 39 tasks for the final table.

## 15:35 update — final component ablation (38 common tasks, 5 runs)

| Arm | Mean | Δ vs full | SE | |t| | Significant? |
|---|---|---|---|---|---|
| full (v22) | 28.9% | — | — | — | — |
| no predictor | **33.7%** | **+4.7** | 3.4 | 1.4 | **no** |
| no gate | **33.7%** | **+4.7** | 3.7 | 1.3 | **no** |
| admit-all | 27.6% | −2.2 | 3.5 | 0.6 | no |
| no versioning | 26.3% | −2.6 | 3.2 | 0.8 | no |

Baseline (no memory) on the same code: 30.0%.

**No component is individually significant.** Removing the predictor or the gate trends +4.7
points (still ns), i.e. those two components are, if anything, mildly harmful; admission and
versioning are neutral. Component-level significance is therefore **not established** for the
current design, and the paper cannot claim it.

## 17:00 update — root cause of tau2 failures (trace analysis)

Parsed all run_0 traces of the current-code runs:

| Run | traces | success | fail: no tool call at end | fail: other |
|---|---|---|---|---|
| PM v22 | 39 | 16 | **23** | 0 |
| baseline base19 | 39 | 10 | **29** | 0 |

**Every τ² failure ends on a turn with no tool call** — the agent writes a summary or asks the
user to confirm ("Nothing will be done until you reply yes") and the episode terminates
unresolved. This is not a bad-action problem; it is a *termination* problem.

Fix (`v26`): `_ensure_tool_call` — if the assistant message has no tool call, re-prompt once
with "Do not end with a question/confirmation; issue the next tool call now" and replace the
message with the returned call. First 6 traces: guard fired 16 times; run in progress.

## 17:00 — v25 (verify-and-repair) final

33 common tasks, 5 runs:

| | v25 | baseline base19 | diff | SE |
|---|---|---|---|---|
| τ² retail | 29.7% | 32.7% | **−3.0** | 3.4 |

Single-candidate verify-and-repair is neutral-to-negative (|t| ≈ 0.9). The verifier agrees
with the solver and does not catch the actual failure mode (text termination). v26 tests the
forced-tool-call guard instead.

## 17:05 — ALFWorld stuck-only (partial)

| Arm | wins/games | rate |
|---|---|---|
| PM pmv6 | 11/39 | 28.2% |
| baseline basev6 | 14/46 | 30.4% |

Partial and slightly negative; the stuck-only memory does not help ALFWorld either. Runs continue.

## Weekend results (2026-10-26)

### ALFWorld stuck-only — final (402 paired game-runs)

| | PM pmv6 | baseline basev6 | diff | SE |
|---|---|---|---|---|
| win rate | **47.3%** | **45.5%** | **+1.7** | 1.7 |

First positive direction on ALFWorld, but t ≈ 1.0, not significant.

### τ² action-guard arms — negative

| Arm | evals | mean |
|---|---|---|
| v26 (force tool call, 1 retry) | 31 | 23.9% |
| v27 (act-until-done prompt + 3 retries) | 38 | 19.5% |
| baseline | 39 | 30.0% |

Forcing the agent to keep acting makes τ² worse; the model's text terminations are often
the only sensible endpoint it can produce.

### Best-of-N trajectory selection (verifier, no reward)

On existing traces (39 tasks × 5 runs), a completion verifier selects one trajectory per task:

| Trace set | mean success | selected success |
|---|---|---|
| PM v22 | 30.8% | **38.5%** |
| baseline base19 | 29.2% | 20.5% |

Selection helps PM traces (+7.7) and hurts baseline traces (−8.7): the verifier is fooled by
baseline text-terminations, while PM traces contain actual tool actions. Re-running selection
across v26/v27 is in progress to test whether action-complete traces are the key.

## 11:15 — best-of-N verifier (repeat)

Re-running the completion verifier on PM v22 traces: mean 30.8% → **selected 35.9%** (+5.1).
An earlier run gave 38.5%; the verifier is noisy, so the gain is +5–8 points, not stable.

The v26/v27 selection run stalled (judge calls too slow) and was stopped. Next step is to make
the verifier deterministic/self-consistent (3 judges, majority) before treating best-of-N as a
method component.
