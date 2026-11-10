#!/bin/bash
cd /data/workspace/PredictMem
export OPENAI_BASE_URL=http://127.0.0.1:8743/v1 OPENAI_API_KEY=dummy
for dom in airline telecom; do
  d=outputs/daedalus/hy4_tau2_generation_${dom}
  vendor/daedalus/.venv/bin/python -m daedalus.scripts.generation --config configs/hy4_tau2_generation_${dom}.yaml > logs/hy4_tau2_generation_${dom}.out 2>&1
  vendor/daedalus/.venv/bin/python -m daedalus.scripts.consolidate ${d} --output ${d}/consolidated_pool.json --model openai/hy4-preview --strategy single > logs/hy4_consolidate_${dom}.out 2>&1
  vendor/daedalus/.venv/bin/python -m daedalus.scripts.inference --config configs/hy4_daedalus_${dom}.yaml > logs/hy4_daedalus_${dom}.out 2>&1
done
