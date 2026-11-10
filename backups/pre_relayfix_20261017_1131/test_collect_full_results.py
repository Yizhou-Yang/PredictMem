"""No model/API regression tests for audited result acceptance."""
import json
from pathlib import Path
import pytest
import collect_full_results as collector
import runtime_safety as safety


def snapshot(counts, ids):
    runs = [{"num_tasks": n, "task_success": {str(t): False for t in list(ids)[:n]}}
            for n in counts]
    return {"aggregate": {"num_runs": len(runs), "num_tasks_per_run_all": counts,
            "unequal_denominators": len(set(counts)) != 1,
            "success_rate_mean": 0.5, "pass_hat_k": {"pass^5": 0.125},
            "pass_at_k": {"pass@5": 0.875}}, "per_run": runs}


@pytest.mark.parametrize("bench,counts", [
    ("tau2", [40,39,40,40,40]),
    ("appworld", [168,168,168,8]),
    ("appworld", [168,132]),
    ("appworld", [42,168,168,168,168]),
])
def test_legacy_partial_never_delta(tmp_path, bench, counts):
    ids = [str(t) for t in range(collector.EXPECTED_TASKS[bench])]
    entry = collector._evaluate_snapshot(snapshot(counts, ids), bench, tmp_path, ids)
    assert entry["status"] == "partial"
    assert collector._delta(entry, entry) is None


def test_full_counts_are_not_terminal_proof(tmp_path):
    ids = [str(t) for t in range(40)]
    entry = collector._evaluate_snapshot(snapshot([40]*5, ids), "tau2", tmp_path, ids)
    assert entry["status"] == "scored_complete_unverified"
    assert entry["official_task_coverage_complete"]
    assert not entry["eligible_for_formal_comparison"]
    assert collector._delta(entry, entry) is None
    assert entry["observed_pass_pow_5"] == 0.125
    assert entry["observed_pass_at_5"] == 0.875
    assert entry["estimated_total_cost_usd"] is None


def test_wrong_ids_not_accepted(tmp_path):
    ids = [str(t) for t in range(40)]
    data = snapshot([40]*5, ids)
    data["per_run"][0]["task_success"]["wrong"] = data["per_run"][0]["task_success"].pop("0")
    entry = collector._evaluate_snapshot(data, "tau2", tmp_path, ids)
    assert entry["status"] == "partial"
    assert entry["per_run_audit"][0]["missing_task_ids"] == ["0"]


def test_marker_score_agreement_required(tmp_path):
    ids = [str(t) for t in range(40)]
    data = snapshot([40]*5, ids)
    for run in range(5):
        directory = tmp_path / f"run_{run}"
        safety.ensure_namespace(directory)
        for tid in ids:
            path = directory / f"{tid}.json"
            scope = {"attempt_id": f"{run}-{tid}", "started": set()}
            safety._start_trace(scope, path)
            path.write_text(json.dumps({"task_id": tid, "success": False}))
            safety._finish_trace(scope, path)
    entry = collector._evaluate_snapshot(data, "tau2", tmp_path, ids)
    assert entry["status"] == "complete"
    assert entry["terminal_completion_verified"]
    data["per_run"][0]["task_success"]["0"] = True
    entry = collector._evaluate_snapshot(data, "tau2", tmp_path, ids)
    assert not entry["eligible_for_formal_comparison"]
    assert entry["per_run_audit"][0]["score_trace_mismatches"] == ["0"]


@pytest.mark.parametrize("bench,total,hole,error", [
    ("appworld", 90, 16, None), ("tau2", 74, None, 47),
])
def test_generation_summary_not_completion(tmp_path, monkeypatch, bench, total, hole, error):
    monkeypatch.setattr(collector, "VENDOR", tmp_path)
    directory = tmp_path / f"outputs/daedalus/hy3_{bench}_generation"
    (directory / "sessions").mkdir(parents=True)
    for index in range(total):
        if index == hole:
            continue
        value = {"session_index": index, "result": "no_task"}
        if index == error:
            value = {"session_index": index, "kind": "session_error"}
        (directory / "sessions" / f"session_{index:02}.json").write_text(json.dumps(value))
    (directory / "run_summary.json").write_text(json.dumps({"num_tasks": 47}))
    (directory / "tasks.json").write_text(json.dumps({"tasks": [], "next_session": total}))
    entry = collector._generation_entry(bench)
    assert entry["status"] == "partial"
    assert entry["missing_session_indices"] == ([] if hole is None else [hole])
    assert entry["session_error_indices"] == ([] if error is None else [error])


def test_missing_snapshot_has_no_score(tmp_path):
    entry = collector._evaluate_snapshot(None, "tau2", tmp_path, [str(t) for t in range(40)])
    assert entry["status"] == "partial"
    assert entry["success_rate_mean"] is None
    assert not entry["eligible_for_formal_comparison"]
