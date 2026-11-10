#!/bin/bash
# 14-hour watchdog: keep the hy4 experiment queue alive and add verification runs.
cd /data/workspace/PredictMem
END=$((SECONDS + 50400))
# delayed verification runs (hy4)
( sleep 14400; cd /tmp && PM_MODEL=openai/hy4-preview nohup /data/workspace/sw-venv/bin/python run_longmemeval.py 500 > /tmp/lme_recheck.out 2>&1 ) &
( sleep 21600; cd /tmp && PM_MODEL=openai/hy4-preview nohup /data/workspace/sw-venv/bin/python run_locomo.py 2000 > /tmp/locomo_recheck.out 2>&1 ) &
while [ $SECONDS -lt $END ]; do
  pgrep -f "run_tau2_v54.py" >/dev/null || nohup env PM_FAILMEM=1 PM_CONC=28 vendor/daedalus/.venv/bin/python run_tau2_v54.py >> logs/pm_tau2v54.out 2>&1 &
  pgrep -f "run_tau2_v53.py" >/dev/null || nohup env PM_CONC=20 vendor/daedalus/.venv/bin/python run_tau2_v53.py >> logs/pm_tau2v53.out 2>&1 &
  if ! pgrep -f "run_alfworld.py" >/dev/null; then
    (cd alfworld_pm && nohup ./run_stuck.sh pm > stuck_pm13.log 2>&1 &)
    (cd alfworld_pm && nohup ./run_stuck.sh base > stuck_base13.log 2>&1 &)
  fi
  sleep 300
done
