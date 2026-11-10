"""仅 any4 CPU、离线且禁止网络的运行安全回归测试。"""
from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager
from types import SimpleNamespace
import unittest
from unittest.mock import patch

# spawn 会重新导入本文件；在所有依赖导入之前封锁网络和 GPU。
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
_original_connect = socket.socket.connect


def _deny_network(self, address):
    if self.family in (socket.AF_INET, socket.AF_INET6):
        raise AssertionError(f"无 API 测试禁止网络：{address}")
    return _original_connect(self, address)


socket.socket.connect = _deny_network
socket.socket.connect_ex = _deny_network
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime_safety as safety

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor" / "daedalus"


@contextmanager
def fake_modules(modules):
    # 只恢复替身键，不能清空期间真实导入的 numpy 等 C 扩展模块。
    missing = object()
    before = {key: sys.modules.get(key, missing) for key in modules}
    sys.modules.update(modules)
    try:
        yield
    finally:
        for key, value in before.items():
            if value is missing:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = value


class SyntheticAgent:
    """不构造 LLM 客户端，用于真实 spawn task pool。"""
    def __init__(self, cfg, run_idx=0):
        self.cfg = cfg
        self.run_idx = run_idx
        self.trace_dir = Path(cfg.logging.trace_dir) / f"run_{run_idx}"
        safety.wrap_solver_class(type(self))

    def solve_task(self, task_id):
        from daedalus.core.logging.trace_logger import TraceLogger, EvaluationResult
        logger = TraceLogger(task_id, "offline", {}, self.trace_dir)
        if logger.trace_exists() and not self.cfg.run.force:
            return {}
        logger.start_turn(0)
        logger.end_turn()
        if task_id == "error":
            raise ValueError("synthetic worker failure")
        if task_id == "hang":
            time.sleep(60)
        logger.log_evaluation(EvaluationResult(success=task_id == "ok"))
        logger.trace.extra["cpu_device_mask"] = os.environ["CUDA_VISIBLE_DEVICES"]
        logger.save()
        return logger.trace.to_dict()


def reference_worker(index, mode):
    if mode == "error":
        raise ValueError("synthetic reference failure")
    if mode == "hang":
        time.sleep(60)
    return index, mode


class _Bar:
    def write(self, *args):
        pass
    def update(self, *args):
        pass
    def set_postfix(self, **kwargs):
        pass
    def close(self):
        pass


class StallTests(unittest.TestCase):
    def test_total_runtime_exceeds_stall_budget_with_progress(self):
        with ThreadPoolExecutor(1) as executor:
            def job(index):
                time.sleep(0.10)
                return index
            futures = [executor.submit(job, i) for i in range(5)]
            start = time.monotonic()
            got = [f.result() for f in safety.completed_without_stall(futures, 0.28)]
        self.assertEqual(got, list(range(5)))
        self.assertGreater(time.monotonic() - start, 0.28)

    def test_timeout_after_one_completion(self):
        done, hung = Future(), Future()
        done.set_result("done")
        completed = safety.completed_without_stall([done, hung], 0.02)
        self.assertIs(next(completed), done)
        with self.assertRaises(safety.PoolStalledError):
            next(completed)

    def test_no_completion_is_fatal(self):
        with self.assertRaises(safety.PoolStalledError):
            list(safety.completed_without_stall([Future()], 0.02))

    def test_empty_pool(self):
        self.assertEqual(list(safety.completed_without_stall([], 0.01)), [])

    def test_duplicate_futures_not_double_counted(self):
        future = Future()
        future.set_result(1)
        self.assertEqual(list(safety.completed_without_stall([future, future], 0.01)), [future])


