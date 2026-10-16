#!/usr/bin/env bash
# ACE offline-playbook reproduction (references/ace) on HY3: tau2 retail then appworld.
# Accumulation is the paper's sequential wave (parallel 1); inference is pass^5 parallel 6.
set -u
cd /data/workspace/PredictMem
PY=vendor/daedalus/.venv/bin/python
STAMP=$(date +%Y%m%d_%H%M%S)
LOG=logs/ace_$STAMP.log
MARK=logs/.mark_ace_$STAMP
mkdir -p logs

log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }

ensure_relay() {
  curl -sf -m 5 http://127.0.0.1:8743/health >/dev/null 2>&1 && return 0
  log "relay down, restarting"
  bash run_relay.sh >> "$LOG" 2>&1
}

phase() {
  local name="$1"; shift
  local marker="$MARK.$name.done"
  [ -f "$marker" ] && { log "SKIP $name (done)"; return 0; }
  log ">>> START $name"
  ensure_relay
  local t0=$(date +%s)
  if "$@" >> "$LOG" 2>&1; then
    log "<<< DONE $name in $(( $(date +%s) - t0 ))s"
    touch "$marker"
    return 0
  else
    log "<<< FAIL $name (exit $?)"
    return $?
  fi
}

log "===== ACE HY3 reproduction $STAMP ====="

phase tau2_ace_accumulation     $PY scripts/run.py ace_accumulation tau2
phase tau2_ace_inference        $PY scripts/run.py ace_inference tau2
phase appworld_ace_accumulation $PY scripts/run.py ace_accumulation appworld
phase appworld_ace_inference    $PY scripts/run.py ace_inference appworld

phase ace_collect $PY scripts/collect_full_results.py
log "===== ACE PIPELINE DISPATCHED ====="
