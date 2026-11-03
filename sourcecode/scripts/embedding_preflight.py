"""CPU embedding 兼容与离线实测；仅隔离 freezegun 对 ML lazy modules 的扫描。"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from contextlib import contextmanager
import datetime as dt
import hashlib
import importlib.metadata
import json
import multiprocessing as mp
import os
from pathlib import Path
import socket
import sys

EMBEDDER = "sentence-transformers/all-mpnet-base-v2"
ML_IGNORE_PREFIXES = ("transformers", "sentence_transformers", "torch")


def configure_embedding_freezegun():
    """freeze 创建前显式配置；不导入 ML、不改默认 ignore 或基准冻结时刻。"""
    import freezegun

    freezegun.configure(extend_ignore_list=list(ML_IGNORE_PREFIXES))
    return {"freezegun_ignored_module_prefixes": list(ML_IGNORE_PREFIXES),
            "retrieval_algorithm_changed": False, "AppWorld_safety_disabled": False}


def prepare_embedding_runtime():
    guard = configure_embedding_freezegun()
    import torch

    torch.set_num_threads(1)
    if torch.get_num_interop_threads() != 1:
        torch.set_num_interop_threads(1)
    return {**guard, "torch_intraop_threads": torch.get_num_threads(),
            "torch_interop_threads": torch.get_num_interop_threads(),
            "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES")}


@contextmanager
def deny_network():
    """每个实测进程封锁外部网络；保留 multiprocessing 所需 Unix socket。"""
    from unittest.mock import patch

    connect, connect_ex, sendto = socket.socket.connect, socket.socket.connect_ex, socket.socket.sendto

    def blocked(original):
        def call(sock, *args, **kwargs):
            if sock.family in (socket.AF_INET, socket.AF_INET6):
                raise AssertionError("离线 embedding preflight 禁止网络/API")
            return original(sock, *args, **kwargs)
        return call

    with patch.object(socket.socket, "connect", blocked(connect)), \
         patch.object(socket.socket, "connect_ex", blocked(connect_ex)), \
         patch.object(socket.socket, "sendto", blocked(sendto)), \
         patch.object(socket, "getaddrinfo", side_effect=AssertionError("离线测试禁止 DNS")):
        yield


def offline_environment():
    from run_verified_reproduction import ROOT, VENDOR, THREAD_ENV, require_remote

    require_remote()
    os.chdir(VENDOR)
    os.environ.update(THREAD_ENV)
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
                      HF_HUB_DISABLE_TELEMETRY="1", LITELLM_LOCAL_MODEL_COST_MAP="True")
    sys.path.insert(0, str(VENDOR))
    return ROOT, VENDOR


def _encode_and_freeze(bank, appworld_task=None, experiment_name=None, install_spawn=False):
    from run_verified_reproduction import ROOT, sha
    from freezegun import freeze_time
    import freezegun.api

    if freezegun.api.freeze_factories:
        raise AssertionError("模型导入和加载必须在基准 freeze 之外")
    # 配置前、freeze 之外真实导入和加载，与修复后数值进行逐位对照。
    import numpy as np
    import torch
    from sentence_transformers import SentenceTransformer
    from references.expel.retrieval import load_demonstrations

    torch.set_num_threads(1)
    if torch.get_num_interop_threads() != 1:
        torch.set_num_interop_threads(1)
    bank = Path(bank)
    demos_path = bank.with_name("demonstrations.json")
    bank_hashes = {str(p): sha(p) for p in (bank, demos_path)}
    demos = load_demonstrations(demos_path)
    if len(demos) < 2:
        raise RuntimeError("需要至少两个 demonstration 验证原 top-2")
    model = SentenceTransformer(EMBEDDER, device="cpu", local_files_only=True)
    if str(model.device) != "cpu":
        raise AssertionError("只允许 CPU embedding")
    texts = [d.task for d in demos]
    query = ["Find the most-liked song in my Spotify playlists."]
    matrix_before = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    query_before = model.encode(query, normalize_embeddings=True, show_progress_bar=False)
    order_before = np.argsort(matrix_before @ query_before[0])[::-1][:2]
    import runtime_safety

    if install_spawn:
        runtime_safety.install("appworld", "expel")
    else:
        runtime_safety._install_cpu_retrievers()
    guard = prepare_embedding_runtime()
    frozen_at = dt.datetime(2023, 5, 18, 12, 0, 0)
    freezer = freeze_time(frozen_at)
    freezer.start()
    try:
        if dt.datetime.now() != frozen_at:
            raise AssertionError("基准冻结时间改变")
        matrix_after = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        query_after = model.encode(query, normalize_embeddings=True, show_progress_bar=False)
        order_after = np.argsort(matrix_after @ query_after[0])[::-1][:2]
        if dt.datetime.now() != frozen_at:
            raise AssertionError("编码改变了基准冻结时间")
    finally:
        freezer.stop()
    if dt.datetime.now().year == 2023 or freezegun.api.freeze_factories:
        raise AssertionError("freezegun.stop 未恢复时间")
    vectors_same = np.array_equal(matrix_before, matrix_after) and np.array_equal(query_before, query_after)
    rankings_same = np.array_equal(order_before, order_after)
    if not vectors_same or not rankings_same:
        raise RuntimeError("兼容修复改变了 embedding 向量或原 top-2 检索")
    world_check = None
    if appworld_task:
        from appworld import AppWorld

        with AppWorld(task_id=appworld_task, experiment_name=experiment_name) as world:
            encoded = model.encode(query, normalize_embeddings=True, show_progress_bar=False)
            if not np.array_equal(encoded, query_before):
                raise AssertionError("AppWorld 内编码改变")
            world_check = {"task_id": world.task.id, "AppWorld_initialized_and_closed": True,
                           "embedding_same_inside_world": True, "LLM_calls": 0}
        if freezegun.api.freeze_factories:
            raise AssertionError("AppWorld 退出后 freeze 残留")
    if any(sha(p) != digest for p, digest in bank_hashes.items()):
        raise AssertionError("实测期间 bank 改变")
    return {"pid": os.getpid(), "API_calls": 0, "network_blocked": True,
            "device": str(model.device), "guard": guard,
            "model_import_and_load_outside_freeze": True, "freezegun_start_stop_passed": True,
            "benchmark_frozen_datetime": frozen_at.isoformat(), "real_time_restored": True,
            "bank_hashes": bank_hashes, "num_demonstrations": len(demos),
            "matrix_shape": list(matrix_before.shape),
            "embedding_vectors_bitwise_equal_before_after_guard_and_freeze": vectors_same,
            "top_2_unchanged": rankings_same,
            "selected_demonstration_task_ids": [demos[int(i)].task_id for i in order_before],
            "matrix_sha256": hashlib.sha256(matrix_before.tobytes()).hexdigest(),
            "query_sha256": hashlib.sha256(query_before.tobytes()).hexdigest(),
            "AppWorld_noapi_check": world_check,
            "source_hashes": {str(Path(__file__).resolve()): sha(__file__),
                              str(ROOT / "scripts/runtime_safety.py"): sha(runtime_safety.__file__)},
            "runtime_safety_import_path": runtime_safety.__file__}


def _spawn_probe(bank, appworld_task, experiment_name):
    offline_environment()
    with deny_network():
        result = _encode_and_freeze(bank, appworld_task, experiment_name, install_spawn=True)
    result["multiprocessing_start_method"] = mp.get_start_method()
    return result


def verify(output, bank, appworld_task=None):
    ROOT, _ = offline_environment()
    from run_verified_reproduction import atomic_json

    output = Path(output)
    if output.exists():
        raise RuntimeError("拒绝覆盖已有 preflight 证据")
    started = dt.datetime.now().astimezone().isoformat()
    with deny_network():
        parent = _encode_and_freeze(bank, appworld_task, output.stem + "_parent_noapi")
        with ProcessPoolExecutor(max_workers=1, mp_context=mp.get_context("spawn")) as executor:
            child = executor.submit(_spawn_probe, str(bank), appworld_task,
                                    output.stem + "_spawn_noapi").result(timeout=600)
    if child["pid"] == parent["pid"] or child["multiprocessing_start_method"] != "spawn":
        raise AssertionError("未执行独立 spawn")
    for key in ("matrix_sha256", "query_sha256", "bank_hashes", "source_hashes",
                "selected_demonstration_task_ids"):
        if parent[key] != child[key]:
            raise AssertionError(f"spawn 与主进程证据不一致：{key}")
    result = {**parent, "status": "passed", "started_at": started,
              "terminated_at": dt.datetime.now().astimezone().isoformat(), "model": EMBEDDER,
              "model_role": "local_text_embedding_not_LLM", "spawn": child,
              "spawn_passed": True, "spawn_vectors_bitwise_equal": True,
              "versions": {n: importlib.metadata.version(n) for n in
                           ("transformers", "sentence-transformers", "torch", "freezegun")}}
    atomic_json(output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bank", type=Path, required=True)
    parser.add_argument("--appworld-task")
    args = parser.parse_args()
    return verify(args.output, args.bank, args.appworld_task)


if __name__ == "__main__":
    raise SystemExit(main())