class PoolBoundaryTests(unittest.TestCase):
    def run_pool(self, outcomes):
        from daedalus.core.agents import task_pool
        from unittest.mock import MagicMock
        executor = MagicMock()
        futures = []
        for value in outcomes:
            future = Future()
            if isinstance(value, Exception):
                future.set_exception(value)
            else:
                future.set_result(value)
            futures.append(future)
        executor.submit.side_effect = futures
        agent = SimpleNamespace(cfg=SimpleNamespace(to_dict=lambda: {}, logging=SimpleNamespace(verbose=False)), run_idx=0)
        with patch.object(safety, "ProcessPoolExecutor", return_value=executor), patch.object(task_pool, "_install_sigterm_reaper"), patch.object(task_pool, "_shutdown_pool") as shutdown, patch("daedalus.core.logging.console.progress_bar", return_value=_Bar()), patch.object(safety, "completed_without_stall", return_value=iter(futures)):
            try:
                return safety.solve_tasks_parallel(agent, [str(i) for i in range(len(futures))], 2)
            finally:
                shutdown.assert_called_once_with(executor)

    def test_worker_exception_never_returns_partial(self):
        with self.assertRaisesRegex(ValueError, "worker"):
            self.run_pool([{"success": True}, ValueError("worker")])

    def test_stall_never_returns_partial(self):
        with self.assertRaises(safety.PoolStalledError):
            self.run_pool([{"success": True}, safety.PoolStalledError("stall")])

    def test_normal_false_result_is_not_worker_exception(self):
        self.assertEqual(self.run_pool([{"success": False}]), [{"success": False}])

    def test_fatal_llm_exception_propagates_without_live_call(self):
        from daedalus.core.llm.client import FatalLLMError
        with self.assertRaises(FatalLLMError):
            self.run_pool([FatalLLMError("offline synthetic fatal")])


class MarkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        safety._install_trace_logger()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / "run_2"
        self.cfg = SimpleNamespace(run=SimpleNamespace(force=False))

    def agent(self, mode="failure", suffix="", derived_error=False):
        from daedalus.core.logging.trace_logger import TraceLogger, EvaluationResult
        directory, cfg = self.directory, self.cfg

        class Base:
            def __init__(self):
                self.trace_dir, self.cfg = directory, cfg
            def solve_task(self, task_id, heuristics=None, trace_suffix=""):
                logger = TraceLogger(task_id, "offline", {}, self.trace_dir, trace_suffix=trace_suffix)
                if heuristics is None and not self.cfg.run.force and logger.trace_exists():
                    return {}
                logger.start_turn(0)
                logger.end_turn()
                if mode == "exception":
                    raise RuntimeError("after intermediate trace")
                if mode == "interrupt":
                    raise KeyboardInterrupt()
                if mode == "empty":
                    return {}
                logger.log_evaluation(EvaluationResult(success=mode == "success"))
                logger.save()
                return logger.trace.to_dict()

        class Reference(Base):
            def solve_task(self, task_id, **kwargs):
                result = super().solve_task(task_id, **kwargs)
                self.marker_inside_super = safety.task_is_complete(directory / f"{task_id}.json", task_id)
                if derived_error:
                    raise RuntimeError("reference post-super error")
                return result

        cls = Reference if derived_error or mode == "outer" else Base
        safety.wrap_solver_class(cls)
        return cls()

    def path(self, stem="task"):
        return self.directory / f"{stem}.json"

    def test_normal_success_marked(self):
        result = self.agent("success").solve_task("task")
        self.assertTrue(result["success"])
        self.assertTrue(safety.task_is_complete(self.path(), "task"))
        self.assertEqual(json.loads(safety._marker_path(self.path()).read_text())["run_directory"], "run_2")

    def test_normal_failure_marked(self):
        result = self.agent().solve_task("task")
        self.assertFalse(result["success"])
        self.assertTrue(safety.task_is_complete(self.path(), "task"))

    def test_exception_keeps_trace_without_marker(self):
        with self.assertRaises(RuntimeError):
            self.agent("exception").solve_task("task")
        self.assertTrue(self.path().exists())
        self.assertFalse(safety._marker_path(self.path()).exists())
        self.assertFalse(safety.task_is_complete(self.path(), "task"))

    def test_interrupt_without_marker(self):
        with self.assertRaises(KeyboardInterrupt):
            self.agent("interrupt").solve_task("task")
        self.assertFalse(safety._marker_path(self.path()).exists())

    def test_reference_post_super_exception_not_marked(self):
        agent = self.agent(derived_error=True)
        with self.assertRaises(RuntimeError):
            agent.solve_task("task")
        self.assertFalse(agent.marker_inside_super)
        self.assertFalse(safety._marker_path(self.path()).exists())

    def test_marker_only_after_outer_return(self):
        agent = self.agent("outer")
        agent.solve_task("task")
        self.assertFalse(agent.marker_inside_super)
        self.assertTrue(safety.task_is_complete(self.path(), "task"))

    def test_trace_tampering_invalidates_marker(self):
        self.agent().solve_task("task")
        self.path().write_text(self.path().read_text() + "\n")
        self.assertFalse(safety.task_is_complete(self.path(), "task"))

    def test_marker_tampering_invalidates_marker(self):
        self.agent().solve_task("task")
        marker = json.loads(safety._marker_path(self.path()).read_text())
        marker["trace_sha256"] = "0" * 64
        safety._marker_path(self.path()).write_text(json.dumps(marker))
        self.assertFalse(safety.task_is_complete(self.path(), "task"))

    def test_wrong_task_id_is_not_done(self):
        self.agent().solve_task("task")
        self.assertFalse(safety.task_is_complete(self.path(), "other"))

    def test_partial_default_success_never_done_or_backfilled(self):
        safety.ensure_namespace(self.directory)
        self.path().write_text('{"task_id":"task","success":false,"turns":[]}')
        self.assertFalse(safety.is_run_complete(self.directory, ["task"]))
        self.assertFalse(safety._marker_path(self.path()).exists())

    def test_existing_success_never_done_or_backfilled(self):
        safety.ensure_namespace(self.directory)
        self.path().write_text('{"task_id":"task","success":true}')
        self.assertFalse(safety.task_is_complete(self.path(), "task"))
        self.assertFalse(safety._marker_path(self.path()).exists())

    def test_partial_trace_is_not_skipped(self):
        safety.ensure_namespace(self.directory)
        self.path().write_text('{"task_id":"task","success":false}')
        result = self.agent("success").solve_task("task")
        self.assertTrue(result["success"])
        self.assertTrue(safety.is_run_complete(self.directory, ["task"]))

    def test_complete_trace_skips_without_rewriting_marker(self):
        agent = self.agent()
        agent.solve_task("task")
        before = safety._marker_path(self.path()).read_bytes()
        self.assertEqual(agent.solve_task("task"), {})
        self.assertEqual(safety._marker_path(self.path()).read_bytes(), before)

    def test_force_exception_invalidates_previous_done_preserving_artifacts(self):
        self.agent().solve_task("task")
        before = safety._marker_path(self.path()).read_bytes()
        self.cfg.run.force = True
        with self.assertRaises(RuntimeError):
            self.agent("exception").solve_task("task")
        self.assertFalse(safety.task_is_complete(self.path(), "task"))
        self.assertEqual(safety._marker_path(self.path()).read_bytes(), before)

    def test_suffix_marker_does_not_complete_plain_inference_task(self):
        self.agent().solve_task("task", heuristics=[], trace_suffix="attempt1")
        self.assertTrue(safety.task_is_complete(self.path("task_attempt1"), "task"))
        self.assertFalse(safety.is_run_complete(self.directory, ["task"]))

    def test_legacy_directory_rejected_unchanged(self):
        self.directory.mkdir()
        self.path().write_text('{"task_id":"task","success":true}')
        before = self.path().read_bytes()
        with self.assertRaisesRegex(RuntimeError, "全新独立 run"):
            self.agent().solve_task("task")
        self.assertEqual(self.path().read_bytes(), before)
        self.assertEqual(list(self.directory.iterdir()), [self.path()])

    def test_malformed_marker_not_done(self):
        self.agent().solve_task("task")
        safety._marker_path(self.path()).write_text("[]")
        self.assertFalse(safety.task_is_complete(self.path(), "task"))

    def test_incompatible_manifest_rejected(self):
        safety.ensure_namespace(self.directory)
        (self.directory / safety.MANIFEST).write_text('{"runtime_safety_version":999}')
        with self.assertRaises(RuntimeError):
            safety.ensure_namespace(self.directory)

    def test_save_without_solve_return_does_not_mark(self):
        from daedalus.core.logging.trace_logger import TraceLogger
        safety.ensure_namespace(self.directory)
        TraceLogger("task", "offline", {}, self.directory).save()
        self.assertTrue(self.path().exists())
        self.assertFalse(safety._marker_path(self.path()).exists())


