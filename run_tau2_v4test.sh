#!/bin/bash
cd /data/workspace/PredictMem/vendor/daedalus
export OPENAI_BASE_URL=http://127.0.0.1:8743/v1 OPENAI_API_KEY=dummy
for id in 65 68 71 74 77 79 86 90 94 97; do
  while [ "$(jobs -r | wc -l)" -ge 3 ]; do wait -n; done
  .venv/bin/python -m daedalus.scripts.inference --config /data/workspace/PredictMem/configs/pm_tau2_retail.yaml --task-id "$id" --num-runs 5 --parallel 1 --experiment-name "pm_tau2v4_retail_t$id" >> "/data/workspace/PredictMem/logs/pm_tau2v4_t$id.log" 2>&1 &
done
wait
echo V4_DONE
