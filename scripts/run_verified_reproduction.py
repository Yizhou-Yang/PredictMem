"""any4 CPU 独立监督管线；新目录、单次启动、不择优重试、不隐式启动 tau2。"""
from __future__ import annotations

import argparse
import copy
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import urlsplit

ROOT = Path(os.environ.get("PREDICTMEM_ROOT", Path(__file__).resolve().parents[1]))
VENDOR = ROOT / "vendor/daedalus"
PYTHON = VENDOR / ".venv/bin/python"
THREAD_ENV = {k: "1" for k in ("OMP_NUM_THREADS", "OMP_THREAD_LIMIT", "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS",
    "RAYON_NUM_THREADS", "TORCH_NUM_THREADS", "TORCH_NUM_INTEROP_THREADS")}
THREAD_ENV.update(CUDA_VISIBLE_DEVICES="-1", TOKENIZERS_PARALLELISM="false")
MAX_WORKERS = 24
DEFAULT_DEADLINE = "2026-10-16T15:33:00+08:00"


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".verified-writing-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def require_remote():
    if ROOT != Path("/data/workspace/PredictMem") or sys.platform != "linux":
        raise RuntimeError("所有执行仅允许 any4 /data/workspace/PredictMem Linux CPU")
    if Path(sys.executable).resolve() != PYTHON.resolve():
        raise RuntimeError("必须使用锁定 vendor .venv Python")


def official_ids(benchmark, split):
    if benchmark == "appworld":
        path = VENDOR / f"data/datasets/{split}.txt"
        ids = [line.strip().split(":")[0] for line in path.read_text().splitlines() if line.strip()]
        expected = {"train": 90, "test_normal": 168}[split]
    else:
        path = VENDOR / "benchmarks/tau2-bench/data/tau2/domains/retail/split_tasks.json"
        ids = [str(x) for x in json.loads(path.read_text())[split]]
        expected = {"train": 74, "test": 40}[split]
    if len(ids) != expected or len(set(ids)) != expected or any(not re.fullmatch(r"[A-Za-z0-9_-]+", x) for x in ids):
        raise ValueError("官方 split taskID 不符合锁定规模")
    return {"path": str(path), "sha256": sha(path), "task_ids": ids, "expected_count": expected}


def source_snapshot():
    lock = json.loads((ROOT / "sources.lock.json").read_text())
    repos, files = {}, {}
    for relative, expected in {".": lock["daedalus"]["commit"], **lock["daedalus"]["submodules"]}.items():
        repo = VENDOR / relative
        actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
        if actual != expected:
            raise RuntimeError(f"锁定 source revision 不一致: {relative}")
        subprocess.run(["git", "diff", "--quiet"], cwd=repo, check=True)
        subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=repo, check=True)
        repos[str(repo)] = {"commit": actual, "tracked_clean": True}
        paths = subprocess.check_output(["git", "ls-files", "-z"], cwd=repo).decode().split("\0")
        for name in paths:
            path = repo / name
            if name and path.is_file():
                files[str(path)] = sha(path)
    optional_missing = []
    for name in ("run.py", "runtime_safety.py", "run_verified_reproduction.py", "collect_verified_results.py", "test_verified_reproduction.py", "embedding_preflight.py", "test_embedding_preflight.py", "tau2_transport_safety.py", "tau2_hy3_eval.py",
                 "relay.py", "test_llm_transport.py", "test_runtime_safety.py", "test_relay.py"):
        path = ROOT / "scripts" / name
        if path.exists():
            files[str(path)] = sha(path)
        else:
            optional_missing.append({"path": str(path), "sha256": None, "present_at_snapshot": False})
    files[str(ROOT / "sources.lock.json")] = sha(ROOT / "sources.lock.json")
    return {"repositories": repos, "file_sha256": files, "uv_lock_sha256": sha(VENDOR / "uv.lock"),
            "unavailable_at_snapshot": optional_missing}


def verify_hashes(mapping):
    for path, digest in mapping.items():
        if not Path(path).is_file() or sha(path) != digest:
            raise RuntimeError(f"快照文件改变或缺失: {path}")


def source_review(snapshot):
    wrapper_changes, source_changes = [], []
    for path, expected in snapshot["file_sha256"].items():
        current = sha(path) if Path(path).is_file() else None
        if current == expected:
            continue
        change = {"path": path, "launch_sha256": expected, "current_sha256": current}
        target = wrapper_changes if Path(path).parent == ROOT / "scripts" else source_changes
        target.append(change)
    frozen_changes = []
    for path, expected in snapshot.get("execution_file_sha256", {}).items():
        current = sha(path) if Path(path).is_file() else None
        if current != expected:
            frozen_changes.append({"path": path, "launch_sha256": expected, "current_sha256": current})
    for name in ("embedding_preflight.py", "tau2_transport_safety.py"):
        path = ROOT / "scripts" / name
        if str(path) not in snapshot["file_sha256"] and path.exists():
            wrapper_changes.append({"path": str(path), "launch_sha256": None, "current_sha256": sha(path), "change": "added_after_launch"})
    return {"reviewed_at": now(), "wrapper_changed_during_run": wrapper_changes,
            "vendor_or_data_source_changed_during_run": source_changes,
            "frozen_execution_source_changed": frozen_changes,
            "launch_snapshot_never_replaced": True,
            "existing_workers_not_hot_reloaded": True,
            "new_changes_effect_on_existing_workers": "不得归因；现存worker已import原版本",
            "later_spawn_wrapper_version": "frozen_namespace_snapshot" if snapshot.get("execution_file_sha256") else "未独立验证；可能读取修改后wrapper，不能排除混合版本"}


