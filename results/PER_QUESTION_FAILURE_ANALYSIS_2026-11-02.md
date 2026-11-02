# Per-question failure analysis (2026-11-02)

All numbers are from the run logs, not estimates. The goal is to locate the component that
causes each failure, then change that component.

## τ² retail

Baseline failures: **10/39**. Classification from the traces:

| Pattern | Count |
|---|---|
| Episode ends with a turn that has no tool call | **10/10** |
| No tool error anywhere in the episode | **8/10** |
| At most two tool errors | 2/10 |

The dominant failure is **premature termination**: the agent stops issuing tool calls before
the task is complete. It is not a prediction error and not a tool error. The controller simply
accepts the stop.

Component to change: **controller termination check**. When a turn has no tool call, verify
completion before accepting; if incomplete, force the next tool call. Earlier attempt failed
because the check only ran on turns whose text contained a question mark or "confirm", so 8 of
the 10 failures skipped it.

## LongMemEval (500 questions)

F1 by question type, full context vs retrieval memory:

| Type | n | full | memory |
|---|---|---|---|
| single-session-user | 70 | 0.033 | **0.553** |
| single-session-assistant | 56 | 0.059 | **0.518** |
| knowledge-update | 78 | 0.034 | **0.455** |
| temporal-reasoning | 133 | 0.062 | **0.230** |
| multi-session | 133 | 0.022 | **0.118** |
| single-session-preference | 30 | 0.045 | 0.051 |

Weakest types: **multi-session (0.118)** and **temporal-reasoning (0.230)**. Single-session
types are strong. The retrieval step returns a flat top-k without session dates, so questions
that require joining sessions or resolving relative time are under-served.

Component to change: **retrieval**. Add session timestamps to the evidence and retrieve per
session for multi-session questions.

## LoCoMo (test split, 778 questions)

F1 by category, note-based memory:

| Category | n | F1 |
|---|---|---|
| 4 (open-domain) | 841 | 0.319 |
| 1 (single-hop) | 282 | 0.354 |
| 3 (multi-hop) | 96 | 0.239 |
| **2 (temporal)** | **321** | **0.097** |

Category 2 is the bottleneck: 321 questions at 0.097 pull the mean down by about 0.06.
The evidence lines carry no session date, and the answer prompt does not ask for a date.

Component to change: **evidence representation and answer prompt**. Prefix every retrieved
utterance with its session date and instruct the model to convert relative expressions
("last week") into explicit dates.

## Component-level conclusion

| Component | Failure it causes | Change |
|---|---|---|
| controller termination | 8/10 τ² failures | verify completion on every no-tool turn |
| retrieval representation | LME multi-session, LoCoMo temporal | session dates in evidence; per-session retrieval |
| predictor risk | gate over-blocks; repair replaces correct calls | keep it narrow (precondition / repeated failure), never terminate |
