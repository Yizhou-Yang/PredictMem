"""Refresh public audited status; process exit markers never prove task completion."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def phase_markers():
    markers = {}
    for path in sorted(ROOT.glob("logs/.mark_*.done")):
        markers[path.stem.rsplit(".", 1)[1]] = "process_returned_zero_only"
    return markers


def main():
    import collect_full_results
    collect_full_results.main()
    full = json.loads((ROOT / "results/full_benchmark.json").read_text())
    phases = {}
    for bench, data in full["benchmarks"].items():
        phases[f"{bench}_generation"] = data["generation"]["status"]
        phases[f"{bench}_consolidate"] = (
            "artifact_present_unverified" if data["generation"].get("consolidated_heuristics") is not None else "missing"
        )
        for arm in ("baseline", "memory"):
            phases[f"{bench}_{arm}"] = data[arm]["status"]
        for method in ("ace", "expel"):
            for stage in ("accumulation", "inference"):
                phases[f"{bench}_{method}_{stage}"] = data[method][stage]["status"]
    status = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "stage": "Audit correction; no original-paper reproduction claim",
        "phases": phases,
        "legacy_process_markers_not_acceptance": phase_markers(),
        "benchmarks": full["benchmarks"], "protocol": full["protocol"],
        "price": "unknown/null, not zero dollars",
    }
    (ROOT / "results/status.json").write_text(json.dumps(status, indent=2) + "\n")
    for bench, data in full["benchmarks"].items():
        print(f"[{bench}] generation={data['generation']['status']}")
        for arm, value in [("baseline", data["baseline"]), ("memory", data["memory"]),
                           ("ace", data["ace"]["inference"]), ("expel", data["expel"]["inference"])]:
            print(f"  {arm}: {value['status']}; counts={value['num_tasks_per_run_all']}; raw MSR={value['success_rate_mean']}; terminal={value['terminal_completion_verified']}")


if __name__ == "__main__":
    main()