def verify_execution_source(snapshot):
    review = source_review(snapshot)
    if review["vendor_or_data_source_changed_during_run"] or review["frozen_execution_source_changed"]:
        raise RuntimeError("锁定vendor或冻结执行快照改变，拒绝验收")
    return review


def freeze_wrappers(namespace, source):
    destination = namespace / "runtime_snapshot"
    destination.mkdir(exist_ok=False)
    frozen = {p: h for p, h in source["file_sha256"].items() if Path(p).parent != ROOT / "scripts"}
    for path, expected in source["file_sha256"].items():
        if Path(path).parent != ROOT / "scripts":
            continue
        target = destination / Path(path).name
        shutil.copyfile(path, target)
        if sha(target) != expected or sha(path) != expected:
            raise RuntimeError("wrapper 冻结时发生并行变更，请在新namespace重新prepare")
        target.chmod(0o444)
        frozen[str(target)] = expected
    source["execution_file_sha256"] = frozen
    source["runtime_snapshot_directory"] = str(destination)
    atomic_json(namespace / "launch_source_snapshot.json", source)
    return destination


def review_legacy_launch(name, wait_for_pid=None):
    namespace = ROOT / "outputs" / name
    manifest = json.loads((namespace / "manifest.json").read_text())
    archive = namespace / "launch_source_archive/launch_snapshot.json"
    snapshot = json.loads(archive.read_text())["original_launch_source"] if archive.exists() else manifest["source"]
    if wait_for_pid:
        import selectors
        descriptor = os.pidfd_open(wait_for_pid)
        atomic_json(namespace / "source_watcher_pid.json", {"pid": os.getpid(), "target_pid": wait_for_pid, "started_at": now()})
        with selectors.DefaultSelector() as selector:
            selector.register(descriptor, selectors.EVENT_READ)
            deadline = datetime.fromisoformat(manifest["deadline"]).timestamp() + 60
            terminated = bool(selector.select(timeout=max(0, deadline-time.time())))
        os.close(descriptor)
        if not terminated:
            raise RuntimeError("source watcher 到截止仍未见 supervisor 终止")
    result = source_review(snapshot)
    latest = json.loads((namespace / "manifest.json").read_text())
    result["observed_sessions"] = latest["sessions"]
    result["original_launch_snapshot_path"] = str(archive)
    result["original_supervisor_source_change_failure_is_not_worker_failure"] = True
    result["terminal_review"] = bool(wait_for_pid)
    target = namespace / ("source_review_final.json" if wait_for_pid else "source_review_current.json")
    atomic_json(target, result)
    if wait_for_pid:
        latest["source_review_final_path"] = str(target)
        latest["wrapper_changed_during_run"] = result["wrapper_changed_during_run"]
        atomic_json(namespace / "manifest.json", latest)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0 if not result["vendor_or_data_source_changed_during_run"] else 1


def dependencies():
    return {"python": sys.version, "executable": sys.executable,
            "distributions": sorted([{"name": d.metadata["Name"], "version": d.version} for d in importlib.metadata.distributions()], key=lambda x: (x["name"] or "", x["version"]))}


def resources():
    paths = ["/sys/fs/cgroup/cpu.max", "/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory.current",
             "/sys/fs/cgroup/cpu/cpu.cfs_quota_us", "/sys/fs/cgroup/cpu/cpu.cfs_period_us",
             "/sys/fs/cgroup/memory/memory.limit_in_bytes", "/sys/fs/cgroup/memory/memory.usage_in_bytes"]
    return {"host": socket.gethostname(), "cpu_count_not_worker_budget": os.cpu_count(),
            "user_cpu_quota_cores": 16, "worker_budget": MAX_WORKERS, "per_worker_numeric_threads": 1,
            "cgroup": {p: Path(p).read_text().strip() for p in paths if Path(p).exists()},
            "thread_environment": THREAD_ENV}


