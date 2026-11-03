#!/usr/bin/env bash
# Finalize the PredictMem overnight benchmark: collect on any4, pull results,
# commit and push to GitHub. Idempotent; safe while the pipeline is still running.
set -euo pipefail
cd /Users/yizhouyang/WorkBuddy/2026-10-08-16-40-15/PredictMem
REMOTE=any4
R=/data/workspace/PredictMem

log() { echo "[$(date '+%H:%M:%S')] $*"; }

log "=== overnight phase markers ==="
ssh -o ConnectTimeout=20 "$REMOTE" "ls -1 $R/logs/.mark_*.done 2>/dev/null || echo '(none yet)'"

log "=== finalize (collect + status) on any4 ==="
ssh -o ConnectTimeout=20 "$REMOTE" "cd $R && CUDA_VISIBLE_DEVICES=-1 PYTHONDONTWRITEBYTECODE=1 vendor/daedalus/.venv/bin/python scripts/finalize.py > logs/finalize_push.log 2>&1"

log "=== pull result files to local ==="
mkdir -p results
for f in full_benchmark.json status.json; do
  scp "$REMOTE:$R/results/$f" "results/$f"
  log "pulled results/$f"
done
scp "$REMOTE:$R/reproduction_protocol.json" reproduction_protocol.json

log "=== commit + push ==="
git add results/ reproduction_protocol.json scripts/ run_*.sh run_relay.sh finalize_and_push.sh
if git diff --cached --quiet; then
  log "nothing new to commit"
else
  git commit -q -m "Correct reproduction audit: withdraw partial deltas and enforce terminal acceptance"
fi
git push origin main
log "=== DONE ==="