class InstallationTests(unittest.TestCase):
    def test_cpu_explicit_device_constructor_and_encode_without_model_load(self):
        calls = []
        class SentenceTransformer:
            def __init__(self, model_name_or_path=None, device=None, **kwargs):
                calls.append((model_name_or_path, device, kwargs))
            def encode(self, sentences, device=None, **kwargs):
                calls.append((sentences, device, kwargs))
                return "offline"
        with fake_modules({"sentence_transformers": SimpleNamespace(SentenceTransformer=SentenceTransformer)}):
            safety._install_sentence_transformer()
            os.environ["CUDA_VISIBLE_DEVICES"] = "0"
            model = SentenceTransformer("fake-model", "cuda", model_kwargs={"dtype": "bfloat16"})
            self.assertEqual(model.encode(["x"], "cuda", normalize_embeddings=True), "offline")
        self.assertEqual(os.environ["CUDA_VISIBLE_DEVICES"], "-1")
        self.assertEqual(calls[0], ("fake-model", "cpu", {"model_kwargs": {"dtype": "bfloat16"}}))
        self.assertEqual(calls[1], (["x"], "cpu", {"normalize_embeddings": True}))

    def test_embedding_factories_keep_cache_and_force_cpu(self):
        from references.expel import retrieval as expel
        from daedalus.core.memory import retrieval as dense
        calls = []
        class SentenceTransformer:
            def __init__(self, name, device=None, **kwargs):
                calls.append((name, device, kwargs))
            def encode(self, sentences, device=None):
                return sentences
        with fake_modules({"sentence_transformers": SimpleNamespace(SentenceTransformer=SentenceTransformer)}), patch.dict(expel._MODELS, clear=True), patch.dict(dense._MODEL_CACHE, clear=True):
            safety._install_cpu_retrievers()
            first = expel._embedder("fake-expel")
            self.assertIs(expel._embedder("fake-expel"), first)
            retriever = dense.DenseRetriever(model_name="fake-dense")
            first_dense = retriever._load_model()
            self.assertIs(retriever._load_model(), first_dense)
        self.assertEqual(calls, [("fake-expel", "cpu", {}),
                                 ("fake-dense", "cpu", {"model_kwargs": {"dtype": "bfloat16"}})])

    def test_core_and_references_installation_and_skip_aliases(self):
        for method in (None, "ace", "expel"):
            safety.install("tau2", method)
            safety.install("tau2", method)
        from daedalus.core.agents import task_pool
        from daedalus.benchmarks.tau2 import runner
        core = importlib.import_module("daedalus.core.evaluation.run_experiment")
        from references.common import run, accumulation
        self.assertIs(task_pool.solve_tasks_parallel, safety.solve_tasks_parallel)
        self.assertIs(runner.solve_tasks_parallel, safety.solve_tasks_parallel)
        self.assertIs(core._is_run_complete, safety.is_run_complete)
        self.assertIs(run.is_run_complete, safety.is_run_complete)
        self.assertIs(accumulation.run_tasks, safety.run_reference_tasks)
        from references.common.solver import MethodSolverMixin
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / "t.json").write_text('{"task_id":"t","success":true}')
            obj = SimpleNamespace(cfg=SimpleNamespace(run=SimpleNamespace(force=False)), trace_dir=folder)
            self.assertFalse(MethodSolverMixin._would_skip(obj, "t"))

    def test_appworld_installation_aliases(self):
        # 读取真实 vendor agent/method 类，仅替换未使用的 AppWorld 环境依赖。
        with fake_modules({"appworld": SimpleNamespace(AppWorld=object),
                                     "appworld.task": SimpleNamespace(load_task_ids=lambda *args: [])}):
            for method in (None, "ace", "expel"):
                safety.install("appworld", method)
        from daedalus.benchmarks.appworld import agent
        self.assertIs(agent.solve_tasks_parallel, safety.solve_tasks_parallel)
        self.assertTrue(agent.ReActAgent.solve_task._runtime_safety)
        safety.install("tau2", "expel")

    def test_new_config_namespace_created_and_old_config_rejected(self):
        from daedalus.core.config import ExperimentConfig
        with tempfile.TemporaryDirectory() as temp:
            cfg = ExperimentConfig()
            cfg.kind = "inference"
            cfg.logging.trace_dir = str(Path(temp) / "traces")
            cfg.run.num_runs = 2
            with patch("daedalus.core.config.experiment_dir", return_value=Path(temp) / "experiment"):
                safety._guard_config(cfg)
                self.assertTrue((Path(temp) / "traces/run_1" / safety.MANIFEST).exists())
            old = Path(temp) / "old"
            old.mkdir()
            (old / "run_meta.json").write_text("{}")
            with patch("daedalus.core.config.experiment_dir", return_value=old):
                with self.assertRaises(RuntimeError):
                    safety._guard_config(cfg)
            self.assertEqual(list(old.iterdir()), [old / "run_meta.json"])

    def test_run_entry_dispatches_all_phases_explicitly_and_cpu(self):
        import run
        from dotenv import load_dotenv
        lock = json.loads((ROOT / "sources.lock.json").read_text())
        commits = list({".": lock["daedalus"]["commit"], **lock["daedalus"]["submodules"]}.values())
        for benchmark in ("tau2", "appworld"):
            for phase in run.CORE_PHASES + run.REFERENCE_PHASES:
                with self.subTest(benchmark=benchmark, phase=phase), patch.object(sys, "argv", ["run.py", phase, benchmark]), patch("dotenv.load_dotenv"), patch.dict(os.environ, {"OPENAI_BASE_URL": "offline", "OPENAI_API_KEY": "offline", "CUDA_VISIBLE_DEVICES": "0"}), patch.object(run.subprocess, "check_output", side_effect=[c+"\n" for c in commits]), patch.object(run.subprocess, "run") as launch:
                    run.main()
                    command = launch.call_args.args[0]
                    self.assertEqual(launch.call_args.kwargs["env"]["CUDA_VISIBLE_DEVICES"], "-1")
                    self.assertEqual(command[0], str(VENDOR / ".venv/bin/python"))
                    self.assertIn(command[1], (str(ROOT / "scripts/runtime_safety.py"), str(ROOT / "scripts/tau2_hy3_eval.py")))
                    self.assertNotIn("-m", command)

    def test_tau2_entry_installs_before_upstream_main(self):
        import tau2_hy3_eval as tau
        for entry in ("inference", "generation", "ace_inference", "expel_inference", "ace_accumulation", "expel_accumulation"):
            module = ("daedalus.scripts." + entry if "_" not in entry else
                      "references." + entry.rsplit("_", 1)[0] + (".run" if entry.endswith("inference") else ".accumulation"))
            events = []
            mod = SimpleNamespace(main=lambda *args: events.append("main"), METHOD=object())
            with fake_modules({module: mod}), patch.object(sys, "argv", ["tau2_hy3_eval.py", entry, "--help"]), patch.object(tau, "install", side_effect=lambda *args: events.append("install")):
                tau._entry()
            self.assertEqual(events, ["install", "main"])
        self.assertEqual(tau._nl.DEFAULT_LLM_NL_ASSERTIONS, "openai/hy3")

    def test_source_lock_clean(self):
        lock = json.loads((ROOT / "sources.lock.json").read_text())
        for directory, expected in {".": lock["daedalus"]["commit"], **lock["daedalus"]["submodules"]}.items():
            actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=VENDOR / directory, text=True).strip()
            self.assertEqual(actual, expected)
            for args in (["diff", "--quiet"], ["diff", "--cached", "--quiet"]):
                subprocess.run(["git", *args], cwd=VENDOR / directory, check=True)