def freeze_bank(namespace, benchmark, method, previous_bank=None):
    if method in ("ace", "expel"):
        source = VENDOR / f"outputs/baselines/{method}/memory/hy3_{benchmark}"
        names = ["playbook.txt", "pool.json", "config.yaml", "run_meta.json", "run_summary.json", f"{method}.yaml"]
        if method == "expel":
            names.append("demonstrations.json")
        provenance = "legacy-bank"
    else:
        source = VENDOR / f"outputs/daedalus/hy3_{benchmark}_generation"
        names = ["pool.json", "consolidated_pool.json", "tasks.json", "run_summary.json", "config.yaml"]
        provenance = "partial-bank"
    if previous_bank:
        verify_hashes(previous_bank["frozen_hashes"])
        source = Path(previous_bank["frozen_directory"])
    destination = namespace / "frozen_banks" / f"{benchmark}_{method}"
    destination.mkdir(parents=True, exist_ok=False)
    hashes, originals = {}, {}
    for name in names:
        original = source / name
        if not original.exists():
            if name == "pool.json" or (method == "memory" and name == "consolidated_pool.json") or (method == "ace" and name == "playbook.txt") or (method == "expel" and name == "demonstrations.json"):
                raise RuntimeError(f"必需 bank 文件缺失: {original}")
            continue
        before = sha(original)
        target = destination / name
        shutil.copyfile(original, target)
        if sha(target) != before or sha(original) != before:
            raise RuntimeError(f"bank 拷贝时发生变化: {original}")
        target.chmod(0o444)
        hashes[str(target)] = before
        originals[str(original)] = before
    result = {"provenance": provenance, "source_directory": str(source), "frozen_directory": str(destination),
              "source_hashes": originals, "frozen_hashes": hashes, "frozen_at": now(),
              "accumulation_terminal_coverage_verified": False, "method_fidelity": "not_validated",
              "method_fully_reproduced": False}
    if previous_bank:
        before = {Path(p).name: h for p, h in previous_bank["frozen_hashes"].items()}
        after = {Path(p).name: h for p, h in hashes.items()}
        if before != after:
            raise RuntimeError("新namespace bank 与旧冻结bank不完全相同")
        result.update(previous_frozen_directory=previous_bank["frozen_directory"], same_bank_bytes_verified=True)
    atomic_json(destination / "provenance.json", result)
    return result


def make_config(arm, namespace):
    benchmark, method = arm["benchmark"], arm["method"]
    cfg = {"benchmark": benchmark, "kind": "inference", "experiment_name": arm["experiment_name"],
           "category": namespace.name, "appworld": {"dataset": arm["split"] if benchmark == "appworld" else "test_normal"},
           "tau2": {"domain": "retail", "task_split": "test", "user_llm": "openai/hy3",
                    "user_llm_args": {"temperature": 0.0, "reasoning_effort": "high"}},
           "run": {"num_runs": arm["num_runs"], "parallel": arm["parallel"], "force": False},
           "agent": {"model": "openai/hy3", "temperature": 1.0, "reasoning_effort": "high", "max_turns": 30},
           "accumulation": {"extraction_model": "openai/hy3", "extraction_reasoning_effort": None},
           "generation": {"explorer_model": "openai/hy3", "explorer_reasoning_effort": "high", "judge_model": "openai/hy3", "judge_reasoning_effort": "high"},
           "memory": {"enabled": False}, "logging": {"verbose": True},
           "cost_accounting": {"enabled": True, "require_complete_estimates": False}}
    cfg[benchmark]["task_ids"] = arm["task_ids"]
    if benchmark == "tau2":
        cfg["tau2"]["task_split"] = arm["split"]
    bank = Path(arm.get("bank", {}).get("frozen_directory", namespace))
    if method == "ace":
        cfg["ace"] = {"playbook_path": str(bank / "playbook.txt"), "reflector_model": "openai/hy3",
                      "reflector_reasoning_effort": "high", "curator_model": "openai/hy3", "curator_reasoning_effort": "high"}
    elif method == "expel":
        cfg["expel"] = {"insights_path": str(bank / "pool.json"), "extraction_model": "openai/hy3",
                        "extraction_reasoning_effort": "high", "reflection_model": "openai/hy3", "reflection_reasoning_effort": "high"}
    elif method == "memory":
        import yaml
        overlay_path = ROOT / "configs" / f"{benchmark}_memory.yaml"
        overlay = yaml.safe_load(overlay_path.read_text())
        memory = copy.deepcopy(overlay["memory"])
        if not memory.get("heuristics_at_start") or Path(memory["pool_path"]).name != "consolidated_pool.json":
            raise RuntimeError("原DAEDALUS config不是consolidated full heuristics_at_start，拒绝替换算法")
        memory["pool_path"] = str(bank / "consolidated_pool.json")
        preserved = copy.deepcopy(overlay)
        preserved.update({k: v for k, v in cfg.items() if k in ("benchmark", "kind", "experiment_name", "category", "appworld", "tau2", "run", "agent", "cost_accounting", "logging")})
        preserved["memory"] = memory
        cfg = preserved
        arm["memory_overlay_provenance"] = {"path": str(overlay_path), "sha256": sha(overlay_path),
            "original_memory": overlay["memory"], "only_bank_path_redirected": True,
            "full_heuristics_at_start": True, "no_bm25_topk_override": True}
    return cfg


