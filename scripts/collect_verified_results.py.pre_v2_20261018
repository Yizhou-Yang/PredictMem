"""独立只读验收：marker、官方 ID、评分和真实 usage 必须同时成立。"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics
import os
import sys


def install_runtime_scoring_metadata():
    """在官方运行入口安装metadata识别，不吞异常、不重算成功评分。"""
    from daedalus.core.evaluation import evaluate
    from runtime_safety import MANIFEST
    evaluate._NON_TRACE_FILES = evaluate._NON_TRACE_FILES | {MANIFEST}


def verified_run_directories(arm):
    from runtime_safety import MANIFEST, VERSION, task_is_complete

    directory = Path(arm["output_directory"])
    if load(directory / MANIFEST) != {"runtime_safety_version": VERSION}:
        raise RuntimeError("独立评分要求已验证的 runtime metadata")
    expected = {f"run_{i}" for i in range(arm["num_runs"])}
    if {p.name for p in directory.glob("run_*") if p.is_dir()} != expected:
        raise RuntimeError("评分前 run 目录集合不一致")
    allowed = {MANIFEST, "evaluation.json", "run_meta.json", "run_summary.json"}
    if any(p.name not in allowed for p in directory.glob("*.json")):
        raise RuntimeError("拒绝忽略真实 flat trace 或未知 JSON")
    for index in range(arm["num_runs"]):
        folder = directory / f"run_{index}"
        if {p.stem for p in folder.glob("*.json") if not p.name.startswith(".")} != set(arm["task_ids"]):
            raise RuntimeError("评分前 trace taskID 集合不一致")
        if not all(task_is_complete(folder / f"{tid}.json", tid) for tid in arm["task_ids"]):
            raise RuntimeError("评分前任务终止 marker 不完整")
    return [directory / f"run_{i}" for i in range(arm["num_runs"])]


def score_official_arm(arm):
    """仅忽略已验证的安全层 metadata；仍调用完整官方 scorer，无模型调用。"""
    from run_verified_reproduction import VENDOR
    from runtime_safety import MANIFEST

    verified_run_directories(arm)
    if arm["benchmark"] == "tau2":
        from run_verified_reproduction import compatibility_approval
        compatibility_approval(arm.get("namespace_path"))
    sys.path.insert(0, str(VENDOR))
    from daedalus.core.config import load_config, experiment_dir
    from daedalus.core.evaluation import evaluate
    from daedalus.core.registry import get_benchmark
    from daedalus.core.logging.usage_aggregate import UsageAggregator
    from run_verified_reproduction import atomic_json
    cfg = load_config(arm["config_path"])
    if arm["method"] in ("ace", "expel"):
        cfg.setup = arm["method"]
    cwd = Path.cwd()
    try:
        os.chdir(VENDOR)
        benchmark = get_benchmark(cfg)
        runs = [benchmark.evaluate_run(cfg, directory, task_ids=arm["task_ids"], run_idx=index)
                for index, directory in enumerate(verified_run_directories(arm))]
        result = {"experiment_name": cfg.name, "benchmark": cfg.benchmark, "multi_run": True,
                  "per_run": runs, "aggregate": evaluate.aggregate_across_runs(runs),
                  "usage": UsageAggregator.from_experiment_dir(experiment_dir(cfg)).summary(),
                  "scoring_channel": "independent_official_scoring_not_primary_execution"}
    finally:
        os.chdir(cwd)
    verified_run_directories(arm)
    atomic_json(arm["independent_evaluation_path"], result)
    return result


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def audit_arm(arm, require_finished=True, evaluation_path=None):
    from runtime_safety import task_is_complete

    directory = Path(arm["output_directory"])
    expected = set(arm["task_ids"])
    issues, per_run, success_sets = [], [], []
    source_audit = None
    snapshot_path = arm.get("launch_source_snapshot_path")
    if snapshot_path:
        from run_verified_reproduction import source_review
        snapshot = load(snapshot_path)
        snapshot = snapshot.get("original_launch_source", snapshot)
        source_audit = source_review(snapshot)
        if source_audit["vendor_or_data_source_changed_during_run"] or source_audit["frozen_execution_source_changed"]:
            issues.append("锁定vendor或冻结执行source发生变化")
    events = {}
    usage_files = sorted((directory / "usage").rglob("*.jsonl"))
    for path in usage_files:
        try:
            for line in path.read_text().splitlines():
                event = json.loads(line)
                eid = event.get("event_id")
                if not eid or eid in events:
                    raise ValueError("usage event_id 缺失或重复")
                events[eid] = event
        except (OSError, ValueError, TypeError) as exc:
            issues.append(f"usage 无效 {path.name}: {exc}")
    # user_simulator 旁证：上游 record_external 不保存真实返回模型/request_id。
    provenance = {}
    for path in sorted((directory / "usage_provenance").rglob("*.jsonl")):
        try:
            for line in path.read_text().splitlines():
                row = json.loads(line)
                if row.get("event_id") in provenance:
                    raise ValueError("provenance event_id 重复")
                provenance[row.get("event_id")] = row
        except (OSError, ValueError, TypeError) as exc:
            issues.append(f"usage_provenance 无效 {path.name}: {exc}")
    completed = {eid: e for eid, e in events.items() if e.get("status") == "completed"}
    observed_models = Counter()
    tokens_total = 0
    token_counts = Counter()
    cache_details_available = False
    by_task = Counter()
    for eid, event in events.items():
        if event.get("requested_model") != "openai/hy3":
            issues.append(f"非 HY3 请求: {eid}")
        if event.get("benchmark") != arm["benchmark"] or event.get("experiment_name") != arm["experiment_name"]:
            issues.append(f"usage experiment/benchmark 不一致: {eid}")
        if str(event.get("task_id")) not in expected or event.get("run_idx") not in range(arm["num_runs"]):
            issues.append(f"usage task/run 不一致: {eid}")
        if event.get("role") not in arm["active_roles"]:
            issues.append(f"未声明模型角色: {eid}")
        if event.get("status") != "completed":
            issues.append(f"API 调用未正常完成: {eid} {event.get('error_type', '')}")
            continue
        returned, request_id = event.get("returned_model"), event.get("request_id")
        side = provenance.get(eid)
        if not request_id and event.get("role") == "user_simulator" and side is not None:
            if side.get("verified") is True and side.get("role") == "user_simulator":
                returned, request_id = side.get("returned_model"), side.get("request_id")
        observed_models[str(returned)] += 1
        if returned not in ("hy3", "openai/hy3") or not request_id:
            issues.append(f"真实返回模型/request_id 未验证: {eid}")
        tokens = event.get("tokens", {})
        if any(type(tokens.get(k)) is not int or tokens[k] < 0 for k in ("prompt_tokens", "completion_tokens")):
            issues.append(f"真实 token 记录缺失: {eid}")
        else:
            tokens_total += tokens["prompt_tokens"] + tokens["completion_tokens"]
        for key, value in tokens.items():
            if key == "cache_details_available":
                cache_details_available = cache_details_available or value is True
            elif type(value) is int and value >= 0:
                token_counts[key] += value
        by_task[(event.get("run_idx"), str(event.get("task_id")))] += 1
    try:
        evaluation = load(evaluation_path or directory / "evaluation.json")
    except (OSError, ValueError):
        evaluation = {}
        issues.append("evaluation.json 缺失或无效")
    if evaluation.get("experiment_name") != arm["experiment_name"] or evaluation.get("benchmark") != arm["benchmark"]:
        issues.append("evaluation experiment/benchmark 不一致")
    runs = evaluation.get("per_run", [])
    if len(runs) != arm["num_runs"]:
        issues.append("evaluation run 数不一致")
    if {p.name for p in directory.glob("run_*") if p.is_dir()} != {f"run_{i}" for i in range(arm["num_runs"])}:
        issues.append("输出 run 目录缺失或包含额外 run")
    rates, referenced = [], set()
    for index in range(arm["num_runs"]):
        run = runs[index] if index < len(runs) else {}
        scores = run.get("task_success", {})
        if not isinstance(scores, dict):
            scores = {}
        local = []
        if set(scores) != expected or run.get("num_tasks") != len(expected):
            local.append("官方 taskID/分母不一致")
        traces = {p.stem for p in (directory / f"run_{index}").glob("*.json") if not p.name.startswith(".")}
        if traces != expected:
            local.append("trace taskID 集合不一致")
        verified, successes = [], set()
        for tid in sorted(expected):
            path = directory / f"run_{index}" / f"{tid}.json"
            if not task_is_complete(path, tid):
                local.append(f"无 SHA-bound 终止 marker: {tid}")
                continue
            trace = load(path)
            verified.append(tid)
            verdict = trace.get("success")
            if type(verdict) is not bool or type(scores.get(tid)) is not bool or scores.get(tid) != verdict:
                local.append(f"trace/score 不一致: {tid}")
            if trace.get("evaluation", {}).get("success") is not verdict:
                local.append(f"task evaluation/trace 不一致: {tid}")
            if trace.get("task_id") != tid or trace.get("experiment_name") != arm["experiment_name"]:
                local.append(f"trace ID/experiment 不一致: {tid}")
            cfg = trace.get("config", {})
            if cfg.get("agent", {}).get("model") != "openai/hy3" or cfg.get("agent", {}).get("reasoning_effort") != "high":
                local.append(f"solver model/effort 不一致: {tid}")
            if cfg.get("run", {}).get("num_runs") != arm["num_runs"] or cfg.get("run", {}).get("parallel") != arm["parallel"]:
                local.append(f"trace run/parallel 不一致: {tid}")
            ids = trace.get("usage_event_ids", [])
            if not ids or len(ids) != len(set(ids)) or not by_task[(index, tid)]:
                local.append(f"task usage 缺失/重复: {tid}")
            for eid in ids:
                event = completed.get(eid, {})
                if event.get("run_idx") != index or str(event.get("task_id")) != tid:
                    local.append(f"trace usage 关联不一致: {tid}/{eid}")
                referenced.add(eid)
            official = run.get("appworld_evaluation", {}).get("individual", {}).get(tid, {})
            if arm["benchmark"] == "appworld" and official.get("success") is not verdict:
                local.append(f"AppWorld 官方评价不一致: {tid}")
            if verdict:
                successes.add(tid)
        rate = len(successes) / len(expected)
        rates.append(rate)
        if run.get("num_successes") != len(successes) or run.get("success_rate") != rate:
            local.append("per-run 成功数/率不一致")
        success_sets.append(successes)
        per_run.append({"run_index": index, "expected_tasks": len(expected), "terminal_count": len(verified),
                        "terminal_task_ids": verified, "success_count": len(successes), "issues": local})
        issues.extend(f"run_{index}: {x}" for x in local)
    if set(completed) - referenced:
        issues.append("存在未被 trace 关联的 completed usage")
    aggregate = evaluation.get("aggregate", {})
    if aggregate.get("num_runs") != arm["num_runs"] or aggregate.get("num_tasks_per_run_all") != [len(expected)] * arm["num_runs"]:
        issues.append("aggregate run/分母不一致")
    if aggregate.get("unequal_denominators") is not False:
        issues.append("aggregate 分母一致性未确认")
    if aggregate.get("success_rate_per_run") != rates or aggregate.get("success_rate_mean") != sum(rates) / len(rates):
        issues.append("aggregate 成功率不一致")
    summary_usage = evaluation.get("usage", {})
    summary_tokens = summary_usage.get("tokens_total", {})
    tokens_match = isinstance(summary_tokens, dict) and all(summary_tokens.get(k) == v for k, v in token_counts.items())
    if isinstance(summary_tokens, dict) and "cache_details_available" in summary_tokens:
        tokens_match = tokens_match and summary_tokens["cache_details_available"] is cache_details_available
    if summary_usage.get("num_completed_calls") != len(completed) or not tokens_match:
        issues.append("evaluation usage 与真实 ledger 不一致")
    if not completed:
        issues.append("没有真实 HY3 completed 调用")
    if require_finished and (arm.get("state") != "finished" or arm.get("exit_code") != 0):
        issues.append("管线进程未正常终止")
    frozen = arm.get("bank", {})
    for path, digest in frozen.get("frozen_hashes", {}).items():
        if not Path(path).is_file() or sha(path) != digest:
            issues.append(f"冻结 bank 被改变/缺失: {path}")
    if issues:
        label = "incomplete_or_invalid"
    elif arm["scope"] == "train_smoke":
        label = "verified_train_smoke_not_test_result"
    elif frozen.get("provenance") == "partial-bank":
        label = "verified_execution_partial_bank_diagnostic"
    elif frozen.get("provenance") == "legacy-bank":
        label = "verified_execution_legacy_bank_fidelity_unvalidated"
    else:
        label = "verified_full_official_baseline"
    accepted = not issues and arm["scope"] == "full_official_test"
    return {"arm": arm["id"], "status": label, "issues": issues, "per_run": per_run,
            "scoring_channel": "independent" if evaluation_path else "primary_official_execution",
            "source_review": source_audit,
            "wrapper_changed_during_run": source_audit["wrapper_changed_during_run"] if source_audit else [],
            "same_source_comparison_verified": bool(source_audit and not source_audit["vendor_or_data_source_changed_during_run"] and
                not source_audit["frozen_execution_source_changed"] and source_audit["later_spawn_wrapper_version"] == "frozen_namespace_snapshot"),
            "execution_verified": not issues, "official_full_test_execution_verified": accepted,
            "method_fidelity": "not_validated", "method_fully_reproduced": False,
            "eligible_for_method_claim": False, "bank_provenance": frozen.get("provenance", "none"),
            "num_completed_calls": len(completed), "total_token_count": tokens_total, "tokens_total": dict(token_counts),
            "observed_returned_models": dict(observed_models), "ledger_hashes": {str(p): sha(p) for p in usage_files},
            "usage_timestamp_note": "AppWorld 冻结世界时间可能进入 ledger；墙钟以 supervisor manifest 为准",
            "estimated_total_cost_usd": summary_usage.get("estimated_total_cost_usd") if summary_usage.get("cost_complete") else None,
            "success_rate_per_run": rates if not issues else None,
            "MSR": statistics.mean(rates) if not issues else None,
            "pass_pow_5": len(set.intersection(*success_sets))/len(expected) if accepted and arm["num_runs"] == 5 else None,
            "pass_at_5": len(set.union(*success_sets))/len(expected) if accepted and arm["num_runs"] == 5 else None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--arms", nargs="+")
    args = parser.parse_args()
    manifest = load(args.manifest)
    selected = args.arms or [a["id"] for a in manifest["arms"] if a.get("state") not in ("planned", "blocked_compatibility")]
    archive = args.manifest.parent / "launch_source_archive/launch_snapshot.json"
    for arm in manifest["arms"]:
        if not arm.get("launch_source_snapshot_path") and archive.exists():
            arm["launch_source_snapshot_path"] = str(archive)
    results = [audit_arm(a) for a in manifest["arms"] if a["id"] in selected]
    result = {"manifest": str(args.manifest), "results": results, "tau2_not_started_without_notice": True,
              "source_review_final_path": manifest.get("source_review_final_path"),
              "launch_snapshot_never_replaced": True}
    from run_verified_reproduction import atomic_json
    atomic_json(args.manifest.parent / "verified_results.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if results and all(a["execution_verified"] for a in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
