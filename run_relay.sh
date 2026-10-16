#!/usr/bin/env bash
# Start (or restart) the loopback HY3 relay. Idempotent.
set -e
cd /data/workspace/PredictMem
mkdir -p logs
pkill -f "scripts/relay.py" 2>/dev/null || true
sleep 1
export HY3_UPSTREAM_URL="http://api.taiji.woa.com/openapi/v2/chat/completions"
export HY3_KEY_FILE="/data/workspace/g2audit/.taiji_key"
export HY3_RELAY_PORT=8743
setsid nohup vendor/daedalus/.venv/bin/python scripts/relay.py > logs/relay.log 2>&1 < /dev/null &
sleep 3
if curl -sf -m 5 http://127.0.0.1:8743/health > /dev/null; then
  echo "RELAY_OK $(curl -s -m 5 http://127.0.0.1:8743/health)"
else
  echo "RELAY_FAIL"; cat logs/relay.log; exit 1
fi
