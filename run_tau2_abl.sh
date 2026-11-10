#!/bin/bash
cd /data/workspace/PredictMem/vendor/daedalus
export OPENAI_BASE_URL=http://127.0.0.1:8743/v1 OPENAI_API_KEY=dummy
CFG=$1; EXP=$2
IDS=$(/data/workspace/PredictMem/vendor/daedalus/.venv/bin/python - <<PY
from tau2.runner import get_tasks
print(" ".join(t.id for t in get_tasks("retail", task_split_name="test") if t.id!="70"))
PY
)
for id in $IDS; do
  while [ "$(jobs -r | wc -l)" -ge 10 ]; do wait -n; done
  .venv/bin/python -m daedalus.scripts.inference --config "$CFG" --task-id "$id" --num-runs 5 --parallel 1 --experiment-name "${EXP}_t$id" >> "/data/workspace/PredictMem/logs/${EXP}_t$id.log" 2>&1 &
done
wait
echo ABL_DONE
