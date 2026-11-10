#!/bin/bash
cd /data/workspace/PredictMem
END=$((SECONDS + 43200))
while [ $SECONDS -lt $END ]; do
  pgrep -f "run_tau2_b23ds.py" >/dev/null || (nohup env PM_BASE_URL=http://127.0.0.1:8745/v1 PM_CONC=8 vendor/daedalus/.venv/bin/python run_tau2_b23ds.py >> logs/base_tau2v23ds.out 2>&1 &)
  pgrep -f "run_tau2_v67ds.py" >/dev/null || (nohup env PM_BASE_URL=http://127.0.0.1:8745/v1 PM_CONC=8 vendor/daedalus/.venv/bin/python run_tau2_v67ds.py >> logs/pm_tau2v67ds.out 2>&1 &)
  pgrep -f "run_abl_full.py" >/dev/null || (nohup env PM_CONC=10 vendor/daedalus/.venv/bin/python run_abl_full.py >> logs/abl_full.out 2>&1 &)
  pgrep -f "run_abl_gate_pred.py" >/dev/null || (nohup env PM_CONC=10 vendor/daedalus/.venv/bin/python run_abl_gate_pred.py >> logs/abl_gate_pred.out 2>&1 &)
  if ! pgrep -f "run_alfworld.py" >/dev/null; then (cd alfworld_pm && nohup ./run_ds_alf.sh >> ds_alf_fs.log 2>&1 &); fi
  sleep 300
done