def compatibility_approval(namespace):
    if namespace is None:
        raise RuntimeError("tau2等待namespace compatibility_approval.json，不允许无证据启动")
    path = Path(namespace) / "compatibility_approval.json"
    if not path.exists():
        raise RuntimeError("tau2等待namespace compatibility_approval.json")
    approval = json.loads(path.read_text())
    if approval.get("benchmark") != "tau2" or approval.get("approved") is not True or approval.get("route_verified") is not True or approval.get("no_api_tests_passed") is not True:
        raise RuntimeError("tau2授权、HY3 route或无API测试证据未通过")
    endpoint = urlsplit(approval.get("endpoint", ""))
    if approval.get("model") != "openai/hy3" or endpoint.hostname != "127.0.0.1" or endpoint.port != 8743:
        raise RuntimeError("tau2 approval必须锁定HY3太极8743")
    hashes = approval.get("source_hashes", {})
    for name in ("runtime_safety.py", "tau2_transport_safety.py"):
        source = str(ROOT / "scripts" / name)
        if source not in hashes:
            raise RuntimeError(f"tau2 approval缺少{ name }源码证据")
    if not approval.get("evidence_sha256"):
        raise RuntimeError("tau2 approval缺少可复核无API测试日志hash")
    verify_hashes(hashes)
    verify_hashes(approval["evidence_sha256"])
    manifest = json.loads((Path(namespace) / "manifest.json").read_text())
    if any(manifest["source"]["file_sha256"].get(p) != h for p, h in hashes.items()):
        raise RuntimeError("tau2 approval与该namespace冻结source不一致，须新namespace")
    return {"path": str(path), "sha256": sha(path), "approval": approval}


def validate_plan(arms, selected, namespace=None):
    if len(selected) != len(set(selected)) or not selected:
        raise ValueError("arm 必须非空且不能重复启动")
    table = {a["id"]: a for a in arms}
    if any(x not in table for x in selected):
        raise ValueError("未知 arm")
    chosen = [table[x] for x in selected]
    if any(a["benchmark"] == "tau2" for a in chosen):
        compatibility_approval(namespace)
    if any(a["state"] != "planned" and not (a["benchmark"] == "tau2" and a["state"] == "blocked_compatibility" and not a.get("launch_count")) for a in chosen):
        raise RuntimeError("拒绝重试/复用任何已启动 arm")
    if any(type(a["parallel"]) is not int or a["parallel"] < 1 for a in chosen) or sum(a["parallel"] for a in chosen) > MAX_WORKERS:
        raise RuntimeError("超出安全总 worker 预算24")
    if any(a["scope"] == "full_official_test" and a["num_runs"] != 5 for a in chosen):
        raise ValueError("官方 test 固定5 runs")
    for arm in chosen:
        if arm.get("method") == "memory":
            memory = arm.get("resolved_core_config", {}).get("memory", {})
            if not memory.get("heuristics_at_start") or Path(memory.get("pool_path") or "").name != "consolidated_pool.json":
                raise RuntimeError("拒绝旧错误memory配置：只能consolidated full heuristics_at_start")
    return chosen


