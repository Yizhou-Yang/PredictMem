#!/bin/bash
cd /data/workspace/PredictMem
export OPENAI_BASE_URL=http://127.0.0.1:8743/v1 OPENAI_API_KEY=dummy
for dom in airline telecom; do
  # ACE bank
  vendor/daedalus/.venv/bin/python -m daedalus.scripts.accumulation --config configs/hy4_ace_${dom}_accum.yaml --max-tasks 40 --parallel 8 > logs/hy4_ace_${dom}_accum.out 2>&1
  # ACE inference with the generated playbook
  vendor/daedalus/.venv/bin/python -m daedalus.scripts.inference --config configs/hy4_ace_${dom}_infer.yaml > logs/hy4_ace_${dom}_infer.out 2>&1
done
