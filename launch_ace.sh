#!/usr/bin/env bash
cd /data/workspace/PredictMem
mkdir -p logs
setsid nohup bash run_ace_overnight.sh > logs/ace_launcher.log 2>&1 < /dev/null &
echo "launched_ace_pid=$!"
sleep 2
cat logs/ace_launcher.log
