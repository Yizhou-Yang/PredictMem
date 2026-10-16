#!/usr/bin/env bash
# RETIRED: this legacy script assumed lower concurrency and trace existence fixed
# truncation/resume. Audit disproved both assumptions. Keep for provenance only.
# Use a fresh independent namespace with runtime_safety and terminal verification.
exit 2
set -u
cd /data/workspace/PredictMem
PY=vendor/daedalus/.venv/bin/python
STAMP=$(date +%Y%m%d_%H%M%S)
LOG=logs/rerun_$STAMP.log
MARK=logs/.mark_rerun_$STAMP
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

log "===== repair rerun $STAMP ====="

# ExpeL inference: never ran (missing dependency), so both benchmarks in full.
phase tau2_expel_inference     $PY scripts/run.py expel_inference tau2
phase appworld_expel_inference $PY scripts/run.py expel_inference appworld

# AppWorld repeats: fill in the task-runs that were truncated at parallel 24.
phase appworld_baseline        $PY scripts/run.py baseline appworld
phase appworld_memory          $PY scripts/run.py memory appworld
phase appworld_ace_inference   $PY scripts/run.py ace_inference appworld

phase rerun_collect $PY scripts/collect_full_results.py
log "===== REPAIR RERUN DISPATCHED ====="
