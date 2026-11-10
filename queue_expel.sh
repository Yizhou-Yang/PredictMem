#!/bin/bash
cd /data/workspace/PredictMem
export OPENAI_BASE_URL=http://127.0.0.1:8743/v1 OPENAI_API_KEY=dummy
for dom in airline telecom; do
  vendor/daedalus/.venv/bin/python -m daedalus.scripts.accumulation --config configs/hy4_expel_${dom}_accum.yaml --max-tasks 40 --parallel 8 > logs/hy4_expel_${dom}_accum.out 2>&1
done
