#!/usr/bin/env bash
# ExpeL experiential-learning reproduction (references/expel) on HY3: tau2 retail then
# appworld. Accumulation gathers experiences (ReAct+Reflexion) then extracts a single
# revisable insight list; inference injects the insight list + top-k similar successful
# trajectories. Both phases run on HY3 (solver + reflection + extraction). Resumable via
# phase markers and the accumulation's own per-task checkpoints.
set -u
cd /data/workspace/PredictMem
PY=vendor/daedalus/.venv/bin/python
STAMP=$(date +%Y%m%d_%H%M%S)
LOG=logs/expel_$STAMP.log
MARK=logs/.mark_expel_$STAMP
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

log "===== ExpeL HY3 reproduction $STAMP ====="

phase tau2_expel_accumulation     $PY scripts/run.py expel_accumulation tau2
phase tau2_expel_inference        $PY scripts/run.py expel_inference tau2
phase appworld_expel_accumulation $PY scripts/run.py expel_accumulation appworld
phase appworld_expel_inference    $PY scripts/run.py expel_inference appworld

phase expel_collect $PY scripts/collect_full_results.py
log "===== EXPEL PIPELINE DISPATCHED ====="
