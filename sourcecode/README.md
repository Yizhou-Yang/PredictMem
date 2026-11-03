# PredictMem SDK

Effect memory with an independent predictor for long-horizon agents.

The SDK exposes one decision loop. A predictor independently predicts the effect of a proposed
action; the controller commits when the predicted effect agrees with the proposal, and expands
the search once when it does not. It never abstains and never terminates.

## Install

```bash
pip install -e sdk            # from the repository root
```

## Quick start: question answering

```python
from predictmem import LLMConfig, LLMClient, QAEngine

client = LLMClient(LLMConfig(model="gpt-4o-mini", api_key="..."))
engine = QAEngine(client)

evidence = "session 1 (2023-04-02): I adopted Pixie. session 2 (2023-06-11): I went climbing."

def expand(question):
    # return a wider evidence window (full conversation, more sessions, ...)
    return full_conversation

result = engine.answer("When did I adopt Pixie?", evidence, expand=expand)
print(result.answer, result.agreed, result.expanded)
```

`result.agreed` is the calibration signal: on the LoCoMo test split, answers where the predictor
and the policy agree score 0.573 F1, against 0.242 when they disagree.

## Quick start: agent procedures

```python
from predictmem import Prediction
from predictmem.adapters import ProcedureRouter

router = ProcedureRouter(default="act")
router.register("clean", clean_procedure)
router.register("heat", heat_procedure)

name, action = router.run(Prediction(kind="clean", expected_effect="sink activated"), instruction, observation)
```

## Effect memory

```python
from predictmem import EffectRecord, EffectStore

store = EffectStore("effects.jsonl")
store.add(EffectRecord(state="order 123", action="refund(123)", predicted="refunded", observed="refunded"))
store.search("refund order 123")
```

Records are versioned by `(state, action)`; a later observation supersedes the earlier one.

## Components

| Module | Purpose |
|---|---|
| `predictmem.core` | `Prediction`, `Decision`, `EffectStore`, `PredictMem`, `agree` |
| `predictmem.llm` | OpenAI-compatible client (`temperature=0.0`) |
| `predictmem.qa` | `QAEngine`: predict answer, answer, agreement-gated expansion |
| `predictmem.adapters` | `ProcedureRouter`: predicted type to procedure |

## Design notes

- The predictor must be **independent** of the policy: same evidence, different prompt.
- Agreement is the commit signal; disagreement triggers exactly one expansion.
- The worst case after an expansion is the base policy, so the layer cannot make an answer
  worse by construction.
- `temperature=0.0` is the default for reproducible evaluation.

## Tests

```bash
pip install -e ".[dev]"
pytest -q sdk/tests
```
