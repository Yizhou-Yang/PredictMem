# PredictMem

An effect memory layer for long-horizon agents, and the harness that evaluates it.

An agent records what each action did: the tool result, the next observation, the answer the
evidence supports. PredictMem stores that effect, replays it on a repeated task or retrieves it as
evidence on a new one, and uses an independent predictor as a second opinion: when the predicted
effect agrees with the proposed action the controller commits, and when it disagrees the controller
expands the search once. It never abstains and never terminates on a disagreement.

## Layout

```
experiments_results/     every trace behind every number in the paper
sourcecode/              the memory layer and the evaluation harness
```

### `sourcecode/`

```
predictmem/              the memory layer, installable on its own
  core.py                  Prediction, Decision, EffectStore, PredictMem, agreement test
  qa.py                    QA adapter: independent answer prediction, agreement-gated expansion
  adapters.py              ProcedureRouter: predicted task/effect type -> procedure
  predict.py               Predictor: one interface, answer/effect prompts
  reuse.py                 skeleton replay + dated retrieval over the effect store
  controller.py            agreement commit, one-round expansion, never terminate
  benchmarks/qa.py         generic QA runner: question + pool + expand -> rows
  llm.py                   OpenAI-compatible client
tests/                   offline unit tests
examples/                runnable demos
configs/                 benchmark and arm configs
scripts/                 runners for tau2, ALFWorld, LongMemEval, LoCoMo
harness/                 agent patches and per-benchmark adapters
REPRODUCING.md           how to reproduce a run end to end
```

### `experiments_results/`

```
traces/hy4/             tau2 run dirs
traces/alfworld/hy4/    ALFWorld step logs
traces/memory/          LME and LoCoMo per-question rows
_paper/verify.py         recomputes every printed number from those traces
reports/                 failure analysis, iteration log, fair-split table
```

```bash
python3 experiments_results/_paper/verify.py
```

recomputes the main table in one pass and prints the share it reproduces (currently 12/12).

## Running it

```bash
cd sourcecode
pip install -r requirements.txt
export OPENAI_BASE_URL=<endpoint>/v1 OPENAI_API_KEY=<key>

python scripts/run_tau2_v63.py            # tau2 retail, replay arm
python scripts/run_tau2_v64.py            # tau2 airline + telecom
python scripts/run_locomo_predcommit.py   # LoCoMo: predictor agreement + expansion
```

`sourcecode/REPRODUCING.md` covers the full sequence.

## The memory layer on its own

```python
from predictmem import LLMClient, QAEngine

engine = QAEngine(LLMClient())
result = engine.answer("When did I adopt Pixie?", evidence, expand=lambda q: full_conversation)
print(result.answer, result.agreed, result.expanded)
```

Agent-side:

```python
from predictmem import Prediction
from predictmem.adapters import ProcedureRouter

router = ProcedureRouter(default="act")
router.register("clean", clean_procedure)
kind, action = router.run(Prediction(kind="clean"), instruction, observation)
```

## Design

**Effect, not lesson.** A record is `(state, action, predicted effect, observed effect, provenance)`.
Records are versioned by `(state, action)`; a later observation supersedes an earlier one.

**Reuse before prediction.** Same-task replay carries the gain on tool-use benchmarks; retrieval
carries it on the memory benchmarks. The predictor is a second opinion on top of reuse.

**Agreement is the commit signal.** The predictor produces an independent effect prediction from
the same evidence. Agreement commits; disagreement expands the search exactly once. The worst case
after an expansion is the base policy, so the layer cannot make an answer worse by construction.

**Measured.** On the LoCoMo test split, answers where the predictor and the policy agree score
0.573 F1 against 0.242 when they disagree, and agreement-gated expansion reaches 0.3534 versus
0.2256 for always-full context. tau2, ALFWorld and LongMemEval are reported against no memory and
against adapted ACE, ExpeL and DAEDALUS.

## Dependencies

`openai` for the client; `pytest` for the offline tests. The backend is any OpenAI-compatible chat
endpoint; no vendor CLI is required to reproduce a run.

## License

MIT, see `sourcecode/LICENSE`.