def prepare(name, deadline, selected=None, bank_manifest=None, embedding_proof=None):
    import yaml
    if not re.fullmatch(r"verified_[A-Za-z0-9_-]+", name):
        raise ValueError("必须使用 verified_ 隔离 namespace")
    namespace = ROOT / "outputs" / name
    namespace.mkdir(parents=True, exist_ok=False)
    logs = ROOT / "logs" / name
    logs.mkdir(parents=True, exist_ok=False)
    source = source_snapshot()
    runtime_snapshot = freeze_wrappers(namespace, source)
    previous = json.loads(Path(bank_manifest).read_text()) if bank_manifest else None
    prior_arms = {a["id"]: a for a in previous["arms"]} if previous else {}
    if selected and (len(selected) != len(set(selected)) or any(x not in {f"{b}_{m}" for b in ("appworld", "tau2") for m in ("baseline", "ace", "expel", "memory")} for x in selected)):
        raise ValueError("prepare指定的arm无效或重复")
    proof = None
    if embedding_proof:
        proof = json.loads(Path(embedding_proof).read_text())
        if proof.get("status") != "passed" or proof.get("API_calls") != 0 or not proof.get("top_2_unchanged") or not proof.get("embedding_vectors_bitwise_equal_before_after_guard_and_freeze"):
            raise RuntimeError("embedding无API preflight未通过")
        verify_hashes({str(ROOT / "scripts/embedding_preflight.py"): proof["source_hashes"][str(ROOT / "scripts/embedding_preflight.py")]})
        shutil.copyfile(embedding_proof, namespace / "embedding_preflight.json")
    deps = dependencies()
    atomic_json(namespace / "dependency_snapshot.json", deps)
    splits = {f"{b}_{s}": official_ids(b, s) for b, s in (("appworld", "train"), ("appworld", "test_normal"), ("tau2", "train"), ("tau2", "test"))}
    arms = []
    for bench in ("appworld", "tau2"):
        for method, parallel in (("baseline", 12), ("ace", 8), ("expel", 4), ("memory", 4)):
            if selected and f"{bench}_{method}" not in selected:
                continue
            split = "test_normal" if bench == "appworld" else "test"
            arm = {"id": f"{bench}_{method}", "benchmark": bench, "method": method, "namespace_path": str(namespace),
                   "num_runs": 5, "parallel": parallel, "split": split, "scope": "full_official_test",
                   "state": "planned" if bench == "appworld" else "blocked_compatibility",
                   "task_ids": splits[f"{bench}_{split}"]["task_ids"], "split_sha256": splits[f"{bench}_{split}"]["sha256"],
                   "experiment_name": f"{name}_{bench}_{method}", "active_roles": {"solver": {"model": "openai/hy3", "reasoning_effort_requested": "high"}},
                   "started_at": None, "terminated_at": None, "exit_code": None, "launch_count": 0}
            if bench == "tau2":
                arm["active_roles"].update(user_simulator={"model": "openai/hy3", "reasoning_effort_requested": "high"},
                                           evaluator={"model": "openai/hy3", "reasoning_effort_requested": "high"})
            if method != "baseline":
                arm["bank"] = freeze_bank(namespace, bench, method, prior_arms.get(arm["id"], {}).get("bank"))
            if method == "expel":
                if not proof:
                    raise RuntimeError("新ExpeL namespace须先通过独立无API embedding preflight")
                arm["embedding_preflight_path"] = str(namespace / "embedding_preflight.json")
                arm["embedding_preflight_sha256"] = sha(namespace / "embedding_preflight.json")
            if arm["id"] in prior_arms:
                arm["replaces_failed_arm"] = {"manifest": str(bank_manifest), "manifest_sha256_at_prepare": sha(bank_manifest),
                    "arm": arm["id"], "previous_state": prior_arms[arm["id"]]["state"],
                    "policy": "整臂兼容修复后新预注册，旧失败保留；不按test成功择优，不复用旧trace"}
            arms.append(arm)
    smokes = []
    for bench in ("appworld", "tau2"):
        candidate = next((a for a in arms if a["benchmark"] == bench), None)
        if candidate is None:
            continue
        smoke_id = f"{bench}_train_smoke" if candidate["method"] == "baseline" else f"{bench}_{candidate['method']}_train_smoke"
        smoke = {**copy.deepcopy(candidate), "id": smoke_id, "num_runs": 1, "parallel": 1, "split": "train",
                 "scope": "train_smoke", "task_ids": splits[f"{bench}_train"]["task_ids"][:1],
                 "split_sha256": splits[f"{bench}_train"]["sha256"], "experiment_name": f"{name}_{smoke_id}"}
        smoke.pop("replaces_failed_arm", None)
        smokes.append(smoke)
    arms = smokes + arms
    sys.path.insert(0, str(VENDOR))
    from daedalus.core.config import load_config, experiment_dir
    from daedalus.core.registry import get_benchmark
    for arm in arms:
        config = ROOT / "configs" / f"{arm['experiment_name']}.yaml"
        if config.exists():
            raise RuntimeError(f"拒绝覆盖已存在 config: {config}")
        config.write_text(yaml.safe_dump(make_config(arm, namespace), sort_keys=False))
        arm["config_path"], arm["config_sha256"] = str(config), sha(config)
        cfg = load_config(config)
        if arm["method"] in ("ace", "expel"):
            cfg.setup = arm["method"]
            mod = __import__(f"references.{arm['method']}.config", fromlist=["ACEConfig" if arm["method"] == "ace" else "ExpeLConfig"])
            cls = getattr(mod, "ACEConfig" if arm["method"] == "ace" else "ExpeLConfig")
            arm["resolved_method_config"] = cls.load(config).to_dict()
        arm["resolved_core_config"] = cfg.to_dict()
        arm["output_directory"] = str(VENDOR / experiment_dir(cfg))
        if Path(arm["output_directory"]).exists():
            raise RuntimeError("拒绝已有官方输出目录")
        # tau2 未收到兼容通知，不能导入运行它的 benchmark/runtime。
        if arm["benchmark"] == "appworld":
            actual = get_benchmark(cfg).list_task_ids(cfg)
            if actual != arm["task_ids"]:
                raise RuntimeError("官方 harness 与锁定 split taskID 顺序不一致")
        method = arm["method"] if arm["method"] in ("ace", "expel") else None
        module = f"references.{method}.run" if method else "daedalus.scripts.inference"
        arm["command"] = [str(PYTHON), str(runtime_snapshot / "runtime_safety.py"), "--benchmark", arm["benchmark"],
                          *(["--method", method] if method else []), module, "--config", str(config)]
        arm["frozen_runtime_entry"] = True
    manifest = {"schema_version": 1, "namespace": name, "prepared_at": now(), "deadline": deadline,
                "execution_location": "any4 CPU", "transport": {"host": "127.0.0.1", "port": 8743, "model": "HY3 太极", "workbuddy_api_used": False},
                "resources": resources(), "source": source, "official_splits": splits,
                "dependency_snapshot_path": str(namespace / "dependency_snapshot.json"),
                "dependency_snapshot_sha256": sha(namespace / "dependency_snapshot.json"),
                "policy": {"test_retries": 0, "select_successful_reruns": False, "old_trace_reuse": False,
                           "legacy_bank_not_method_reproduction": True, "partial_bank_diagnostic_only": True,
                           "tau2_requires_compatibility_notice": True, "effort_provider_effectiveness": "requested_not_independently_confirmed",
                           "primary_scoring_failure_never_auto_promoted": True},
                "compatibility_approval_requirements": {"path": str(namespace / "compatibility_approval.json"),
                    "required_true": ["approved", "route_verified", "no_api_tests_passed"], "benchmark": "tau2", "model": "openai/hy3",
                    "endpoint_port": 8743, "source_hashes_required": ["runtime_safety.py", "tau2_transport_safety.py"],
                    "evidence_sha256_required": True, "train_smoke_primary_required": True},
                "arms": arms, "sessions": []}
    atomic_json(namespace / "manifest.json", manifest)
    print(json.dumps({"manifest": str(namespace / "manifest.json"), "logs": str(logs), "arms": [a["id"] for a in arms]}, ensure_ascii=False), flush=True)
    return 0


