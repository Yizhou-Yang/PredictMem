"""Validate pinned dependencies, disjoint official splits, and config role boundaries."""
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess

from daedalus.core.config import load_config

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor" / "daedalus"


def main():
    lock = json.loads((ROOT / "sources.lock.json").read_text())
    revisions = {}
    for name, expected in {".": lock["daedalus"]["commit"],
                           **lock["daedalus"]["submodules"]}.items():
        actual = subprocess.check_output(["git", "rev-parse", "HEAD"],
                                         cwd=VENDOR / name, text=True).strip()
        assert actual == expected, f"Unpinned source: {name}"
        revisions[name] = actual
    from tau2.runner import get_tasks
    tau_train = [t.id for t in get_tasks("retail", task_split_name="train")]
    tau_test = [t.id for t in get_tasks("retail", task_split_name="test")]
    assert len(tau_train) == 74 and len(tau_test) == 40
    assert not set(tau_train) & set(tau_test)
    from appworld.task import load_task_ids
    import appworld.download
    app_train = load_task_ids("train")
    app_test = load_task_ids("test_normal")
    assert len(app_train) == 90 and len(app_test) == 168
    assert not set(app_train) & set(app_test)
    for path in (ROOT / "configs").glob("*.yaml"):
        cfg = load_config(path)
        assert cfg.agent.model == "openai/hy3"
        assert cfg.accumulation.extraction_model == "openai/hy3"
        assert cfg.generation.explorer_model == cfg.generation.judge_model == "openai/hy3"
        assert cfg.cost_accounting.enabled and not cfg.cost_accounting.require_complete_estimates
        if cfg.benchmark == "tau2":
            assert cfg.tau2.user_llm == "openai/hy3"
        if "smoke" in path.stem or "generation" in path.stem:
            split = cfg.tau2.task_split if cfg.benchmark == "tau2" else cfg.appworld.dataset
            assert split == "train"
            if cfg.benchmark == "appworld" and "generation" in path.stem:
                assert cfg.generation.sandbox_dataset == "train"
        if "baseline" in path.stem or "memory" in path.stem:
            split = cfg.tau2.task_split if cfg.benchmark == "tau2" else cfg.appworld.dataset
            assert split == ("test" if cfg.benchmark == "tau2" else "test_normal")
        if "memory" in path.stem:
            assert cfg.memory.enabled and cfg.memory.heuristics_at_start
    result = {"status": "passed", "python": platform.python_version(),
              "revisions": revisions, "appworld_data_version": appworld.download.DATA_VERSION,
              "packages": {n: importlib.metadata.version(n) for n in
                           ("daedalus", "appworld", "tau2", "litellm", "openai", "pytest")},
              "splits": {"tau2_retail": {"train_count": len(tau_train),
                         "test_count": len(tau_test), "disjoint": True},
                         "appworld": {"train_count": len(app_train),
                         "test_normal_count": len(app_test), "disjoint": True}},
              "config_checks": "all generated configs accepted by upstream schema", 
              "audit_scope": "IDs/counts, config schema and split settings only; not proof of full pipeline information isolation"}
    (ROOT / "results" / "environment.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
