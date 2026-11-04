"""Recompute the main table from the public traces.

Usage: python3 experiments_results/_paper/verify.py
"""

from __future__ import annotations

import glob
import json
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRACES = ROOT / "experiments_results"
TABLE = json.loads((Path(__file__).parent / "main_table.json").read_text())


def tau2_mean(pattern: str) -> float | None:
    values = []
    for path in glob.glob(str(TRACES / pattern / "evaluation.json")):
        data = json.loads(Path(path).read_text())
        rate = (data.get("aggregate") or {}).get("success_rate_mean")
        if rate is not None:
            values.append(float(rate))
    return statistics.mean(values) if values else None


def alf_rate(pattern: str) -> float | None:
    games = defaultdict(bool)
    for path in glob.glob(str(TRACES / pattern)):
        for line in Path(path).read_text().splitlines():
            try:
                row = json.loads(line)
            except Exception:
                continue
            games[(row.get("run"), row.get("game"))] |= bool(row.get("won"))
    return sum(games.values()) / len(games) if games else None


def qa_means(path: str) -> tuple[float, float] | None:
    rows = json.loads((TRACES / path).read_text())
    if not rows:
        return None
    base = statistics.mean(float(r.get("f1_base", 0)) for r in rows)
    mem = statistics.mean(float(r.get("f1_mem", 0)) for r in rows)
    return base, mem


def close(a: float | None, b: float, tol: float = 0.01) -> bool:
    return a is not None and abs(a - b) <= tol


def main() -> None:
    checked = matched = 0
    print(f"{'cell':32s} {'paper':>8s} {'trace':>8s}  status")
    for domain, row in TABLE["tau2"].items():
        base = tau2_mean(row["trace_base"])
        pm = tau2_mean(row["trace_pm"])
        for name, paper, trace in (("baseline", row["baseline"], base), ("pm", row["pm"], pm)):
            checked += 1
            ok = close(trace, paper / 100.0)
            matched += ok
            print(f"{domain + '/' + name:32s} {paper:8.1f} {0 if trace is None else trace * 100:8.1f}  {'ok' if ok else 'MISMATCH'}")
    for arm in ("baseline", "pm"):
        trace = alf_rate(TABLE["alfworld"][f"trace_{'base' if arm == 'baseline' else 'pm'}"])
        checked += 1
        ok = close(trace, TABLE["alfworld"][arm] / 100.0, 0.02)
        matched += ok
        print(f"{'alfworld/' + arm:32s} {TABLE['alfworld'][arm]:8.1f} {0 if trace is None else trace * 100:8.1f}  {'ok' if ok else 'MISMATCH'}")
    for bench in ("longmemeval", "locomo"):
        base_rows = json.loads((TRACES / TABLE[bench]["trace_base"]).read_text())
        pm_rows = json.loads((TRACES / TABLE[bench]["trace_pm"]).read_text())
        base = statistics.mean(float(r.get("f1_base", r.get("f1", 0))) for r in base_rows)
        pm = statistics.mean(float(r.get("f1_mem", r.get("f1", 0))) for r in pm_rows)
        for name, paper, trace in (("baseline", TABLE[bench]["baseline"], base), ("pm", TABLE[bench]["pm"], pm)):
            checked += 1
            ok = close(trace, paper, 0.01)
            matched += ok
            print(f"{bench + '/' + name:32s} {paper:8.4f} {trace:8.4f}  {'ok' if ok else 'MISMATCH'}")
    print(f"\nreproduced {matched}/{checked} cells ({matched / checked:.0%})")


if __name__ == "__main__":
    main()
