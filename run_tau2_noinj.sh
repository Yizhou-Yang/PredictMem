#!/bin/bash
cd /data/workspace/PredictMem/vendor/daedalus
export OPENAI_BASE_URL=http://127.0.0.1:8743/v1 OPENAI_API_KEY=dummy
IDS=$(/data/workspace/PredictMem/vendor/daedalus/.venv/bin/python - <<PY
from tau2.runner import get_tasks
print(" ".join(t.id for t in get_tasks("retail", task_split_name="test") if t.id!="70"))
PY
)
for id in $IDS; do
  while [ "$(jobs -r | wc -l)" -ge 10 ]; do wait -n; done
  .venv/bin/python -m daedalus.scripts.inference \
    --config /data/workspace/PredictMem/configs/pm_tau2_noinj.yaml \
    --task-id "$id" --num-runs 5 --parallel 1 \
    --experiment-name "pm_tau2_noinj_t$id" >> "/data/workspace/PredictMem/logs/pm_tau2_noinj_t$id.log" 2>&1 &
done
wait
echo NOINJ_DONE
