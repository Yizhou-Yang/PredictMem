#!/bin/bash
cd /data/workspace/PredictMem/vendor/daedalus
export OPENAI_BASE_URL=http://127.0.0.1:8743/v1 OPENAI_API_KEY=dummy
for id in 36 38 39 40 45 60 62 68 108 111; do
  while [ "$(jobs -r | wc -l)" -ge 4 ]; do wait -n; done
  .venv/bin/python -m daedalus.scripts.inference \
    --config /data/workspace/PredictMem/configs/pm_tau2_controller.yaml \
    --task-id "$id" --num-runs 5 --parallel 1 \
    --experiment-name "pm_tau2_t$id" >> "/data/workspace/PredictMem/logs/pm_tau2_t$id.log" 2>&1 &
done
wait
echo MISSING_DONE
