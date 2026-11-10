#!/usr/bin/env bash
cd /data/workspace/PredictMem
mkdir -p logs
setsid nohup bash run_overnight.sh > logs/launcher.log 2>&1 < /dev/null &
echo "launched_pid=$!"
sleep 2
echo "--- launcher.log ---"
cat logs/launcher.log
