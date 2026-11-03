# PredictMem arm — harness integration

This directory contains the from-scratch PredictMem arm for the DAEDALUS/AppWorld harness.
It is copied here for review; the runnable copy lives in `vendor/daedalus/daedalus/benchmarks/appworld/predictmem/` on the experiment host.

## Target harness

- `vendor/daedalus` at the commit recorded in `sources.lock.json`
- PredictMem patch commit on the experiment host: `d1a687e659ae6d34ec8594b3cc8bb2eb28804c6f`
  ("add predictmem arm: predictor, surprise, store, gate, agent")
- Source lock must be updated to that commit before a verified run; the runner refuses a dirty
  or unlocked harness.

## Files added

```
daedalus/benchmarks/appworld/predictmem/
  __init__.py
  records.py      Prediction / Observation / EffectRecord, signatures
  config.py       (schema lives in daedalus/core/config.py for loader compatibility)
  store.py        versioned, deduped, capacity-bounded JSONL store
  surprise.py     semantic + LLM judge + execution mismatch
  retrieval.py    BM25 with confidence/recency weighting
  gate.py         warn / block with risk score
  predictor.py    structured LLM predictor and judge (JSON, fallback)
  agent.py        PredictMemReActAgent
  prompts/        predict.txt, judge.txt
```

## Patches to existing harness files

1. `daedalus/core/config.py`
   - add `PredictMemGateConfig`, `PredictMemAblationConfig`, `PredictMemConfig`
   - add field `predictmem: PredictMemConfig` to `ExperimentConfig`
   - build it in `config_from_dict`: `predictmem=PredictMemConfig.from_dict(data.get("predictmem"))`
   - keep exactly one `@dataclass` decorator on each class (insertion point is delicate;
     a duplicate/missing decorator makes `ExperimentConfig.to_dict()` leak a `LoggingConfig`
     object and breaks `yaml.safe_dump`)

2. `daedalus/benchmarks/appworld/agent.py`
   - add `_before_execute(code, messages, logger, turn_idx)` returning `(code, synthetic_observation|None)`
   - add `_after_execute(code, output, success, messages, logger, turn_idx)`
   - in `solve_task`, call `_before_execute` before `world.execute` and `_after_execute` after
   - defaults are no-ops, so baseline/ACE/ExpeL/DAEDALUS behavior is unchanged

3. `daedalus/benchmarks/appworld/runner.py`
   - in `build_agent`, dispatch to `PredictMemReActAgent` when `cfg.predictmem.enabled`

4. `scripts/run_verified_reproduction.py`
   - arm method list: add `("predictmem", 8)` (total worker budget is 24)
   - `prepare` whitelist: add `predictmem`
   - `make_config`: add the `predictmem:` block (enabled, models, thresholds, gate, ablation)
   - `freeze_bank` only for `ace|expel|memory`; PredictMem has no frozen bank

## Validity

- predictor and judge never see task success/verifier output
- per-task store by default (`shared_bank: false`); no cross-task leakage
- every record carries provenance (predictor/judge model) and a version/supersede chain
- ablations: `no_predictor`, `admit_all`, `no_versioning`, `no_gate`
- same harness, model, `max_turns=30`, task split as the other arms

## Smoke evidence

Single AppWorld train task (`82e2fac_1`):

- 1/1 success
- 10 turns -> 10 events
- 2 records admitted (surprise 0.73 and 0.60, threshold 0.55)
- gates: pass (max risk score 0.17 on this easy task)
- events: `run_0/predictmem/events.jsonl`, bank snapshot `82e2fac_1_bank.json`
