"""无 API 单测；fixture 模拟官方产物，不进行模型调用或 benchmark solve。"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from collect_verified_results import audit_arm, verified_run_directories, install_runtime_scoring_metadata
from run_verified_reproduction import MAX_WORKERS, THREAD_ENV, atomic_json, make_config, sha, stop_group, validate_plan, verify_hashes, endpoint_env, source_review, verify_execution_source, compatibility_approval, pipeline
from runtime_safety import _atomic_json, _marker_path, _started_path


class VerifiedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        atomic_json(self.directory / ".runtime_safety.json", {"runtime_safety_version": 1})
        self.arm = {"id": "appworld_baseline", "benchmark": "appworld", "method": "baseline", "scope": "full_official_test",
                    "state": "finished", "exit_code": 0, "parallel": 12, "num_runs": 5,
                    "experiment_name": "verified_fixture", "split": "test_normal", "task_ids": ["task_a", "task_b"],
                    "active_roles": {"solver": {"model": "openai/hy3", "reasoning_effort_requested": "high"}},
                    "output_directory": str(self.directory)}
        events, runs, rates = [], [], []
        for index in range(5):
            folder = self.directory / f"run_{index}"
            folder.mkdir()
            _atomic_json(folder / ".runtime_safety.json", {"runtime_safety_version": 1})
            scores = {}
            for tid in self.arm["task_ids"]:
                success = tid == "task_a" or index == 4
                scores[tid] = success
                eid = f"event_{index}_{tid}"
                event = {"event_id": eid, "status": "completed", "role": "solver", "requested_model": "openai/hy3",
                         "returned_model": "hy3", "request_id": f"request_{eid}", "task_id": tid, "run_idx": index,
                         "benchmark": "appworld", "experiment_name": self.arm["experiment_name"],
                         "tokens": {"prompt_tokens": 7, "completion_tokens": 3}}
                events.append(event)
                path = folder / f"{tid}.json"
                _atomic_json(path, {"task_id": tid, "experiment_name": self.arm["experiment_name"],
                                   "config": {"agent": {"model": "openai/hy3", "reasoning_effort": "high"},
                                              "run": {"num_runs": 5, "parallel": 12}},
                                   "success": success, "evaluation": {"success": success}, "usage_event_ids": [eid]})
                _atomic_json(_started_path(path), {"attempt_id": eid})
                _atomic_json(_marker_path(path), {"runtime_safety_version": 1, "state": "solve_task_returned",
                    "trace_file": path.name, "task_id": tid, "attempt_id": eid, "trace_sha256": sha(path)})
            rate = sum(scores.values())/2
            rates.append(rate)
            runs.append({"task_success": scores, "num_tasks": 2, "num_successes": sum(scores.values()), "success_rate": rate,
                         "appworld_evaluation": {"individual": {tid: {"success": value} for tid, value in scores.items()}}})
        self.usage = self.directory / "usage/launch/worker.jsonl"
        self.usage.parent.mkdir(parents=True)
        self.usage.write_text("\n".join(json.dumps(x) for x in events) + "\n")
        atomic_json(self.directory / "evaluation.json", {"experiment_name": self.arm["experiment_name"], "benchmark": "appworld", "per_run": runs,
            "aggregate": {"num_runs": 5, "num_tasks_per_run_all": [2]*5, "unequal_denominators": False,
                          "success_rate_per_run": rates, "success_rate_mean": sum(rates)/5},
            "usage": {"num_completed_calls": 10, "tokens_total": {"prompt_tokens": 70, "completion_tokens": 30}, "cost_complete": False, "estimated_total_cost_usd": 0}})

    def tearDown(self):
        self.temp.cleanup()

    def rewrite_trace(self, change):
        path = self.directory / "run_0/task_a.json"
        value = json.loads(path.read_text())
        change(value)
        atomic_json(path, value)
        marker = json.loads(_marker_path(path).read_text())
        marker["trace_sha256"] = sha(path)
        atomic_json(_marker_path(path), marker)

    def mutate_usage(self, change):
        data = [json.loads(l) for l in self.usage.read_text().splitlines()]
        change(data)
        self.usage.write_text("\n".join(json.dumps(x) for x in data)+"\n")

    def assert_invalid(self):
        result = audit_arm(self.arm)
        self.assertFalse(result["execution_verified"])
        self.assertIsNone(result["MSR"])
        self.assertTrue(result["issues"])

    def test_complete_accepts_legitimate_failures_without_retry(self):
        result = audit_arm(self.arm)
        self.assertTrue(result["execution_verified"], result["issues"])
        self.assertEqual(result["pass_pow_5"], .5)
        self.assertEqual(result["pass_at_5"], 1.0)
        self.assertEqual(result["MSR"], .6)
        self.assertIsNone(result["estimated_total_cost_usd"])
        self.assertFalse(result["method_fully_reproduced"])

    def test_old_trace_not_done(self):
        _marker_path(self.directory / "run_0/task_a.json").unlink()
        self.assert_invalid()

    def test_marker_attempt_mismatch(self):
        atomic_json(_started_path(self.directory / "run_0/task_a.json"), {"attempt_id": "other"})
        self.assert_invalid()

    def test_tampered_trace_hash(self):
        path = self.directory / "run_0/task_a.json"
        path.write_text(path.read_text()+" ")
        self.assert_invalid()

    def test_score_disagreement(self):
        self.rewrite_trace(lambda d: d.update(success=False))
        self.assert_invalid()

    def test_task_evaluation_disagreement(self):
        self.rewrite_trace(lambda d: d.update(evaluation={"success": False}))
        self.assert_invalid()

    def test_missing_official_task(self):
        (self.directory / "run_3/task_b.json").unlink()
        self.assert_invalid()

    def test_extra_task_trace(self):
        atomic_json(self.directory / "run_0/extra_task.json", {})
        self.assert_invalid()

    def test_unexpected_model(self):
        self.mutate_usage(lambda rows: rows[0].update(returned_model="gpt-unallowed"))
        self.assert_invalid()

    def test_usage_missing_returned_model(self):
        self.mutate_usage(lambda rows: rows[0].pop("returned_model"))
        self.assert_invalid()

    def test_usage_duplicate(self):
        self.mutate_usage(lambda rows: rows.append(rows[0]))
        self.assert_invalid()

    def test_usage_failed_call(self):
        self.mutate_usage(lambda rows: rows[0].update(status="error", error_type="Timeout"))
        self.assert_invalid()

    def test_usage_task_mismatch(self):
        self.mutate_usage(lambda rows: rows[0].update(task_id="task_b"))
        self.assert_invalid()

    def test_usage_token_summary_schema_and_value(self):
        path = self.directory / "evaluation.json"
        value = json.loads(path.read_text())
        value["usage"]["tokens_total"] = 100
        atomic_json(path, value)
        self.assert_invalid()
        value["usage"]["tokens_total"] = {"prompt_tokens": 71, "completion_tokens": 30}
        atomic_json(path, value)
        self.assert_invalid()

    def test_no_usage_not_accepted(self):
        self.usage.unlink()
        self.assert_invalid()

    def test_process_failure_not_accepted(self):
        self.arm["exit_code"] = 7
        self.assert_invalid()

    def test_legacy_and_partial_never_method_verified(self):
        for provenance, expected in (("legacy-bank", "verified_execution_legacy_bank_fidelity_unvalidated"),
                                     ("partial-bank", "verified_execution_partial_bank_diagnostic")):
            self.arm["bank"] = {"provenance": provenance}
            result = audit_arm(self.arm)
            self.assertEqual(result["status"], expected)
            self.assertFalse(result["eligible_for_method_claim"])

    def test_frozen_bank_tamper(self):
        bank = self.directory / "frozen_bank.json"
        bank.write_text("{}"); digest = sha(bank); bank.write_text("[]")
        self.arm["bank"] = {"provenance": "legacy-bank", "frozen_hashes": {str(bank): digest}}
        self.assert_invalid()

    def test_train_smoke_never_formal_score(self):
        self.arm["scope"] = "train_smoke"
        result = audit_arm(self.arm)
        self.assertEqual(result["status"], "verified_train_smoke_not_test_result")
        self.assertFalse(result["official_full_test_execution_verified"])
        self.assertIsNone(result["pass_pow_5"])

    def test_worker_budget_and_no_retry(self):
        arms = [{**self.arm, "id": name, "state": "planned", "parallel": count} for name, count in (("b",12),("a",8),("e",4))]
        self.assertEqual(sum(a["parallel"] for a in validate_plan(arms,["b","a","e"])), MAX_WORKERS)
        arms[2]["parallel"] = 8
        with self.assertRaises(RuntimeError): validate_plan(arms,["b","a","e"])
        with self.assertRaises(ValueError): validate_plan(arms,["b","b"])
        arms[0]["state"] = "finished"
        with self.assertRaises(RuntimeError): validate_plan(arms,["b"])

    def test_tau2_blocked_even_if_marked_planned(self):
        arm = {**self.arm, "benchmark": "tau2", "state": "planned"}
        with self.assertRaises(RuntimeError): validate_plan([arm],[arm["id"]])

    def test_all_dormant_roles_are_hy3_in_config(self):
        cfg = make_config(self.arm, self.directory)
        self.assertEqual(cfg["tau2"]["user_llm"], "openai/hy3")
        self.assertEqual(cfg["generation"]["judge_model"], "openai/hy3")
        self.assertEqual(cfg["accumulation"]["extraction_model"], "openai/hy3")
        self.assertFalse(cfg["run"]["force"])

    def test_environment_cpu_threads_and_endpoint_guard(self):
        for name in ("OMP_NUM_THREADS", "OMP_THREAD_LIMIT", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
            self.assertEqual(THREAD_ENV[name], "1")
        self.assertEqual(THREAD_ENV["CUDA_VISIBLE_DEVICES"], "-1")
        with patch.dict(os.environ, {"OPENAI_BASE_URL": "http://127.0.0.1:8742/v1", "OPENAI_API_KEY": "fixture"}):
            with self.assertRaises(RuntimeError): endpoint_env()

    def test_source_hash_change_rejected(self):
        p = self.directory / "source.py"
        p.write_text("x=1")
        verify_hashes({str(p): sha(p)})
        digest = sha(p); p.write_text("x=2")
        with self.assertRaises(RuntimeError): verify_hashes({str(p): digest})

    def test_official_scoring_ignores_only_valid_runtime_metadata(self):
        self.assertEqual(len(verified_run_directories(self.arm)), 5)
        atomic_json(self.directory / "real_flat_trace.json", {"task_id": "task_a"})
        with self.assertRaises(RuntimeError): verified_run_directories(self.arm)

    def test_official_scoring_rejects_unfinished_trace(self):
        _marker_path(self.directory / "run_0/task_a.json").unlink()
        with self.assertRaises(RuntimeError): verified_run_directories(self.arm)

    def test_official_scoring_rejects_invalid_runtime_metadata(self):
        atomic_json(self.directory / ".runtime_safety.json", {"runtime_safety_version": -1})
        with self.assertRaises(RuntimeError): verified_run_directories(self.arm)

    def test_runtime_entry_installs_metadata_before_primary_scoring(self):
        from daedalus.core.evaluation import evaluate
        previous = evaluate._NON_TRACE_FILES
        try:
            install_runtime_scoring_metadata()
            self.assertEqual(len(evaluate._detect_runs(self.directory)), 5)
            atomic_json(self.directory / "real_flat_trace.json", {})
            with self.assertRaises(RuntimeError): evaluate._detect_runs(self.directory)
        finally:
            evaluate._NON_TRACE_FILES = previous

    def test_memory_preserves_consolidated_full_initial_overlay(self):
        arm = {**self.arm, "method": "memory", "bank": {"frozen_directory": str(self.directory)}}
        cfg = make_config(arm, self.directory)
        self.assertTrue(cfg["memory"]["heuristics_at_start"])
        self.assertEqual(Path(cfg["memory"]["pool_path"]).name, "consolidated_pool.json")
        self.assertNotIn("retriever", cfg["memory"])
        self.assertTrue(arm["memory_overlay_provenance"]["no_bm25_topk_override"])

    def test_old_raw_memory_plan_is_rejected(self):
        arm = {**self.arm, "state": "planned", "method": "memory", "resolved_core_config": {"memory": {"pool_path": "pool.json", "heuristics_at_start": False}}}
        with self.assertRaises(RuntimeError): validate_plan([arm], [arm["id"]])

    def test_wrapper_change_does_not_replace_launch_snapshot_or_blame_old_worker(self):
        root = self.directory / "mock_root"
        scripts = root / "scripts"; scripts.mkdir(parents=True)
        path = scripts / "runtime_safety.py"; path.write_text("original")
        frozen = self.directory / "frozen_runtime.py"; frozen.write_text("original")
        snapshot = {"file_sha256": {str(path): sha(path)}, "execution_file_sha256": {str(frozen): sha(frozen)}}
        original = copy.deepcopy(snapshot)
        path.write_text("modified")
        with patch("run_verified_reproduction.ROOT", root):
            review = verify_execution_source(snapshot)
        self.assertEqual(len(review["wrapper_changed_during_run"]), 1)
        self.assertTrue(review["existing_workers_not_hot_reloaded"])
        self.assertEqual(snapshot, original)
        self.assertEqual(review["later_spawn_wrapper_version"], "frozen_namespace_snapshot")

    def test_frozen_execution_source_change_is_rejected(self):
        path = self.directory / "frozen.py"; path.write_text("original")
        snapshot = {"file_sha256": {}, "execution_file_sha256": {str(path): sha(path)}}
        path.write_text("changed")
        with self.assertRaises(RuntimeError): verify_execution_source(snapshot)

    def test_tau2_namespace_approval_validates_route_tests_and_hashes(self):
        root = self.directory / "approval_root"; scripts = root / "scripts"; scripts.mkdir(parents=True)
        hashes = {}
        for name in ("runtime_safety.py", "tau2_transport_safety.py"):
            path = scripts / name; path.write_text("fixture"); hashes[str(path)] = sha(path)
        evidence = root / "unit.log"; evidence.write_text("no_api_pass")
        atomic_json(root / "manifest.json", {"source": {"file_sha256": hashes}})
        approval = {"benchmark": "tau2", "approved": True, "route_verified": True, "no_api_tests_passed": True,
                    "model": "openai/hy3", "endpoint": "http://127.0.0.1:8743/v1", "source_hashes": hashes,
                    "evidence_sha256": {str(evidence): sha(evidence)}}
        atomic_json(root / "compatibility_approval.json", approval)
        arm = {**self.arm, "benchmark": "tau2", "state": "blocked_compatibility"}
        with patch("run_verified_reproduction.ROOT", root):
            self.assertEqual(len(validate_plan([arm], [arm["id"]], root)), 1)
            approval["no_api_tests_passed"] = False; atomic_json(root / "compatibility_approval.json", approval)
            with self.assertRaises(RuntimeError): validate_plan([arm], [arm["id"]], root)

    def test_independent_score_channel_never_promotes_failed_execution(self):
        self.arm["state"] = "failed"; self.arm["exit_code"] = 1
        result = audit_arm(self.arm, evaluation_path=self.directory / "evaluation.json")
        self.assertFalse(result["execution_verified"])
        self.assertEqual(result["scoring_channel"], "independent")
        self.assertEqual(self.arm["state"], "failed")

    def test_pipeline_stops_after_failed_train_smoke_without_test_retry(self):
        root = self.directory / "pipeline_root"; namespace = root / "outputs/verified_fixture"; namespace.mkdir(parents=True)
        smoke = {**self.arm, "id": "appworld_train_smoke", "scope": "train_smoke"}
        atomic_json(namespace / "manifest.json", {"arms": [smoke, self.arm], "deadline": "2026-10-16T15:33:00+08:00"})
        with patch("run_verified_reproduction.ROOT", root), patch("run_verified_reproduction.execute", return_value=1) as execute_mock, patch("collect_verified_results.audit_arm", return_value={"execution_verified": False}):
            self.assertEqual(pipeline("verified_fixture", [self.arm["id"]]), 1)
            execute_mock.assert_called_once_with("verified_fixture", ["appworld_train_smoke"])

    def test_supervised_process_is_reaped(self):
        process = subprocess.Popen([sys.executable, "-c", "import signal; signal.pause()"], start_new_session=True)
        stop_group(process)
        self.assertIsNotNone(process.returncode)
        self.assertNotEqual(process.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
