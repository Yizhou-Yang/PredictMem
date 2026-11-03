"""显式安装的 pinned harness 运行安全层；不改 vendor 源码或算法。"""
from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from contextvars import ContextVar
from functools import wraps
import importlib
import inspect
import json
import multiprocessing as mp
import os
from pathlib import Path
import runpy
import signal
import sys
import tempfile
import uuid

VERSION = 1
STALL_TIMEOUT_S = 1500
MANIFEST = ".runtime_safety.json"
_ACTIVE = ContextVar("runtime_safety_task", default=None)
_INSTALLED = set()


class PoolStalledError(RuntimeError):
    pass


def force_cpu():
    os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
    for key in ("OMP_NUM_THREADS", "OMP_THREAD_LIMIT", "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "RAYON_NUM_THREADS"):
        os.environ.setdefault(key, "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


force_cpu()


def _atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".writing-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def check_namespace(directory):
    """旧目录只读拒绝；绝不从 success 或现存 trace 推导完成状态。"""
    directory = Path(directory)
    manifest = directory / MANIFEST
    if manifest.exists():
        if json.loads(manifest.read_text()) != {"runtime_safety_version": VERSION}:
            raise RuntimeError(f"运行安全版本不兼容：{directory}")
    elif directory.exists() and any(directory.iterdir()):
        raise RuntimeError(f"拒绝复用旧产物目录，请使用全新独立 run：{directory}")


def ensure_namespace(directory):
    directory = Path(directory)
    check_namespace(directory)
    directory.mkdir(parents=True, exist_ok=True)
    manifest = directory / MANIFEST
    try:
        with manifest.open("x", encoding="utf-8") as stream:
            json.dump({"runtime_safety_version": VERSION}, stream)
    except FileExistsError:
        check_namespace(directory)


def _marker_path(trace):
    trace = Path(trace)
    return trace.parent / ".task_run_done" / trace.name


def _started_path(trace):
    trace = Path(trace)
    return trace.parent / ".task_run_started" / trace.name


def task_is_complete(trace, task_id=None):
    import hashlib

    trace = Path(trace)
    try:
        manifest = json.loads((trace.parent / MANIFEST).read_text())
        marker = json.loads(_marker_path(trace).read_text())
        started = json.loads(_started_path(trace).read_text())
        raw = trace.read_bytes()
        data = json.loads(raw)
        return (
            manifest == {"runtime_safety_version": VERSION}
            and isinstance(marker, dict)
            and isinstance(started, dict)
            and isinstance(data, dict)
            and marker.get("runtime_safety_version") == VERSION
            and marker.get("state") == "solve_task_returned"
            and marker.get("trace_file") == trace.name
            and marker.get("task_id") == data.get("task_id")
            and (task_id is None or marker.get("task_id") == str(task_id))
            and isinstance(marker.get("attempt_id"), str)
            and marker["attempt_id"] == started.get("attempt_id")
            and marker.get("trace_sha256") == hashlib.sha256(raw).hexdigest()
        )
    except (OSError, ValueError, TypeError):
        return False


def is_run_complete(trace_dir, task_ids):
    trace_dir = Path(trace_dir)
    return trace_dir.exists() and all(
        task_is_complete(trace_dir / f"{tid}.json", tid) for tid in task_ids
    )


def _start_trace(scope, path):
    path = Path(path)
    if path not in scope["started"]:
        ensure_namespace(path.parent)
        _atomic_json(_started_path(path), {"attempt_id": scope["attempt_id"]})
        scope["started"].add(path)


def _finish_trace(scope, path):
    import hashlib

    raw = path.read_bytes()
    data = json.loads(raw)
    if not isinstance(data, dict) or not isinstance(data.get("task_id"), str):
        raise RuntimeError(f"正常返回后的 trace 无效：{path}")
    _atomic_json(_marker_path(path), {
        "runtime_safety_version": VERSION,
        "state": "solve_task_returned",
        "task_id": data["task_id"],
        "trace_file": path.name,
        "run_directory": path.parent.name,
        "attempt_id": scope["attempt_id"],
        "trace_sha256": hashlib.sha256(raw).hexdigest(),
    })


def wrap_solver_class(cls):
    """包住最外层返回，reference 的 post-super 异常也不能生成 marker。"""
    for base in cls.__mro__:
        original = base.__dict__.get("solve_task")
        if original is None or getattr(original, "_runtime_safety", False):
            continue
        signature = inspect.signature(original)

        @wraps(original)
        def solve(self, *args, __original=original, __signature=signature, **kwargs):
            if _ACTIVE.get() is not None:
                return __original(self, *args, **kwargs)
            bound = __signature.bind(self, *args, **kwargs)
            values = dict(bound.arguments)
            values.update(values.get("kwargs", {}))
            tid = values["task_id"]
            override = values.get("task_override")
            if override is not None:
                tid = override.id
            suffix = values.get("trace_suffix", "")
            stem = f"{tid}_{suffix}" if suffix else str(tid)
            path = Path(self.trace_dir) / f"{stem}.json"
            ensure_namespace(path.parent)
            accumulation = any(values.get(k) is not None for k in
                               ("heuristics", "evaluator", "task_override"))
            scope = {"attempt_id": uuid.uuid4().hex, "started": set(), "saved": set()}
            if self.cfg.run.force or accumulation or not task_is_complete(path, tid):
                _start_trace(scope, path)
            token = _ACTIVE.set(scope)
            try:
                result = __original(self, *args, **kwargs)
                # 只在 solve_task 正常 return 后提交；合法失败与成功同等处理。
                for saved in scope["saved"]:
                    _finish_trace(scope, saved)
                return result
            finally:
                _ACTIVE.reset(token)

        solve._runtime_safety = True
        base.solve_task = solve


def _install_trace_logger():
    from daedalus.core.logging.trace_logger import TraceLogger

    if getattr(TraceLogger.save, "_runtime_safety", False):
        return
    original = TraceLogger.save

    @wraps(original)
    def save(self):
        scope = _ACTIVE.get()
        suffix = f"_{self.trace_suffix}" if self.trace_suffix else ""
        path = Path(self.trace_dir) / f"{self.task_id}{suffix}.json"
        ensure_namespace(path.parent)
        if scope is not None:
            _start_trace(scope, path)
        path = original(self)
        if scope is not None:
            scope["saved"].add(Path(path))
        return path

    save._runtime_safety = True
    TraceLogger.save = save
    TraceLogger.trace_exists = lambda self: task_is_complete(
        Path(self.trace_dir) / f"{self.task_id}{'_' + self.trace_suffix if self.trace_suffix else ''}.json",
        self.task_id,
    )


def _install_sentence_transformer():
    from embedding_preflight import prepare_embedding_runtime

    prepare_embedding_runtime()
    from sentence_transformers import SentenceTransformer

    original = SentenceTransformer.__init__
    if getattr(original, "_runtime_safety", False):
        return
    signature = inspect.signature(original)

    @wraps(original)
    def init(self, *args, **kwargs):
        force_cpu()
        bound = signature.bind_partial(self, *args, **kwargs)
        bound.arguments["device"] = "cpu"
        original(*bound.args, **bound.kwargs)

    init._runtime_safety = True
    SentenceTransformer.__init__ = init
    encode = SentenceTransformer.encode
    encode_signature = inspect.signature(encode)

    @wraps(encode)
    def encode_cpu(self, *args, **kwargs):
        bound = encode_signature.bind_partial(self, *args, **kwargs)
        bound.arguments["device"] = "cpu"
        return encode(*bound.args, **bound.kwargs)

    SentenceTransformer.encode = encode_cpu


def _cpu_expel_embedder(name):
    from references.expel import retrieval

    model = retrieval._MODELS.get(name)
    if model is None:
        _install_sentence_transformer()
        from sentence_transformers import SentenceTransformer
        model = retrieval._MODELS[name] = SentenceTransformer(name, device="cpu")
    return model


def _cpu_dense_model(self):
    from daedalus.core.memory import retrieval

    def build():
        _install_sentence_transformer()
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer(self._model_name, device="cpu", model_kwargs={"dtype": "bfloat16"})

    return retrieval._cached_model(self._model_name, build)


def _install_cpu_retrievers():
    from embedding_preflight import configure_embedding_freezegun
    from collect_verified_results import install_runtime_scoring_metadata

    configure_embedding_freezegun()
    install_runtime_scoring_metadata()
    # 仅安装工厂；不在 baseline/ACE 或无 API 测试启动时导入 torch、加载权重。
    from daedalus.core.memory import retrieval
    retrieval.DenseRetriever._load_model = _cpu_dense_model
    from references.expel import retrieval as expel
    expel._embedder = _cpu_expel_embedder


def _install_llm_transport():
    """关闭 litellm/OpenAI SDK 的隐藏重试（默认 2 次），让每次 HY3 尝试都落 ledger。

    ACE 1258 run_1 的 6b6ca61_2 在第 8 次调用上 ≥1079s 既无 completed 也无 failed 事件：
    客户端 timeout=600s 且 SDK 内部会对超时/5xx 静默重试 2 次（最坏 ~1800s），这些尝试
    既不进入 harness 的 6 次重试计数，也不写 usage ledger（可能已计费）。重试权归 harness。
    """
    import litellm

    original = litellm.completion
    if getattr(original, "_runtime_safety", False):
        return

    @wraps(original)
    def completion(*args, **kwargs):
        kwargs["max_retries"] = 0
        return original(*args, **kwargs)

    completion._runtime_safety = True
    litellm.completion = completion


def _install_tau2_llm_transport():
    """tau2 以 `from litellm import completion` 绑定名字；同样关闭 SDK 隐藏重试。

    tau2 自身协议的 litellm num_retries=3 保持不变（上游原协议），只去掉其下方再叠加的
    OpenAI SDK 2 次静默重试。
    """
    import litellm
    from tau2.utils import llm_utils

    llm_utils.completion = litellm.completion


PROVENANCE_DIR = "usage_provenance"  # 不在 usage/ 下：不改上游 ledger，也不计入 stall 心跳


def _install_tau2_user_provenance():
    """为上游 user_simulator 用量事件补充“真实返回模型/request_id”旁证。

    上游 `_record_user_simulator_usage` 经 record_external 记账，returned_model 直接写成
    请求模型、request_id 为空；但 tau2 的每条 UserMessage.raw_data 保留了上游响应的
    model 与 id。这里不改写任何 ledger 事件，只把 (event_id → raw_data.model/id) 按上游
    同一顺序追加到实验目录的 usage_provenance/worker_<pid>.jsonl；对不上即标 unverified。
    """
    from daedalus.benchmarks.tau2 import runner

    cls = runner.Tau2TaskRunner
    original = cls._record_user_simulator_usage
    if getattr(original, "_runtime_safety", False):
        return

    @wraps(original)
    def record(self, logger, sim, messages):
        from tau2.data_model.message import UserMessage

        before = len(logger.trace.usage_event_ids)
        result = original(self, logger, sim, messages)
        new_ids = [e for e in logger.trace.usage_event_ids[before:] if e]
        billed = [m for m in messages if isinstance(m, UserMessage) and getattr(m, "usage", None)]
        rows = []
        aligned = len(new_ids) == len(billed)
        for index, event_id in enumerate(new_ids):
            raw = (getattr(billed[index], "raw_data", None) or {}) if aligned else {}
            model, request_id = raw.get("model"), raw.get("id")
            rows.append({"event_id": event_id, "role": "user_simulator",
                         "returned_model": model, "request_id": request_id,
                         "source": "tau2 UserMessage.raw_data (upstream response)",
                         "verified": bool(aligned and model in ("hy3", "openai/hy3") and request_id)})
        if rows:
            directory = Path(logger.trace_dir).parent / PROVENANCE_DIR
            directory.mkdir(parents=True, exist_ok=True)
            with (directory / f"worker_{os.getpid()}.jsonl").open("a", encoding="utf-8") as stream:
                for row in rows:
                    stream.write(json.dumps(row, sort_keys=True) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
        return result

    record._runtime_safety = True
    cls._record_user_simulator_usage = record


def ledger_progress(root):
    """usage ledger 只追加：(文件数, 总字节) 变化即代表有 LLM 尝试结束（成功或失败）。"""
    if root is None:
        return None
    root = Path(root)
    files = [p for p in root.rglob("*.jsonl") if p.is_file()] if root.exists() else []
    return (len(files), sum(p.stat().st_size for p in files))


def _progress_probe(root):
    if root is None:
        return None
    return lambda: ledger_progress(root)


def completed_without_stall(futures, timeout=STALL_TIMEOUT_S, progress=None):
    """每次完成重新开始等待，绝非整个 iterator 的总时间预算。

    progress（可选）：返回可比较的进度令牌；窗口内无 task 完成但令牌变化（有 LLM 尝试
    落 ledger）则继续等待。窗口内既无完成也无已记录尝试才判定 stall。
    """
    pending = set(futures)
    last = progress() if progress is not None else None
    while pending:
        done, pending = wait(pending, timeout=timeout, return_when=FIRST_COMPLETED)
        if not done:
            current = progress() if progress is not None else None
            if progress is not None and current != last:
                last = current
                continue
            raise PoolStalledError(
                f"连续 {timeout} 秒没有 task 完成且没有新的 LLM ledger 事件，剩余 {len(pending)} 项")
        for future in done:
            yield future


def _worker_initializer():
    install(os.environ["PREDICTMEM_RUNTIME_BENCHMARK"],
            os.environ.get("PREDICTMEM_RUNTIME_METHOD") or None)


def solve_tasks_parallel(agent, task_ids, num_workers, run_ids=None):
    from daedalus.core.agents import task_pool as pool
    from daedalus.core.logging import console

    pairs = (list(zip(run_ids, task_ids, strict=True)) if run_ids is not None
             else [(agent.run_idx, t) for t in task_ids])
    cfg_dict = agent.cfg.to_dict()
    cls_path = pool.agent_class_path(agent)
    results = []
    bar = None
    executor = ProcessPoolExecutor(max_workers=num_workers, mp_context=mp.get_context("spawn"),
                                   initializer=_worker_initializer)
    handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
    pool._install_sigterm_reaper(executor)
    try:
        futures = {executor.submit(pool._solve_single_task, cfg_dict, tid, cls_path, idx): tid
                   for idx, tid in pairs}
        bar = console.progress_bar(len(task_ids), desc="solving")
        n_ok = 0
        progress = _progress_probe(_ledger_root(agent.cfg))
        for future in completed_without_stall(futures, pool._STALL_TIMEOUT_S, progress):
            result = future.result()  # worker 的任何异常直接传播，不能伪装成 {}。
            results.append(result)
            success = bool(result.get("success", False))
            n_ok += success
            if agent.cfg.logging.verbose:
                bar.write(f"  [done] {futures[future]} — {success}")
            bar.update(1)
            bar.set_postfix(ok=n_ok)
        return results
    finally:
        if bar is not None:
            bar.close()
        try:
            pool._shutdown_pool(executor)
        finally:
            _restore_signals(handlers)


def _restore_signals(handlers):
    for sig, handler in handlers.items():
        try:
            signal.signal(sig, handler)
        except ValueError:
            pass  # 非主线程无法安装/恢复 signal handler。


def run_reference_tasks(worker, jobs, args_of, max_workers):
    from daedalus.core.agents import task_pool as pool

    if max_workers == 1:
        return sorted([worker(*args_of(index, tid)) for index, tid in jobs], key=lambda r: r[0])
    executor = ProcessPoolExecutor(max_workers=max_workers, mp_context=mp.get_context("spawn"),
                                   initializer=_worker_initializer)
    handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
    pool._install_sigterm_reaper(executor)
    try:
        futures = [executor.submit(worker, *args_of(index, tid)) for index, tid in jobs]
        progress = _progress_probe(os.environ.get("PREDICTMEM_LEDGER_ROOT") or None)
        results = [f.result() for f in completed_without_stall(futures, pool._STALL_TIMEOUT_S, progress)]
        return sorted(results, key=lambda r: r[0])
    finally:
        try:
            pool._shutdown_pool(executor)
        finally:
            _restore_signals(handlers)


def _ledger_root(cfg):
    """与 UsageLedger 相同的落盘位置：<ledger_dir 或 experiment_dir>/usage。"""
    try:
        from daedalus.core.config import experiment_dir
        accounting = getattr(cfg, "cost_accounting", None)
        if accounting is None or not getattr(accounting, "enabled", False):
            return None
        base = Path(accounting.ledger_dir) if accounting.ledger_dir else experiment_dir(cfg)
        return base / "usage"
    except Exception:  # noqa: BLE001 —— 探针缺失只退化为“仅按完成计时”，不放宽判据
        return None


def _guard_config(cfg, create=True):
    from daedalus.core.config import experiment_dir, resolve_trace_dir

    root = _ledger_root(cfg)
    if root is not None:
        os.environ["PREDICTMEM_LEDGER_ROOT"] = str(root)
    directories = [experiment_dir(cfg)]
    if cfg.logging.trace_dir:
        directories.append(Path(cfg.logging.trace_dir))
    for directory in directories:
        check_namespace(directory)
    if create:
        for directory in directories:
            ensure_namespace(directory)
        traces = ([resolve_trace_dir(cfg, run_idx=i) for i in range(cfg.run.num_runs)]
                  if cfg.kind in ("inference", "testset") else [resolve_trace_dir(cfg)])
        for directory in traces:
            ensure_namespace(directory)


def install(benchmark, method=None):
    """入口和 spawn initializer 均须显式调用；无 sitecustomize 或 vendor 写入。"""
    force_cpu()
    if benchmark == "tau2":
        from tau2_transport_safety import install as install_tau2_transport
        install_tau2_transport()
    if benchmark not in ("tau2", "appworld") or method not in (None, "ace", "expel"):
        raise ValueError("运行安全层仅支持当前 core、ACE、ExpeL 的 tau2/appworld 入口")
    os.environ["PREDICTMEM_RUNTIME_BENCHMARK"] = benchmark
    os.environ["PREDICTMEM_RUNTIME_METHOD"] = method or ""
    key = (benchmark, method)
    if key in _INSTALLED:
        return
    _install_llm_transport()
    if benchmark == "tau2":
        _install_tau2_llm_transport()
    _install_cpu_retrievers()
    _install_trace_logger()
    from daedalus.core.agents import task_pool
    task_pool.solve_tasks_parallel = solve_tasks_parallel
    core = importlib.import_module("daedalus.core.evaluation.run_experiment")
    core._is_run_complete = is_run_complete
    if not getattr(core.run_experiment, "_runtime_safety", False):
        original = core.run_experiment

        @wraps(original)
        def core_run(cfg):
            _guard_config(cfg)
            return original(cfg)

        core_run._runtime_safety = True
        core.run_experiment = core_run
    # 先替换 task_pool，再导入 benchmark，避免 from-import 捕获旧函数。
    module = importlib.import_module(f"daedalus.benchmarks.{benchmark}.{'runner' if benchmark == 'tau2' else 'agent'}")
    module.solve_tasks_parallel = solve_tasks_parallel
    wrap_solver_class(module.Tau2TaskRunner if benchmark == "tau2" else module.ReActAgent)
    if benchmark == "tau2":
        _install_tau2_user_provenance()
    if method:
        common = importlib.import_module("references.common.run")
        common.is_run_complete = is_run_complete
        if not getattr(common.run_experiment, "_runtime_safety", False):
            original_ref = common.run_experiment

            @wraps(original_ref)
            def reference_run(spec, cfg, mcfg):
                _guard_config(cfg)
                return original_ref(spec, cfg, mcfg)

            reference_run._runtime_safety = True
            common.run_experiment = reference_run
        from references.common.solver import MethodSolverMixin
        MethodSolverMixin._would_skip = lambda self, tid: (
            not self.cfg.run.force and task_is_complete(Path(self.trace_dir) / f"{tid}.json", tid)
        )
        agents = importlib.import_module(f"references.{method}.agents")
        path = agents._AGENTS[benchmark]
        mod, name = path.rsplit(".", 1)
        wrap_solver_class(getattr(importlib.import_module(mod), name))
        accumulation = importlib.import_module("references.common.accumulation")
        accumulation.run_tasks = run_reference_tasks
        if not getattr(accumulation.save_run_config, "_runtime_safety", False):
            snapshot = accumulation.save_run_config

            @wraps(snapshot)
            def guarded_snapshot(cfg):
                _guard_config(cfg)
                return snapshot(cfg)

            guarded_snapshot._runtime_safety = True
            accumulation.save_run_config = guarded_snapshot
    _INSTALLED.add(key)


def _entry():
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", choices=("appworld", "tau2"), required=True)
    parser.add_argument("--method", choices=("ace", "expel"))
    parser.add_argument("module")
    args, rest = parser.parse_known_args()
    allowed = {"daedalus.scripts.inference", "daedalus.scripts.generation", "daedalus.scripts.consolidate"}
    allowed.update(f"references.{m}.{s}" for m in ("ace", "expel") for s in ("run", "accumulation"))
    if args.module not in allowed:
        parser.error("不支持的运行入口")
    install(args.benchmark, args.method)
    sys.argv = [args.module, *rest]
    runpy.run_module(args.module, run_name="__main__")


if __name__ == "__main__":
    # 避免 spawn 通过 __mp_main__ 找不到 initializer 和 context 状态分叉。
    sys.modules.setdefault("runtime_safety", sys.modules[__name__])
    _entry()
