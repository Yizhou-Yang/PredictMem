#!/bin/bash
# 8-hour watchdog: keep the hy4 experiment queue alive.
cd /data/workspace/PredictMem
END=$((SECONDS + 28800))
while [ $SECONDS -lt $END ]; do
  pgrep -f "run_tau2_v54.py" >/dev/null || nohup env PM_FAILMEM=1 PM_CONC=28 vendor/daedalus/.venv/bin/python run_tau2_v54.py >> logs/pm_tau2v54.out 2>&1 &
  pgrep -f "run_tau2_v53.py" >/dev/null || nohup env PM_CONC=20 vendor/daedalus/.venv/bin/python run_tau2_v53.py >> logs/pm_tau2v53.out 2>&1 &
  if ! pgrep -f "run_alfworld.py" >/dev/null; then
    (cd alfworld_pm && nohup ./run_stuck.sh pm > stuck_pm13.log 2>&1 &)
    (cd alfworld_pm && nohup ./run_stuck.sh base > stuck_base13.log 2>&1 &)
  fi
  sleep 300
done