def endpoint_env():
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
    endpoint = urlsplit(os.environ.get("OPENAI_BASE_URL", ""))
    if endpoint.hostname != "127.0.0.1" or endpoint.port != 8743 or endpoint.path.rstrip("/") != "/v1" or not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("只允许已授权 HY3 太极 127.0.0.1:8743/v1")
    env = os.environ.copy()
    env.update(THREAD_ENV)
    env["PREDICTMEM_ROOT"] = str(ROOT)
    env.update(OPENAI_API_BASE=os.environ["OPENAI_BASE_URL"], OPENAI_SERVICE_TIER="auto", LITELLM_LOCAL_MODEL_COST_MAP="True")
    return env


def stop_group(process):
    # 只回收本 supervisor 创建的新进程组，不触碰旧进程。
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=12)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def reserved_workers(exclude_namespace):
    reservations = []
    for path in (ROOT / "outputs").glob("verified_*/manifest.json"):
        if path.parent.name == exclude_namespace:
            continue
        other = json.loads(path.read_text())
        for arm in other["arms"]:
            pid = arm.get("pid")
            if arm.get("state") == "running" and pid and Path(f"/proc/{pid}/cmdline").exists():
                if other["namespace"].encode() in Path(f"/proc/{pid}/cmdline").read_bytes():
                    reservations.append({"namespace": other["namespace"], "arm": arm["id"], "pid": pid, "parallel": arm["parallel"]})
    return reservations


