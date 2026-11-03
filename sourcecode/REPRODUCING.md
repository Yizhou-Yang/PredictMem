# Reproducing the runs

## Install

```bash
cd sourcecode
pip install -r requirements.txt
pip install -e .
```

## Agent benchmarks (tau2, ALFWorld)

The public traces were produced with the PredictMem agent patch and the configs in `configs/`.
Each runner writes one directory per task under `outputs/inference/<benchmark>/<experiment>_<task>/`
with five runs and an `evaluation.json` produced by the official evaluator.

```bash
export OPENAI_BASE_URL=http://<endpoint>/v1
export OPENAI_API_KEY=<key>

python scripts/run_tau2_v63.py     # tau2 retail, replay arm
python scripts/run_tau2_v64.py     # tau2 airline + telecom
```

## Question-answering benchmarks

```bash
python scripts/run_locomo_bm25.py      # LoCoMo top-k retrieval
python scripts/run_locomo_predcommit.py  # predictor agreement + expansion
python scripts/run_lme_predict.py      # LongMemEval retrieval
```

## Numbers

```bash
python3 ../experiments_results/_paper/verify.py
```

recomputes the main-table values from the traces and prints the share it can reproduce. Values
whose trace is not in the public tree are reported as `unverified` rather than silently skipped.
