"""仅 any4 CPU：ignore hook 回归、实际 MPNet 编码、AppWorld 与 spawn，无 API。"""
from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
from types import ModuleType
import unittest
from unittest.mock import patch

import embedding_preflight as preflight


class LazyMLModule(ModuleType):
    def __dir__(self):
        raise AssertionError("freezegun 不得枚举 ML lazy module")


class GuardTests(unittest.TestCase):
    def test_config_extends_defaults_idempotently_without_freeze(self):
        import freezegun
        from freezegun.config import settings
        import freezegun.api

        before = list(settings.default_ignore_list)
        depth = len(freezegun.api.freeze_factories)
        preflight.configure_embedding_freezegun()
        first = list(settings.default_ignore_list)
        preflight.configure_embedding_freezegun()
        self.assertEqual(first, settings.default_ignore_list)
        self.assertTrue(set(before).issubset(first))
        self.assertTrue(set(preflight.ML_IGNORE_PREFIXES).issubset(first))
        self.assertEqual(depth, len(freezegun.api.freeze_factories))
        self.assertNotIn("appworld", first)
        self.assertNotIn("daedalus", first)

    def test_lazy_modules_not_enumerated_benchmark_time_unchanged(self):
        from freezegun import freeze_time

        preflight.configure_embedding_freezegun()
        lazy = {prefix + ".preflight_lazy": LazyMLModule(prefix + ".preflight_lazy")
                for prefix in preflight.ML_IGNORE_PREFIXES}
        frozen = datetime(2023, 5, 18, 12, 0, 0)
        with patch.dict(sys.modules, lazy):
            freezer = freeze_time(frozen)
            freezer.start()
            try:
                self.assertEqual(datetime.now(), frozen)
            finally:
                freezer.stop()
        self.assertNotEqual(datetime.now(), frozen)

    def test_hook_does_not_import_ml_or_start_freeze(self):
        code = '''import sys
import runtime_safety
import freezegun.api
from freezegun.config import settings
before = set(sys.modules)
runtime_safety._install_cpu_retrievers()
new = set(sys.modules) - before
assert not any(n == p or n.startswith(p + ".") for n in new
               for p in ("torch", "transformers", "sentence_transformers")), sorted(new)
assert not freezegun.api.freeze_factories
assert all(p in settings.default_ignore_list
           for p in ("torch", "transformers", "sentence_transformers"))
print("HOOK_NO_ML_IMPORT_NO_FREEZE")
'''
        root = Path(__file__).resolve().parents[1]
        code = f"import sys; sys.path.insert(0, {str(root / 'scripts')!r});\n" + code
        process = subprocess.run([sys.executable, "-c", code], capture_output=True,
                                 cwd=root / "vendor/daedalus", text=True, timeout=60)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.assertIn("HOOK_NO_ML_IMPORT_NO_FREEZE", process.stdout)

    def test_network_is_denied(self):
        import socket

        with preflight.deny_network(), socket.socket() as sock:
            with self.assertRaisesRegex(AssertionError, "禁止网络"):
                sock.connect(("127.0.0.1", 8743))


class ActualEmbeddingTests(unittest.TestCase):
    def test_actual_cpu_all_mpnet_freezegun_and_spawn(self):
        root = Path("/data/workspace/PredictMem")
        bank = Path(os.environ["PREDICTMEM_EMBEDDING_BANK"])
        output = Path(os.environ["PREDICTMEM_EMBEDDING_PROOF"])
        command = [sys.executable, str(root / "scripts/embedding_preflight.py"),
                   "--output", str(output), "--bank", str(bank),
                   "--appworld-task", "82e2fac_1"]
        process = subprocess.run(command, capture_output=True, text=True, timeout=900)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        proof = json.loads(output.read_text())
        self.assertEqual(proof["status"], "passed")
        self.assertEqual(proof["API_calls"], 0)
        self.assertEqual(proof["model"], preflight.EMBEDDER)
        self.assertTrue(proof["spawn_passed"])
        self.assertTrue(proof["spawn_vectors_bitwise_equal"])
        for check in (proof, proof["spawn"]):
            self.assertEqual(check["device"], "cpu")
            self.assertTrue(check["network_blocked"])
            self.assertTrue(check["model_import_and_load_outside_freeze"])
            self.assertTrue(check["freezegun_start_stop_passed"])
            self.assertTrue(check["real_time_restored"])
            self.assertTrue(check["top_2_unchanged"])
            self.assertTrue(check["embedding_vectors_bitwise_equal_before_after_guard_and_freeze"])
            self.assertTrue(check["AppWorld_noapi_check"]["AppWorld_initialized_and_closed"])
            self.assertEqual(check["guard"]["torch_intraop_threads"], 1)
            self.assertEqual(check["guard"]["torch_interop_threads"], 1)
        print(json.dumps({"proof": str(output), "parent_pid": proof["pid"],
                          "spawn_pid": proof["spawn"]["pid"], "API_calls": 0}), flush=True)


if __name__ == "__main__":
    preflight.offline_environment()
    unittest.main(verbosity=2)
