"""Export public-safe official smoke summaries; never turn unknown price into zero."""
import json
from pathlib import Path

from daedalus.core.config import load_config
from daedalus.core.logging.accounting import CostAccounting

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor" / "daedalus"


def main():
    result = {"scope": "train-only engineering smoke; not a leaderboard result",
              "full_reproduction_complete": False, "benchmarks": {}}
    for bench in ("appworld", "tau2"):
        d = VENDOR / "outputs" / "inference" / bench / "hy3-smoke" / f"hy3_{bench}_train_smoke"
        data = json.loads((d / "evaluation.json").read_text())
        usage = data["usage"]
        entry = {"split": "train", "aggregate": data["aggregate"], "per_run": [
                     {k: r.get(k) for k in ("num_tasks", "num_successes", "success_rate", "task_success")}
                     for r in data["per_run"]],
                 "usage": {k: usage.get(k) for k in (
                     "estimated_total_cost_usd", "provider_reported_total_cost_usd", "cost_complete",
                     "tokens_total", "calls_by_role", "num_completed_calls", "num_failed_without_usage")},
                 "source": str(d.relative_to(ROOT) / "evaluation.json")}
        if bench == "tau2":
            trace = json.loads((d / "run_0" / "0.json").read_text())
            entry["failure_diagnosis"] = {
                "termination_reason": trace["extra"]["termination_reason"],
                "official_reward": trace["evaluation"]["reward"],
                "observed": "HY3 user emitted STOP after confirmation before the solver executed exchange; no completed exchange write.",
                "attribution": "Solver repeatedly requested confirmation and simulator ended prematurely; single-case observation, not a general failure rate."}
        result["benchmarks"][bench] = entry
    for bench in ("appworld", "tau2"):
        d = VENDOR / "outputs" / "daedalus" / f"hy3_{bench}_generation_smoke"
        if not (d / "config.yaml").exists():
            continue
        cfg = load_config(d / "config.yaml")
        cfg.kind = "generation"
        cfg.cost_accounting.ledger_dir = str(d)
        acc = CostAccounting.for_worker(cfg)
        u = acc.summary()
        entry = {"usage": {k: u.get(k) for k in (
                      "estimated_total_cost_usd", "cost_complete", "tokens_total",
                      "calls_by_role", "num_completed_calls", "num_failed_without_usage")},
                 "coverage_survey_present": (d / "coverage_tags.txt").exists()}
        if (d / "run_summary.json").exists():
            summary = json.loads((d / "run_summary.json").read_text())
            entry["run_summary"] = {k: summary.get(k) for k in ("stage", "num_tasks", "num_heuristics")}
        result.setdefault("generation_smoke", {})[bench] = entry
    (ROOT / "results" / "smoke.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
