#!/bin/bash
cd /data/workspace/PredictMem
END=$((SECONDS + 43200))   # 12h
while [ $SECONDS -lt $END ]; do
  pgrep -f "run_expel_alf.sh" >/dev/null || (cd /data/workspace/alfworld_pm && nohup ./run_expel_alf.sh >> expelalf.log 2>&1 &)
  pgrep -f "run_daedalus_alf.sh" >/dev/null || (cd /data/workspace/alfworld_pm && nohup ./run_daedalus_alf.sh >> daedalusalf.log 2>&1 &)
  pgrep -f "lme_ace_adapt" >/dev/null || (cd /tmp && nohup bash -c "for m in ace expel daedalus; do /data/workspace/sw-venv/bin/python lme_ace_adapt.py \$m; done" >> /tmp/lme_competitors.out 2>&1 &)
  pgrep -f "locomo_ace_adapt" >/dev/null || (cd /tmp && nohup bash -c "for m in ace expel daedalus; do /data/workspace/sw-venv/bin/python locomo_ace_adapt.py \$m; done" >> /tmp/locomo_competitors.out 2>&1 &)
  pgrep -f "queue_daedalus_domains.sh" >/dev/null || (cd /data/workspace/PredictMem && nohup ./queue_daedalus_domains.sh >> logs/queue_daedalus_domains.log 2>&1 &)
  sleep 600
done
