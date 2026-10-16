#!/usr/bin/env bash
# Finalize the PredictMem overnight benchmark: collect on any4, pull results,
# commit and push to GitHub. Idempotent; safe while the pipeline is still running.
set -uo pipefail
cd /Users/yizhouyang/WorkBuddy/2026-10-08-16-40-15/PredictMem
REMOTE=any4
R=/data/workspace/PredictMem

log() { echo "[$(date '+%H:%M:%S')] $*"; }

log "=== overnight phase markers ==="
ssh -o ConnectTimeout=20 "$REMOTE" "ls -1 $R/logs/.mark_*.done 2>/dev/null || echo '(none yet)'"

log "=== finalize (collect + status) on any4 ==="
ssh -o ConnectTimeout=20 "$REMOTE" "cd $R && vendor/daedalus/.venv/bin/python scripts/finalize.py 2>&1" \
  || log "WARN: finalize.py reported an error; still pulling whatever exists"

log "=== pull result files to local ==="
mkdir -p results
for f in full_benchmark.json status.json environment.json hy3_transport_probe.json smoke.json; do
  ssh -o ConnectTimeout=20 "$REMOTE" "cat $R/results/$f 2>/dev/null" > "results/$f" \
    && log "pulled results/$f" || log "skip results/$f (missing)"
done
ssh -o ConnectTimeout=20 "$REMOTE" "cat $R/reproduction_protocol.json 2>/dev/null" > reproduction_protocol.json \
  && log "pulled reproduction_protocol.json" || log "skip reproduction_protocol.json"

log "=== commit + push ==="
git add results/ reproduction_protocol.json scripts/ run_*.sh run_relay.sh finalize_and_push.sh
if git diff --cached --quiet; then
  log "nothing new to commit"
else
  git commit -q -m "Overnight DAEDALUS + ACE + ExpeL HY3 reproduction: results + status" || log "WARN: commit failed"
fi
git push origin main 2>&1 | tail -3 || log "WARN: push failed (may need credentials)"
log "=== DONE ==="
