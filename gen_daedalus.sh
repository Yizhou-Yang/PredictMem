#!/bin/bash
cd /data/workspace/PredictMem
export OPENAI_BASE_URL=http://127.0.0.1:8743/v1 OPENAI_API_KEY=dummy
vendor/daedalus/.venv/bin/python -m daedalus.scripts.generation --config configs/hy4_tau2_generation.yaml > logs/hy4_tau2_generation.out 2>&1
vendor/daedalus/.venv/bin/python -m daedalus.scripts.inference --config configs/hy4_daedalus_tau2_retail.yaml > logs/hy4_daedalus_tau2.out 2>&1