class ProcessTests(unittest.TestCase):
    def probe(self, mode, expected=1):
        process = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--probe", mode],
                                 cwd=VENDOR, capture_output=True, text=True, timeout=45)
        if expected == 0:
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        else:
            self.assertNotEqual(process.returncode, 0, process.stdout + process.stderr)
        return process.stdout + process.stderr

    def test_worker_exception_exits_nonzero(self):
        self.assertIn("synthetic worker failure", self.probe("core-error"))

    def test_stall_exits_nonzero_after_partial_completion(self):
        output = self.probe("core-stall")
        self.assertIn("PoolStalledError", output)
        self.assertIn("PARTIAL_COMPLETE_THEN_STALL", output)

    def test_reference_parallel_exception_exits_nonzero(self):
        self.assertIn("synthetic reference failure", self.probe("reference-error"))

    def test_reference_serial_exception_exits_nonzero(self):
        self.assertIn("synthetic reference failure", self.probe("reference-serial-error"))

    def test_reference_stall_exits_nonzero(self):
        self.assertIn("PoolStalledError", self.probe("reference-stall"))

    def test_real_spawn_normal_failure_marker_and_cpu(self):
        self.assertIn("SPAWN_NORMAL_FAILURE_MARKED_CPU", self.probe("core-normal", 0))


