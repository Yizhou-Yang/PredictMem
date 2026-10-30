# Unified PredictMem core

One method, four adapters. Every benchmark step is mapped to the same loop:

```
action --predict--> Prediction(expected_effect, risk, confidence)
       --controller--> Decision(commit | fallback)
```

`daedalus/predictmem/core.py` defines `Prediction`, `Decision`, `Controller`, and the
`PredictMem` facade. A benchmark adapter only supplies:

1. the action representation,
2. the effect representation,
3. the fallback action (`veto` / `retry` / `abstain` / `clarify`).

## Adapters

| Benchmark | action | effect | fallback | ablation arms |
|---|---|---|---|---|
| τ² | tool call | next observation / state change | veto on destructive calls | full / replay-only / gate-only |
| ALFWorld | text command | next observation | gate (can disable) | full / no-predictor / no-memory |
| LongMemEval | answer | evidence support for the answer | abstain (`Unknown`) | full / retrieval-only / no-controller |
| LoCoMo | answer | evidence support for the answer | abstain | full / retrieval-only |

## What is shared vs adapted

Shared: risk threshold ε, commit/fallback semantics, effect records with provenance,
ablation switches.

Adapted: only the predictor prompt and the fallback action, because "what an effect is"
differs between a tool-call environment and a question-answering task.

## Ablation contract

Every benchmark must report at least:

- `full` (store + predictor + controller)
- `no predictor` (store + controller with risk=0)
- `no controller` (always commit)
- `no memory` (no retrieval/replay)

This is what makes the component claims comparable across columns.
