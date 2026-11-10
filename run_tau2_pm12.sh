#!/bin/bash
cd /data/workspace/PredictMem/vendor/daedalus
export OPENAI_BASE_URL=http://127.0.0.1:8743/v1 OPENAI_API_KEY=dummy
exec .venv/bin/python -m daedalus.scripts.inference --config /tmp/pm_tau2_smoke.yaml --experiment-name pm_tau2_full3 --num-runs 5 --parallel 12
