#!/bin/bash
cd /data/workspace/PredictMem/vendor/daedalus
export OPENAI_BASE_URL=http://127.0.0.1:8743/v1 OPENAI_API_KEY=dummy
exec .venv/bin/python -m daedalus.scripts.inference --config /data/workspace/PredictMem/configs/pm_tau2_no70.yaml --experiment-name pm_tau2_run0 --num-runs 1 --parallel 4
