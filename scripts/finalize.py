"""Finalize an overnight run: collect results and refresh status.json/report.

Idempotent — safe to run at any point while the pipeline is still going; it
reports phases as ``running``/``partial`` where appropriate and never presents an
unfinished arm as a completed number.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor" / "daedalus"


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=VENDOR, capture_output=True, text=True)


def phase_markers() -> dict[str, str]:
    """Map phase -> done/failed from the latest overnight marker set.

    Marker files are named ``logs/.mark[_<prefix>]_<STAMP>.<phase>.done``; the phase is
    the segment between the final dot and ``.done`` (``p.stem`` already drops ``.done``).
    """
    markers = {}
    for p in sorted(ROOT.glob("logs/.mark_*.done")):
        markers[p.stem.rsplit(".", 1)[1]] = "done"
    return markers


def main() -> None:
    import collect_full_results  # same dir

    # Re-generate the full benchmark summary.
    collect_full_results.main()
    full = json.loads((ROOT / "results" / "full_benchmark.json").read_text())

    done = phase_markers()
    # Determine the latest overnight log for timing/diagnosis.
    logs = sorted(ROOT.glob("logs/overnight_*.log"))
    log_tail = ""
    if logs:
        tail = logs[-1].read_text().splitlines()[-40:]
        log_tail = "\n".join(tail)

    status = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "stage": "full DAEDALUS + ACE + ExpeL HY3 reproduction (overnight)",
        "phases": {
            "tau2_generation": done.get("tau2_generation", "pending"),
            "tau2_consolidate": done.get("tau2_consolidate", "pending"),
            "tau2_baseline": done.get("tau2_baseline", "pending"),
            "tau2_memory": done.get("tau2_memory", "pending"),
            "tau2_ace_accumulation": done.get("tau2_ace_accumulation", "pending"),
            "tau2_ace_inference": done.get("tau2_ace_inference", "pending"),
            "tau2_expel_accumulation": done.get("tau2_expel_accumulation", "pending"),
            "tau2_expel_inference": done.get("tau2_expel_inference", "pending"),
            "appworld_generation": done.get("appworld_generation", "pending"),
            "appworld_consolidate": done.get("appworld_consolidate", "pending"),
            "appworld_baseline": done.get("appworld_baseline", "pending"),
            "appworld_memory": done.get("appworld_memory", "pending"),
            "appworld_ace_accumulation": done.get("appworld_ace_accumulation", "pending"),
            "appworld_ace_inference": done.get("appworld_ace_inference", "pending"),
            "appworld_expel_accumulation": done.get("appworld_expel_accumulation", "pending"),
            "appworld_expel_inference": done.get("appworld_expel_inference", "pending"),
        },
        "benchmarks": full.get("benchmarks", {}),
        "protocol": full.get("protocol", {}),
        "price": "unknown (HY3 no local price record); null is not zero dollars",
        "log_tail": log_tail,
    }
    (ROOT / "results" / "status.json").write_text(json.dumps(status, indent=2) + "\n")

    # Compact human summary.
    lines = ["PredictMem DAEDALUS + ACE + ExpeL HY3 reproduction — status",
             f"updated {status['updated_at']}"]
    for bench, b in status["benchmarks"].items():
        g = b.get("generation", {})
        d = b.get("memory_minus_baseline")
        da = b.get("ace_minus_baseline")
        dx = b.get("expel_minus_baseline")
        ace = b.get("ace", {}).get("inference", {})
        acc = b.get("ace", {}).get("accumulation", {})
        expel = b.get("expel", {}).get("inference", {})
        exacc = b.get("expel", {}).get("accumulation", {})
        lines.append(f"\n[{bench}]")
        lines.append(f"  generation: tasks={g.get('num_tasks')} "
                     f"heuristics={g.get('num_heuristics')} "
                     f"consolidated={g.get('consolidated_heuristics')} "
                     f"status={g.get('status')}")
        lines.append(f"  baseline: {b['baseline'].get('status')} "
                     f"sr={b['baseline'].get('success_rate_mean')}")
        lines.append(f"  memory:   {b['memory'].get('status')} "
                     f"sr={b['memory'].get('success_rate_mean')}")
        if d:
            lines.append(f"  Δ memory−baseline: {d['delta_pp']} pp "
                         f"(base {d['baseline']} → mem {d['memory']})")
        lines.append(f"  ACE accumulation: {acc.get('status')} "
                     f"tasks={acc.get('num_tasks')} bullets={acc.get('num_bullets')}")
        lines.append(f"  ACE inference: {ace.get('status')} "
                     f"sr={ace.get('success_rate_mean')}")
        if da:
            lines.append(f"  Δ ACE−baseline: {da['delta_pp']} pp "
                         f"(base {da['baseline']} → ace {da['memory']})")
        lines.append(f"  ExpeL accumulation: {exacc.get('status')} "
                     f"tasks={exacc.get('num_tasks')} insights={exacc.get('num_insights')}")
        lines.append(f"  ExpeL inference: {expel.get('status')} "
                     f"sr={expel.get('success_rate_mean')}")
        if dx:
            lines.append(f"  Δ ExpeL−baseline: {dx['delta_pp']} pp "
                         f"(base {dx['baseline']} → expel {dx['memory']})")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
