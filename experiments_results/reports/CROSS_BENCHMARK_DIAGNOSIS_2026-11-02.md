# Cross-benchmark diagnosis: the common failure is premature commitment

This note abstracts the per-question failures into one mechanism, then states what to change.

## Per-question evidence

| Benchmark | Failure count / rate | Signature in the logs | What was missing at commit time |
|---|---|---|---|
| τ² retail | 10/39 baseline failures, all end with a turn that has no tool call; 8 of 10 have no tool error | the agent stops before the order state is updated | the required mutation was never executed |
| ALFWorld | losing games average 48.5 steps vs 10.2 for wins | the agent keeps moving between rooms and containers | the target object was never found or placed |
| LongMemEval multi-session | F1 0.118; gold 3 answered 1, gold 5 answered 2 | evidence from one session only | items from the other sessions were never retrieved |
| LoCoMo temporal | F1 0.090 on 321 questions | answers "No evidence", "session_2" | the dated utterance was never retrieved |

## The common abstraction

In every case the agent **commits before its evidence covers the question or its actions cover the
goal**. The failure is not a wrong prediction of an effect; it is a **missing coverage check
before commitment**.

Coverage is checkable per benchmark:

| Benchmark | Coverage condition | Search that fills it |
|---|---|---|
| τ² | required write executed, confirmation observed | keep issuing tool calls until the state changes |
| ALFWorld | object held, target receptacle visited | explore unvisited rooms/containers |
| LongMemEval | every relevant item enumerated across sessions | per-session retrieval, then count |
| LoCoMo | dated utterance for the entity is in evidence | retrieve the sessions that mention the entity |

## What to change

1. Replace "predict risk, gate" with **"predict the missing coverage element, then search"**.
   The predictor outputs what is missing (an entity, a date, an item, a mutation), not a
   block/abstain decision.
2. Add a **deterministic coverage check** per adapter. The predictor only names the missing
   element; the check decides whether it is present. This avoids the LLM yes/no calls that
   misfired in the plan variants (LME plan 0.2402 vs 0.3016; per-session 0.0706 vs 0.118).
3. Keep commitment unconditional after one search round. No abstain, no termination.

## Why earlier variants failed

| Variant | Result | Reason |
|---|---|---|
| gate / abstain | τ² 65.5, LME 0.179 | they used the predictor to stop |
| risk repair | τ² 70.8 | replaced correct actions |
| per-session always | LME 0.0706 | extra context is noise unless the question needs it |
| predictor chooses retrieval scope | LME 0.2402 | the LLM choice was worse than the fixed prior |
| termination check without cap | τ² 46.7 | continued after a correct finish |

The pattern: the predictor works only when it names a **specific missing element**, and the
controller then takes a **specific search action**.
