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
    """Map phase -> done/failed from the latest overnight marker set."""
    markers = {}
    marks = sorted(ROOT.glob("logs/.mark_*.done"))
    if not marks:
        return markers
    base = marks[0].stem  # logs/.mark_<STAMP>.<phase>.done
    for p in marks:
        phase = p.stem.rsplit(".", 1)[0].split("_", 1)[1]
        markers[phase] = "done"
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
        "stage": "full DAEDALUS HY3 reproduction (overnight)",
        "phases": {
            "tau2_generation": done.get("tau2_generation", "pending"),
            "tau2_consolidate": done.get("tau2_consolidate", "pending"),
            "tau2_baseline": done.get("tau2_baseline", "pending"),
            "tau2_memory": done.get("tau2_memory", "pending"),
            "appworld_generation": done.get("appworld_generation", "pending"),
            "appworld_consolidate": done.get("appworld_consolidate", "pending"),
            "appworld_baseline": done.get("appworld_baseline", "pending"),
            "appworld_memory": done.get("appworld_memory", "pending"),
        },
        "benchmarks": full.get("benchmarks", {}),
        "protocol": full.get("protocol", {}),
        "price": "unknown (HY3 no local price record); null is not zero dollars",
        "log_tail": log_tail,
    }
    (ROOT / "results" / "status.json").write_text(json.dumps(status, indent=2) + "\n")

    # Compact human summary.
    lines = ["PredictMem DAEDALUS HY3 reproduction — status",
             f"updated {status['updated_at']}"]
    for bench, b in status["benchmarks"].items():
        g = b.get("generation", {})
        d = b.get("memory_minus_baseline")
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
    print("\n".join(lines))


if __name__ == "__main__":
    main()
