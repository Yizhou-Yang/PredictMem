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