def _probe(mode):
    safety.install("tau2", "expel")
    from daedalus.core.agents import task_pool
    from daedalus.core.config import ExperimentConfig
    task_pool._STALL_TIMEOUT_S = 12 if "stall" in mode else 20
    shutdown = task_pool._shutdown_pool
    task_pool._shutdown_pool = lambda executor: shutdown(executor, grace=0.1)
    # probe 主进程即将退出，不留下指向已关闭 executor 的 signal handler。
    handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        with tempfile.TemporaryDirectory() as temp:
            if mode.startswith("reference"):
                job_mode = "hang" if "stall" in mode else "error"
                safety.run_reference_tasks(reference_worker, [(0, job_mode)], lambda i, t: (i, t),
                                           1 if "serial" in mode else 2)
                return
            cfg = ExperimentConfig()
            cfg.logging.trace_dir = temp
            cfg.logging.verbose = False
            ids = ["ok", "hang"] if "stall" in mode else ["error"] if "error" in mode else ["failure"]
            agent = SyntheticAgent(cfg)
            try:
                results = safety.solve_tasks_parallel(agent, ids, 1)
            except safety.PoolStalledError:
                if mode == "core-stall":
                    assert safety.task_is_complete(Path(temp) / "run_0/ok.json", "ok")
                    print("PARTIAL_COMPLETE_THEN_STALL", flush=True)
                raise
            assert len(results) == len(ids)
            assert results[0]["success"] is False
            assert results[0]["extra"]["cpu_device_mask"] == "-1"
            assert safety.task_is_complete(Path(temp) / "run_0/failure.json", "failure")
            assert os.environ["CUDA_VISIBLE_DEVICES"] == "-1"
            print("SPAWN_NORMAL_FAILURE_MARKED_CPU")
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--probe":
        _probe(sys.argv[2])
    else:
        unittest.main(verbosity=2)
