"""无 API：用 loopback 假上游证明 litellm/OpenAI SDK 的隐藏重试，以及安全层将其关闭。

只允许连接 127.0.0.1 上本测试自己起的假服务；任何其他地址一律拒绝，绝不触达 HY3。
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import sys
import threading
import unittest

os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
_original_connect = socket.socket.connect


def _loopback_only(self, address):
    if self.family in (socket.AF_INET, socket.AF_INET6) and address[0] not in ("127.0.0.1", "::1"):
        raise AssertionError(f"无 API 测试仅允许 loopback：{address}")
    return _original_connect(self, address)


socket.socket.connect = _loopback_only
sys.path.insert(0, str(Path(__file__).resolve().parent))


class _Upstream(BaseHTTPRequestHandler):
    hits = 0

    def do_POST(self):  # noqa: N802
        type(self).hits += 1
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        body = json.dumps({"error": {"message": "synthetic upstream failure", "type": "server_error"}}).encode()
        self.send_response(500)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class HiddenRetryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 其他测试模块会在导入时把网络整体拒绝；本类期间只放开 loopback，结束后恢复。
        cls._saved = (socket.socket.connect, socket.socket.connect_ex)
        socket.socket.connect = _loopback_only
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _Upstream)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}/v1"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        socket.socket.connect, socket.socket.connect_ex = cls._saved

    def call(self, completion):
        _Upstream.hits = 0
        with self.assertRaises(Exception):
            completion(model="openai/hy3", api_base=self.base, api_key="offline-placeholder",
                       messages=[{"role": "user", "content": "x"}], timeout=5)
        return _Upstream.hits

    def test_default_sdk_retries_are_hidden_and_patch_disables_them(self):
        import litellm
        original = litellm.completion
        try:
            hidden = self.call(original)
            import runtime_safety as safety
            safety._install_llm_transport()
            self.assertIsNot(litellm.completion, original)
            visible = self.call(litellm.completion)
            safety._install_llm_transport()  # 幂等
            self.assertEqual(self.call(litellm.completion), 1)
        finally:
            litellm.completion = original
        # 根因证据：未打补丁时一次 harness 尝试 = 多次上游请求，且都不写 ledger。
        print(f"\n[hidden-retry evidence] default upstream hits={hidden}, patched={visible}")
        self.assertGreater(hidden, 1)
        self.assertEqual(visible, 1)

    def test_tau2_bound_name_uses_patched_transport(self):
        import litellm
        from tau2.utils import llm_utils
        original, bound = litellm.completion, llm_utils.completion
        try:
            import runtime_safety as safety
            safety._install_llm_transport()
            safety._install_tau2_llm_transport()
            self.assertIs(llm_utils.completion, litellm.completion)
            self.assertTrue(getattr(llm_utils.completion, "_runtime_safety", False))
            self.assertEqual(self.call(llm_utils.completion), 1)
        finally:
            litellm.completion, llm_utils.completion = original, bound


class UserSimulatorProvenanceTests(unittest.TestCase):
    def test_sidecar_binds_event_ids_to_upstream_raw_data_in_order(self):
        import tempfile
        from types import SimpleNamespace
        from tau2.data_model.message import AssistantMessage, UserMessage
        import runtime_safety as safety
        from daedalus.benchmarks.tau2 import runner

        safety._install_tau2_user_provenance()
        safety._install_tau2_user_provenance()  # 幂等
        ids = iter(["ev1", "ev2", "ev3"])
        fake = SimpleNamespace(cfg=SimpleNamespace(tau2=SimpleNamespace(user_llm="openai/hy3")),
                               accounting=SimpleNamespace(record_external=lambda *a, **k: next(ids)))
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "exp" / "run_0"
            run_dir.mkdir(parents=True)
            logger = SimpleNamespace(task_id="0", trace_dir=run_dir,
                                     trace=SimpleNamespace(usage_event_ids=["solver-ev"], cost_complete=True))
            messages = [
                AssistantMessage(role="assistant", content="hi"),
                UserMessage(role="user", content="a", usage={"prompt_tokens": 3, "completion_tokens": 2},
                            raw_data={"model": "hy3", "id": "up-1"}),
                UserMessage(role="user", content="b", usage={"prompt_tokens": 4, "completion_tokens": 1},
                            raw_data={"model": "gpt-4.1", "id": "up-2"}),
                UserMessage(role="user", content="c"),  # 无 usage：上游不记账
            ]
            runner.Tau2TaskRunner._record_user_simulator_usage(fake, logger, None, messages)
            rows = [json.loads(l) for p in (Path(tmp) / "exp" / safety.PROVENANCE_DIR).glob("*.jsonl")
                    for l in p.read_text().splitlines()]
        self.assertEqual(logger.trace.usage_event_ids, ["solver-ev", "ev1", "ev2"])
        self.assertEqual([(r["event_id"], r["request_id"], r["verified"]) for r in rows],
                         [("ev1", "up-1", True), ("ev2", "up-2", False)])


if __name__ == "__main__":
    unittest.main()
