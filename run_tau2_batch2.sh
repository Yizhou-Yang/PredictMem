#!/bin/bash
cd /data/workspace/PredictMem/vendor/daedalus
export OPENAI_BASE_URL=http://127.0.0.1:8743/v1 OPENAI_API_KEY=dummy
EXP=pm_tau2_batch2
DIR=outputs/inference/tau2/predictmem/$EXP
count() { find "$DIR"/run_* -maxdepth 1 -name "*.json" 2>/dev/null | wc -l; }
for i in $(seq 1 60); do
  n=$(count)
  echo "batch $i start, traces=$n"
  [ "$n" -ge 200 ] && { echo DONE; break; }
  .venv/bin/python -m daedalus.scripts.inference \
    --config /data/workspace/PredictMem/configs/pm_tau2_controller.yaml \
    --experiment-name "$EXP" --num-runs 5 --parallel 4 --max-tasks 5 >> /data/workspace/PredictMem/logs/pm_tau2_batch2.log 2>&1 || true
done
