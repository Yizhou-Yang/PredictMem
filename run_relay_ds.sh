#!/usr/bin/env bash
set -e
cd /data/workspace/PredictMem
pkill -f "HY3_RELAY_PORT=8745" 2>/dev/null || true
export HY3_UPSTREAM_URL="https://api.deepseek.com/v1/chat/completions"
export HY3_KEY_FILE="/data/workspace/g2audit/.deepseek_key"
export HY3_RELAY_PORT=8745
export HY3_RELAY_AUDIT_LOG="/data/workspace/PredictMem/logs/relay_ds_audit.jsonl"
setsid nohup vendor/daedalus/.venv/bin/python scripts/relay.py > logs/relay_ds.log 2>&1 < /dev/null &
sleep 3
curl -sf -m 5 http://127.0.0.1:8745/health && echo RELAY_DS_OK
