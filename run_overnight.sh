#!/usr/bin/env bash
# PredictMem overnight full benchmark: DAEDALUS HY3 reproduction.
# tau2 retail (priority) then appworld test_normal. Resumable via phase markers.
set -u
cd /data/workspace/PredictMem
PY=vendor/daedalus/.venv/bin/python
STAMP=$(date +%Y%m%d_%H%M%S)
LOG=logs/overnight_$STAMP.log
MARK=logs/.mark_$STAMP
mkdir -p logs

log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }

ensure_relay() {
  if curl -sf -m 5 http://127.0.0.1:8743/health >/dev/null 2>&1; then
    return 0
  fi
  log "relay down, restarting"
  bash run_relay.sh >> "$LOG" 2>&1
}

phase() {
  local name="$1"; shift
  local marker="$MARK.$name.done"
  if [ -f "$marker" ]; then log "SKIP $name (done)"; return 0; fi
  log ">>> START $name"
  ensure_relay
  local t0=$(date +%s)
  if "$@" >> "$LOG" 2>&1; then
    local dt=$(( $(date +%s) - t0 ))
    log "<<< DONE $name in ${dt}s"
    touch "$marker"
    return 0
  else
    local rc=$?
    log "<<< FAIL $name (exit $rc)"
    return $rc
  fi
}

log "===== PredictMem overnight benchmark $STAMP ====="
log "marker=$MARK"

phase tau2_generation   $PY scripts/run.py generation tau2
phase tau2_consolidate  $PY scripts/run.py consolidate tau2
phase tau2_baseline     $PY scripts/run.py baseline tau2
phase tau2_memory       $PY scripts/run.py memory tau2

phase appworld_generation   $PY scripts/run.py generation appworld
phase appworld_consolidate  $PY scripts/run.py consolidate appworld
phase appworld_baseline     $PY scripts/run.py baseline appworld
phase appworld_memory       $PY scripts/run.py memory appworld

phase collect_results $PY scripts/collect_full_results.py

log "===== ALL PHASES DISPATCHED ====="
