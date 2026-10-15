"""Collect the full HY3 reproduction of DAEDALUS and ACE: generation/accumulation,
consolidation, and paired eval.

Reads the official harness artifacts and writes a public-safe summary to
``results/full_benchmark.json``. Never turns an unknown price into zero. A paired
arm that has not finished is reported as ``status: missing/partial``, not as a
completed leaderboard number.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor" / "daedalus"


def _load(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _generation_entry(bench: str) -> dict:
    d = VENDOR / "outputs" / "daedalus" / f"hy3_{bench}_generation"
    summary = _load(d / "run_summary.json")
    if summary is None:
        return {"status": "missing"}
    usage = summary.get("usage", {})
    entry = {
        "status": "complete",
        "num_tasks": summary.get("num_tasks"),
        "num_heuristics": summary.get("num_heuristics"),
        "tokens_total": usage.get("tokens_total"),
        "num_completed_calls": usage.get("num_completed_calls"),
        "estimated_total_cost_usd": usage.get("estimated_total_cost_usd"),
        "cost_complete": usage.get("cost_complete"),
    }
    # Consolidation is a separate step; report it if present.
    pool = _load(d / "consolidated_pool.json")
    if isinstance(pool, dict) and "items" in pool:
        entry["consolidated_heuristics"] = len(pool["items"])
    elif isinstance(pool, list):
        entry["consolidated_heuristics"] = len(pool)
    return entry


def _eval_entry(bench: str, arm: str) -> dict:
    p = VENDOR / "outputs" / "inference" / bench / "hy3-reproduction" / f"hy3_{bench}_{arm}" / "evaluation.json"
    d = _load(p)
    if d is None:
        return {"status": "missing"}
    agg = d.get("aggregate", {})
    usage = d.get("usage", {})
    return {
        "status": "complete",
        "num_runs": agg.get("num_runs"),
        "num_tasks_per_run": agg.get("num_tasks_per_run"),
        "success_rate_mean": agg.get("success_rate_mean"),
        "success_rate_std": agg.get("success_rate_std"),
        "success_rate_se": agg.get("success_rate_se"),
        "success_rate_per_run": agg.get("success_rate_per_run"),
        "tokens_total": usage.get("tokens_total"),
        "num_completed_calls": usage.get("num_completed_calls"),
        "estimated_total_cost_usd": usage.get("estimated_total_cost_usd"),
        "cost_complete": usage.get("cost_complete"),
    }


def _delta(base: dict | None, mem: dict | None) -> dict | None:
    if not base or not mem:
        return None
    if base.get("status") != "complete" or mem.get("status") != "complete":
        return None
    b, m = base.get("success_rate_mean"), mem.get("success_rate_mean")
    if b is None or m is None:
        return None
    return {"baseline": b, "memory": m, "delta_pp": round(100.0 * (m - b), 3)}


def _ace_entry(bench: str) -> dict:
    """ACE playbook accumulation + playbook-conditioned inference."""
    acc_d = VENDOR / "outputs" / "baselines" / "ace" / "memory" / f"hy3_{bench}"
    summary = _load(acc_d / "run_summary.json")
    accumulation = {"status": "missing"}
    if summary is not None:
        usage = summary.get("usage", {})
        accumulation = {
            "status": "complete",
            "num_tasks": summary.get("num_tasks"),
            "num_bullets": summary.get("num_bullets"),
            "playbook_chars": summary.get("playbook_chars"),
            "tokens_total": usage.get("tokens_total"),
            "num_completed_calls": usage.get("num_completed_calls"),
            "estimated_total_cost_usd": usage.get("estimated_total_cost_usd"),
            "cost_complete": usage.get("cost_complete"),
        }
    ev = _load(VENDOR / "outputs" / "baselines" / "ace" / "inference" / f"hy3_{bench}" / "evaluation.json")
    if ev is None:
        inference = {"status": "missing"}
    else:
        agg = ev.get("aggregate", {})
        usage = ev.get("usage", {})
        inference = {
            "status": "complete",
            "num_runs": agg.get("num_runs"),
            "num_tasks_per_run": agg.get("num_tasks_per_run"),
            "success_rate_mean": agg.get("success_rate_mean"),
            "success_rate_std": agg.get("success_rate_std"),
            "success_rate_per_run": agg.get("success_rate_per_run"),
            "tokens_total": usage.get("tokens_total"),
            "num_completed_calls": usage.get("num_completed_calls"),
            "estimated_total_cost_usd": usage.get("estimated_total_cost_usd"),
            "cost_complete": usage.get("cost_complete"),
        }
    return {"accumulation": accumulation, "inference": inference}


def main() -> None:
    result = {
        "scope": "DAEDALUS + ACE reproduction on the HY3 backbone; not an official-model leaderboard result",
        "protocol": {
            "generation": "official self-play, train split; HY3 for solver/explorer/judge/simulator",
            "consolidation": "single strategy, HY3 high effort",
            "paired_eval": "baseline (no memory) vs memory (consolidated pool), test split, 5 repetitions (pass^5)",
            "ace": "Generator/Reflector/Curator playbook over train split (sequential, no success signal); "
                   "inference injects whole playbook, single attempt, 5 runs",
            "tau2_evaluator": "internal NL-assertions judge re-pointed to HY3 via explicit shim (self-evaluation arm)",
            "price": "unknown (HY3 has no local price record); null is not zero dollars",
        },
        "benchmarks": {},
    }
    for bench in ("tau2", "appworld"):
        base = _eval_entry(bench, "baseline")
        mem = _eval_entry(bench, "memory")
        ace = _ace_entry(bench)
        ace_inf = ace["inference"]
        result["benchmarks"][bench] = {
            "generation": _generation_entry(bench),
            "baseline": base,
            "memory": mem,
            "memory_minus_baseline": _delta(base, mem),
            "ace": ace,
            "ace_minus_baseline": _delta(base, ace_inf),
        }
    dest = ROOT / "results" / "full_benchmark.json"
    dest.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
