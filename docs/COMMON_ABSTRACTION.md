# The common abstraction across the four benchmarks

All four benchmarks instantiate the same three objects. Only the action space and the effect
representation change.

## Objects

| Symbol | Object | Shared definition |
|---|---|---|
| $M$ | effect store | records $(s, a, \hat e, e, \text{prov})$: state, action, predicted effect, observed effect, provenance; versioned by $(s,a)$ |
| $P$ | predictor | independent prediction $\hat e = P(s, a)$ of the effect of the candidate action, with a confidence |
| $C$ | controller | compares the predictor output with the policy output; commits on agreement, expands the search on disagreement |

## One decision step

```
a_policy ~ policy(s)                     # the base policy proposes an action or an answer
ê        = P(s, a_policy)                # independent prediction of that action's effect
g        = agree(ê, e_policy)            # does the predicted effect match the proposed one?
if g:      commit a_policy
else:      search R↑ (more evidence / more exploration), recompute ê and a, commit once
```

The controller never abstains and never terminates on a disagreement. After one expansion it
commits the policy action, so the worst case is the base policy.

## Effect, per benchmark

| Benchmark | action $a$ | effect $e$ | agreement test | expansion $R\uparrow$ |
|---|---|---|---|---|
| $\tau^2$ | tool call | next observation / state change | predicted observation matches the tool result | re-issue the call after a state read |
| ALFWorld | text command | next frame | predicted observation matches the frame | explore an unvisited location |
| LongMemEval | answer | answer text | predicted answer is contained in the policy answer | per-session retrieval |
| LoCoMo | answer | answer text | predicted answer is contained in the policy answer | full-conversation retrieval |

## Why this abstraction

The per-question logs show one failure pattern in all four: **the agent commits before its
evidence or actions cover the question or the goal**. The controller above turns the predictor
into a coverage detector: agreement means the evidence supports the commit; disagreement means
search more.

It also explains the negative results that came before:

| Variant | Why it failed under this abstraction |
|---|---|
| gate / abstain | used the predictor to reject a commit instead of expanding the search |
| risk repair on every high-risk call | replaced correct actions because the predictor's risk was not calibrated |
| per-session retrieval always | applied the expansion unconditionally, adding noise |
| termination check | expanded after a correct commit |

## Measured support

- LoCoMo: agreement subset F1 0.573 vs 0.242 on disagreement; agreement-gated commit 0.3534
  vs always-full 0.2256 and fixed top-k 0.2988.
- ALFWorld: procedure routing chosen by the predicted task type reaches 0.717 on the holdout
  subset (partial runs) vs 0.619 without routing.
- LongMemEval: fixed retrieval remains stronger than the predictor-gated variant; the
  abstraction predicts that the disagreement rate must be informative before it can help.
- $\tau^2$: replay is the gain; the predictor stays inert unless its risk labels are calibrated.