def execute(name, selected):
    namespace = ROOT / "outputs" / name
    manifest_path = namespace / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    chosen = validate_plan(manifest["arms"], selected, namespace)
    reservations = reserved_workers(name)
    if sum(a["parallel"] for a in chosen) + sum(a["parallel"] for a in reservations) > MAX_WORKERS:
        raise RuntimeError("跨namespace总worker预算超过24，须错峰而非全部并发")
    for bench in {a["benchmark"] for a in chosen if a["scope"] == "full_official_test"}:
        smoke = next((a for a in manifest["arms"] if a["scope"] == "train_smoke" and a["benchmark"] == bench), {})
        primary_verified = smoke.get("audit", {}).get("execution_verified") and smoke.get("state") == "finished" and smoke.get("exit_code") == 0 and smoke.get("primary_scoring_status") == "verified"
        if not primary_verified:
            raise RuntimeError(f"{bench}必须先通过本namespace真实train smoke的primary执行与评分；独立评分不能替代")
    launch_review = verify_execution_source(manifest["source"])
    verify_hashes({str(ROOT / "scripts" / name): manifest["source"]["file_sha256"][str(ROOT / "scripts" / name)]
                   for name in ("run_verified_reproduction.py", "collect_verified_results.py")})
    if dependencies() != json.loads(Path(manifest["dependency_snapshot_path"]).read_text()):
        raise RuntimeError("依赖快照改变")
    for split in manifest["official_splits"].values():
        verify_hashes({split["path"]: split["sha256"]})
    env = endpoint_env()
    deadline = datetime.fromisoformat(manifest["deadline"]).timestamp()
    if deadline <= time.time():
        raise RuntimeError("授权截止时间已过；拒绝新启动")
    # 同 namespace 仅允许一个活跃监督进程；flock 不删旧锁。
    import fcntl
    lock_stream = (namespace / "supervisor.lock").open("a")
    fcntl.flock(lock_stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
    mutex, processes, cancel = threading.Lock(), {}, threading.Event()
    session = {"pid": os.getpid(), "started_at": now(), "terminated_at": None, "selected_arms": selected, "exit_code": None, "state": "running",
               "launch_source_snapshot_path": str(namespace / "launch_source_snapshot.json"),
               "source_review_at_start": launch_review, "other_namespace_worker_reservations": reservations}
    manifest["sessions"].append(session)
    atomic_json(namespace / "supervisor_pid.json", {"pid": os.getpid(), "started_at": session["started_at"], "deadline": manifest["deadline"]})
    atomic_json(manifest_path, manifest)

    def handle_signal(signum, frame):
        cancel.set()
        raise KeyboardInterrupt(f"收到终止信号 {signum}")

    old = {sig: signal.signal(sig, handle_signal) for sig in (signal.SIGTERM, signal.SIGINT)}

    def arm_run(arm):
        from collect_verified_results import audit_arm
        process = None
        try:
            verify_hashes({arm["config_path"]: arm["config_sha256"], **arm.get("bank", {}).get("frozen_hashes", {})})
            if arm.get("embedding_preflight_path"):
                verify_hashes({arm["embedding_preflight_path"]: arm["embedding_preflight_sha256"]})
            arm["launch_source_snapshot_path"] = str(namespace / "launch_source_snapshot.json")
            if cancel.is_set():
                raise RuntimeError("supervisor 已取消")
            if Path(arm["output_directory"]).exists():
                raise RuntimeError("拒绝已有输出路径：不从旧 trace 恢复")
            log = ROOT / "logs" / name / f"{arm['id']}.log"
            with log.open("x") as stream:
                with mutex:
                    if cancel.is_set():
                        raise RuntimeError("supervisor 已取消")
                    process = subprocess.Popen(arm["command"], cwd=VENDOR, env=env, stdin=subprocess.DEVNULL,
                                               stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
                    processes[arm["id"]] = process
                    arm.update(state="running", pid=process.pid, pgid=process.pid, log_path=str(log), started_at=now(), launch_count=1)
                    atomic_json(manifest_path, manifest)
                print(json.dumps({"started": arm["id"], "pid": process.pid, "log": str(log), "output": arm["output_directory"]}, ensure_ascii=False), flush=True)
                code = process.wait(timeout=max(0.01, deadline - time.time()))
            with mutex:
                arm["harness_exit_code"] = code
                atomic_json(manifest_path, manifest)
            if code:
                raise RuntimeError(f"官方入口非零 exit={code}")
            with mutex:
                arm["source_review_at_termination"] = verify_execution_source(manifest["source"])
                atomic_json(manifest_path, manifest)
            if not (Path(arm["output_directory"]) / "evaluation.json").exists():
                arm["primary_scoring_status"] = "missing_or_failed"
                raise RuntimeError("primary官方评分缺失；禁止自动独立评分将failed execution变successful")
            arm["primary_scoring_status"] = "present_requires_audit"
            audit = audit_arm(arm, require_finished=False)
            if not audit["execution_verified"]:
                with mutex:
                    arm["audit"] = audit
                raise RuntimeError("完成验收失败: " + "; ".join(audit["issues"][:8]))
            with mutex:
                arm.update(state="finished", exit_code=0, terminated_at=now(), audit=audit, primary_scoring_status="verified")
                atomic_json(manifest_path, manifest)
            return True
        except (Exception, KeyboardInterrupt) as exc:
            if process is not None:
                stop_group(process)
            with mutex:
                arm.update(state="failed", exit_code=process.returncode if process is not None and process.returncode else 1,
                           terminated_at=now(), error=f"{type(exc).__name__}: {exc}",
                           source_review_at_termination=source_review(manifest["source"]))
                atomic_json(manifest_path, manifest)
            print(json.dumps({"failed": arm["id"], "error": arm["error"]}, ensure_ascii=False), flush=True)
            return False

    executor = ThreadPoolExecutor(max_workers=len(chosen))
    futures = []
    exit_code = 1
    try:
        futures = [executor.submit(arm_run, arm) for arm in chosen]
        results = [f.result() for f in as_completed(futures)]
        exit_code = 0 if all(results) else 1
        return exit_code
    finally:
        cancel.set()
        with mutex:
            active = list(processes.values())
        for process in active:
            stop_group(process)
        executor.shutdown(wait=True, cancel_futures=True)
        for sig, handler in old.items():
            signal.signal(sig, handler)
        session.update(state="finished" if exit_code == 0 else "failed", exit_code=exit_code, terminated_at=now(),
                       source_review_at_termination=source_review(manifest["source"]))
        manifest["wrapper_changed_during_run"] = session["source_review_at_termination"]["wrapper_changed_during_run"]
        atomic_json(manifest_path, manifest)
        atomic_json(namespace / "supervisor_status.json", session)
        fcntl.flock(lock_stream, fcntl.LOCK_UN)
        lock_stream.close()


def offline_score(name, selected, reconcile_smoke=False):
    from collect_verified_results import audit_arm, score_official_arm
    namespace = ROOT / "outputs" / name
    path = namespace / "manifest.json"
    manifest = json.loads(path.read_text())
    arms = [a for a in manifest["arms"] if a["id"] in selected]
    if len(arms) != len(set(selected)):
        raise RuntimeError("未知或重复评分 arm")
    if reconcile_smoke:
        if len(arms) != 1 or arms[0]["scope"] != "train_smoke" or arms[0].get("offline_scoring", {}).get("audit", {}).get("execution_verified"):
            raise RuntimeError("只允许对未验收首轮 train smoke 做无模型离线评分修复")
        if any(a.get("launch_count", 0) for a in manifest["arms"] if a["scope"] == "full_official_test"):
            raise RuntimeError("test 已开始，不允许改动其 source preflight 快照")
        if not arms[0].get("error", "").startswith("RuntimeError: 完成验收失败:"):
            raise RuntimeError("只能修复已记录的评分验收缺失，不能覆盖 solver/worker 失败")
    for arm in arms:
        verify_hashes({arm["config_path"]: arm["config_sha256"], **arm.get("bank", {}).get("frozen_hashes", {})})
        started = now()
        arm["independent_evaluation_path"] = str(namespace / f"{arm['id']}_independent_evaluation.json")
        score_official_arm(arm)
        audit = audit_arm(arm, require_finished=False, evaluation_path=arm["independent_evaluation_path"])
        report = {"started_at": started, "terminated_at": now(), "pid": os.getpid(), "exit_code": 0 if audit["execution_verified"] else 1,
                  "model_calls_made": 0, "trace_reruns": 0, "original_supervisor_failure_preserved": True,
                  "scoring_channel": "independent_official_scoring_original_execution_not_promoted",
                  "independent_evaluation_path": arm["independent_evaluation_path"],
                  "metadata_overlay": "仅沿显式终止run目录调用官方scorer，primary文件和原execution状态不覆盖",
                  "scorer_source": source_snapshot(), "audit": audit}
        if reconcile_smoke:
            if arm.get("offline_scoring"):
                arm.setdefault("offline_scoring_history", []).append(arm["offline_scoring"])
            arm["offline_scoring"] = report
            previous = manifest["source"]
            current = source_snapshot()
            manifest.setdefault("source_history", []).append({"source": previous, "superseded_at": now(),
                "reason": "test 启动前独立评分 metadata 修复；原smoke执行source保留，不重跑模型"})
            manifest["source"] = current
            atomic_json(path, manifest)
        atomic_json(namespace / f"{arm['id']}_offline_scoring.json", report)
        print(json.dumps({"arm": arm["id"], "execution_verified": audit["execution_verified"], "issues": audit["issues"], "model_calls_made": 0}, ensure_ascii=False), flush=True)
        if not audit["execution_verified"]:
            return 1
    return 0


def pipeline(name, selected):
    namespace = ROOT / "outputs" / name
    manifest = json.loads((namespace / "manifest.json").read_text())
    status = {"pid": os.getpid(), "started_at": now(), "terminated_at": None, "state": "running", "stages": [], "exit_code": None,
              "selected_test_arms": selected, "deadline": manifest["deadline"], "no_task_level_retry": True}
    atomic_json(namespace / "pipeline_pid.json", {"pid": os.getpid(), "started_at": status["started_at"], "deadline": manifest["deadline"]})
    atomic_json(namespace / "pipeline_status.json", status)
    print(json.dumps({"pipeline_pid": os.getpid(), "namespace": name, "selected": selected, "deadline": manifest["deadline"]}), flush=True)
    code = 1
    try:
        table = {a["id"]: a for a in manifest["arms"]}
        benches = {table[arm]["benchmark"] for arm in selected}
        for bench in sorted(benches):
            smoke = next(a for a in manifest["arms"] if a["scope"] == "train_smoke" and a["benchmark"] == bench)
            result = execute(name, [smoke["id"]])
            status["stages"].append({"stage": "train_smoke_primary", "arm": smoke["id"], "exit_code": result})
            atomic_json(namespace / "pipeline_status.json", status)
            if result:
                return result
        code = execute(name, selected)
        status["stages"].append({"stage": "full_official_test_primary", "arms": selected, "exit_code": code})
        return code
    finally:
        latest = json.loads((namespace / "manifest.json").read_text())
        from collect_verified_results import audit_arm
        results = [audit_arm(a) for a in latest["arms"] if a["id"] in selected or a["scope"] == "train_smoke"]
        atomic_json(namespace / "verified_results.json", {"updated_at": now(), "results": results,
                    "execution_and_independent_scoring_not_conflated": True, "launch_snapshot_never_replaced": True})
        status.update(terminated_at=now(), exit_code=code, state="finished" if code == 0 else "failed_or_deadline_partial")
        atomic_json(namespace / "pipeline_status.json", status)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "execute", "pipeline", "score", "rescore-smoke", "review-source"))
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--deadline", default=DEFAULT_DEADLINE)
    parser.add_argument("--arms", nargs="+")
    parser.add_argument("--bank-manifest", type=Path)
    parser.add_argument("--embedding-proof", type=Path)
    parser.add_argument("--wait-for-pid", type=int)
    args = parser.parse_args()
    require_remote()
    os.environ.update(THREAD_ENV)
    if args.action == "prepare":
        return prepare(args.namespace, args.deadline, args.arms, args.bank_manifest, args.embedding_proof)
    if args.action == "review-source":
        return review_legacy_launch(args.namespace, args.wait_for_pid)
    if not args.arms:
        parser.error("必须显式指定 --arms")
    if args.action in ("score", "rescore-smoke"):
        return offline_score(args.namespace, args.arms, reconcile_smoke=args.action == "rescore-smoke")
    if args.action == "pipeline":
        return pipeline(args.namespace, args.arms)
    return execute(args.namespace, args.arms)


if __name__ == "__main__":
    raise SystemExit(main())
