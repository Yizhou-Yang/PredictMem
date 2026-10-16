"""Public-safe HY3 audit. Coverage, terminal completion and fidelity are separate.

Legacy artifacts are retained as observations, never promoted by file existence.
Only full official task sets with SHA-bound completion markers admit paired deltas.
All data collection runs on any4 CPU, without model/API calls.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor" / "daedalus"
EXPECTED_RUNS = 5
EXPECTED_TASKS = {"tau2": 40, "appworld": 168}
EXPECTED_TRAIN = {"tau2": 74, "appworld": 90}


def _load(path: Path):
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _usage(summary):
    usage = (summary or {}).get("usage", {})
    return {k: usage.get(k) for k in (
        "tokens_total", "num_completed_calls", "estimated_total_cost_usd", "cost_complete"
    )}


def _official_ids(bench):
    """Read the exact pinned split files; do not import or invoke an evaluator."""
    if bench == "appworld":
        path = VENDOR / "data/datasets/test_normal.txt"
        ids = [line.strip().split(":")[0] for line in path.read_text().splitlines() if line.strip()]
    else:
        path = VENDOR / "benchmarks/tau2-bench/data/tau2/domains/retail/split_tasks.json"
        ids = [str(t) for t in json.loads(path.read_text())["test"]]
    if len(ids) != EXPECTED_TASKS[bench] or len(set(ids)) != len(ids):
        raise ValueError(f"Invalid pinned {bench} test split")
    return set(ids), hashlib.sha256(path.read_bytes()).hexdigest()


def _evaluate_snapshot(data, bench, directory, expected_ids=None):
    """Coverage is necessary, but default success/evaluation fields are not terminal proof."""
    from runtime_safety import task_is_complete

    ids, split_hash = _official_ids(bench) if expected_ids is None else (set(expected_ids), None)
    runs = (data or {}).get("per_run", [])
    agg = (data or {}).get("aggregate", {})
    counts, per_run, issues = [], [], []
    fully_scored = data is not None and len(runs) == EXPECTED_RUNS
    terminal_complete = fully_scored
    for index in range(EXPECTED_RUNS):
        run = runs[index] if index < len(runs) else {}
        scored = run.get("task_success", {})
        seen = set(scored)
        valid_scores = isinstance(scored, dict) and all(type(v) is bool for v in scored.values())
        count = run.get("num_tasks", 0)
        counts.append(count)
        missing = sorted(ids - seen)
        extra = sorted(seen - ids)
        coverage = count == len(ids) and seen == ids and valid_scores
        fully_scored = fully_scored and coverage
        unverified = []
        score_mismatches = []
        for tid in sorted(seen):
            trace = Path(directory) / f"run_{index}" / f"{tid}.json"
            if not task_is_complete(trace, tid):
                unverified.append(tid)
            else:
                payload = _load(trace)
                if payload.get("success") != scored[tid]:
                    score_mismatches.append(tid)
        terminal_complete = terminal_complete and coverage and not unverified and not score_mismatches
        per_run.append({
            "run_index": index, "num_scored_tasks": count,
            "missing_task_ids": missing, "extra_task_ids": extra,
            "unverified_terminal_task_ids": unverified,
            "score_trace_mismatches": score_mismatches,
            "official_task_coverage_complete": coverage,
        })
    if len(runs) != EXPECTED_RUNS:
        issues.append(f"Expected {EXPECTED_RUNS} runs, observed {len(runs)}")
    if not fully_scored:
        issues.append("Official task coverage incomplete; aggregate is diagnostic only")
    if not terminal_complete:
        issues.append("Missing terminal completion evidence; trace existence/default success is insufficient")
    if agg.get("num_runs") != len(runs):
        fully_scored = terminal_complete = False
        issues.append("Aggregate/per-run run count mismatch")
    if agg.get("num_tasks_per_run_all") not in (None, counts[:len(runs)]):
        fully_scored = terminal_complete = False
        issues.append("Aggregate/per-run denominator mismatch")
    if agg.get("unequal_denominators"):
        fully_scored = terminal_complete = False
        issues.append("Harness reports unequal denominators")
    if data is None:
        status = "partial" if Path(directory).exists() else "missing"
    elif terminal_complete:
        status = "complete"
    elif fully_scored:
        status = "scored_complete_unverified"
    else:
        status = "partial"
    raw_trace_counts = []
    for index in range(EXPECTED_RUNS):
        traces = [_load(p) for p in (Path(directory) / f"run_{index}").glob("*.json")]
        raw_trace_counts.append(len({str(t["task_id"]) for t in traces
                                     if isinstance(t, dict) and "task_id" in t and str(t["task_id"]) in ids}))
    result = {
        "status": status,
        "raw_trace_count_per_run_not_terminal_proof": raw_trace_counts,
        "evaluation_snapshot_exists": data is not None,
        "method_fidelity": "not_validated",
        "eligible_for_formal_comparison": terminal_complete,
        "expected_runs": EXPECTED_RUNS, "expected_tasks_per_run": len(ids),
        "official_split_sha256": split_hash,
        "num_runs": agg.get("num_runs"),
        "num_tasks_per_run": agg.get("num_tasks_per_run"),
        "num_tasks_per_run_all": counts[:len(runs)],
        "unequal_denominators": agg.get("unequal_denominators"),
        "official_task_coverage_complete": fully_scored,
        "terminal_completion_verified": terminal_complete,
        "issues": issues, "per_run_audit": per_run,
        "success_rate_mean": agg.get("success_rate_mean"),
        "success_rate_std": agg.get("success_rate_std"),
        "success_rate_se": agg.get("success_rate_se"),
        "success_rate_per_run": agg.get("success_rate_per_run"),
        "observed_pass_pow_5": agg.get("pass_hat_k", {}).get("pass^5"),
        "observed_pass_at_5": agg.get("pass_at_k", {}).get("pass@5"),
        "metric_scope": "official complete task set" if terminal_complete else "raw observation only; not an accepted protocol score",
        **_usage(data),
    }
    return result


def _eval_entry(bench, arm):
    directory = VENDOR / "outputs/inference" / bench / "hy3-reproduction" / f"hy3_{bench}_{arm}"
    return _evaluate_snapshot(_load(directory / "evaluation.json"), bench, directory)


def _item_count(data):
    return len(data.get("items", [])) if isinstance(data, dict) else len(data) if isinstance(data, list) else None


def _generation_entry(bench):
    directory = VENDOR / "outputs/daedalus" / f"hy3_{bench}_generation"
    if not directory.exists():
        return {"status": "missing"}
    summary = _load(directory / "run_summary.json")
    bank = _load(directory / "tasks.json") or {}
    records, invalid, mismatch = {}, [], []
    for path in sorted((directory / "sessions").glob("session_*.json")):
        match = re.fullmatch(r"session_(\d+)\.json", path.name)
        if not match:
            continue
        index = int(match.group(1))
        value = _load(path)
        if not isinstance(value, dict):
            invalid.append(path.name)
            continue
        records[index] = value
        if value.get("session_index") != index:
            mismatch.append(index)
    expected = set(range(EXPECTED_TRAIN[bench]))
    errors = sorted(i for i, value in records.items() if value.get("kind") == "session_error")
    normal = {i for i, value in records.items() if value.get("result") in
              ("banked", "too_easy", "too_hard", "no_task", "near_duplicate")}
    complete = set(records) == expected and normal == expected and not invalid and not mismatch
    return {
        "status": "complete" if complete and summary else "partial",
        "expected_sessions": len(expected), "num_session_records": len(records),
        "num_normal_terminal_sessions": len(normal),
        "missing_session_indices": sorted(expected - set(records)),
        "extra_session_indices": sorted(set(records) - expected),
        "session_error_indices": errors, "invalid_session_files": invalid,
        "session_index_mismatches": mismatch,
        "result_counts": dict(Counter(v.get("result", "session_error") for v in records.values())),
        "all_sessions_completed_without_error": complete,
        "claimed_next_session": bank.get("next_session"),
        "num_tasks": len(bank.get("tasks", [])),
        "num_heuristics": _item_count(_load(directory / "pool.json")),
        "consolidated_heuristics": _item_count(_load(directory / "consolidated_pool.json")),
        "run_summary_exists": summary is not None,
        "method_fidelity": "not_validated", **_usage(summary),
    }


def _reference_entry(bench, method):
    acc_dir = VENDOR / f"outputs/baselines/{method}/memory/hy3_{bench}"
    summary = _load(acc_dir / "run_summary.json")
    accumulation = {"status": "partial" if acc_dir.exists() else "missing"}
    if summary:
        accumulation = {
            "status": "summary_reported_complete_unverified" if summary.get("num_tasks") == EXPECTED_TRAIN[bench] else "partial",
            "expected_train_tasks": EXPECTED_TRAIN[bench],
            "method_fidelity": "not_validated",
            **{key: summary.get(key) for key in ("num_tasks", "num_bullets", "playbook_chars", "num_solved", "num_insights", "num_demonstrations")},
            **_usage(summary),
        }
    ev_dir = VENDOR / f"outputs/baselines/{method}/inference/hy3_{bench}"
    return {"accumulation": accumulation,
            "inference": _evaluate_snapshot(_load(ev_dir / "evaluation.json"), bench, ev_dir)}


def _delta(base, memory):
    if not all(value.get("eligible_for_formal_comparison") is True
               and value.get("method_fidelity") == "validated"
               for value in (base, memory)):
        return None
    if base.get("official_split_sha256") != memory.get("official_split_sha256"):
        return None
    if base.get("success_rate_mean") is None or memory.get("success_rate_mean") is None:
        return None
    return {"baseline": base["success_rate_mean"], "memory": memory["success_rate_mean"],
            "delta_pp": round(100 * (memory["success_rate_mean"] - base["success_rate_mean"]), 3),
            "scope": "HY3 arm observation; not validation of original-paper fidelity"}


def main():
    result = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Audited HY3 method port; original-paper reproduction NOT established",
        "supersedes": "Withdraws complete labels and unvalidated deltas in commit f0a0ff1",
        "protocol": {
            "paired_eval": "Five independent runs over the full fixed official test set; five repetitions are not pass^5",
            "metrics": {"MSR": "mean task success rate across runs", "pass^5": "fraction of tasks successful in all five runs", "pass@5": "fraction successful at least once in five runs"},
            "paper_models": "solver gpt-5.4-mini default effort; auxiliaries gpt-5.4 high; tau2 user gpt-4.1-2025-04-14",
            "hy3_models": "All model roles use HY3 Taiji only; solver high requested; tau2 user and NL evaluator changed to HY3",
            "execution": "any4 CPU only; no WorkBuddy API for experiments",
            "implementation": "Pinned DAEDALUS; ACE/ExpeL are its references reimplementations, not original author repos",
            "acceptance": "Official per-run task IDs + five runs + score/trace agreement + SHA-bound terminal markers; old artifacts not auto-promoted",
            "runtime_fix": "Explicit runtime_safety shim; real no-completion stall, exception propagation, CPU embedding; no locked vendor edits",
            "price": "unknown/null, never zero dollars",
        },
        "benchmarks": {},
    }
    for bench in ("tau2", "appworld"):
        base, memory = _eval_entry(bench, "baseline"), _eval_entry(bench, "memory")
        ace, expel = _reference_entry(bench, "ace"), _reference_entry(bench, "expel")
        generation = _generation_entry(bench)
        result["benchmarks"][bench] = {
            "generation": generation, "baseline": base, "memory": memory,
            "memory_minus_baseline": _delta(base, memory) if generation["status"] == "complete" else None,
            "ace": ace, "ace_minus_baseline": _delta(base, ace["inference"]),
            "expel": expel, "expel_minus_baseline": _delta(base, expel["inference"]),
        }
    dest = ROOT / "results/full_benchmark.json"
    dest.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
