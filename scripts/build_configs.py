"""Overlay HY3 transport/model settings on pinned author configs; no vendor edits."""
import copy
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor" / "daedalus"


def build():
    out = ROOT / "configs"
    out.mkdir(exist_ok=True)
    for benchmark in ("tau2", "appworld"):
        for phase, source in (("baseline", "inference/baseline"),
                              ("generation", "generation/daedalus"),
                              ("memory", "inference/daedalus")):
            path = VENDOR / "configs" / benchmark / f"{source}.yaml"
            cfg = copy.deepcopy(yaml.safe_load(path.read_text()))
            cfg["experiment_name"] = f"hy3_{benchmark}_{phase}"
            cfg["category"] = "hy3-reproduction"
            cfg["agent"] = {"model": "openai/hy3", "temperature": 1.0,
                            "reasoning_effort": "high", "max_turns": 30}
            cfg.setdefault("accumulation", {}).update(
                extraction_model="openai/hy3", extraction_reasoning_effort=None)
            cfg.setdefault("generation", {}).update(
                explorer_model="openai/hy3", explorer_reasoning_effort="high",
                judge_model="openai/hy3", judge_reasoning_effort="high")
            if phase == "generation":
                cfg["generation"].update(coverage_tags_path=None,
                                          num_sessions=74 if benchmark == "tau2" else 90,
                                          num_explorers=1)
                if benchmark == "tau2":
                    cfg["tau2"]["task_split"] = "train"
            if benchmark == "tau2":
                cfg.setdefault("tau2", {}).update(
                    domain="retail", user_llm="openai/hy3",
                    user_llm_args={"temperature": 0.0, "reasoning_effort": "high"}, max_steps=200)
            cfg["cost_accounting"] = {"enabled": True,
                                      "require_complete_estimates": False}
            cfg["run"] = {"num_runs": 5 if phase != "generation" else 1,
                          "parallel": 1}
            if phase == "baseline":
                cfg["memory"] = {"enabled": False}
            elif phase == "memory":
                cfg["memory"].update(
                    enabled=True, heuristics_at_start=True,
                    pool_path=f"outputs/daedalus/hy3_{benchmark}_generation/consolidated_pool.json")
            target = out / f"{benchmark}_{phase}.yaml"
            target.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
        cfg = yaml.safe_load((out / f"{benchmark}_generation.yaml").read_text())
        cfg["experiment_name"] = f"hy3_{benchmark}_generation_smoke"
        cfg["generation"]["num_sessions"] = 1
        # Reuse a prior smoke's completed coverage survey when available, so a
        # single-session smoke does not re-pay the one-time survey cost.
        prior_cov = f"outputs/daedalus/hy3_{benchmark}_generation_smoke/coverage_tags.txt"
        if (VENDOR / prior_cov).exists():
            cfg["experiment_name"] = f"hy3_{benchmark}_generation_smoke2"
            cfg["generation"]["coverage_tags_path"] = prior_cov
        (out / f"{benchmark}_generation_smoke.yaml").write_text(
            yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
        # Smoke uses TRAIN only, preserving test tasks for final paired evaluation.
        cfg = yaml.safe_load((out / f"{benchmark}_baseline.yaml").read_text())
        cfg["experiment_name"] = f"hy3_{benchmark}_train_smoke"
        cfg["category"] = "hy3-smoke"
        cfg["run"] = {"num_runs": 1, "parallel": 1, "max_tasks": 1}
        cfg[benchmark]["task_split" if benchmark == "tau2" else "dataset"] = "train"
        (out / f"{benchmark}_smoke.yaml").write_text(
            yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    print(json.dumps({"configs_written": sorted(p.name for p in out.glob("*.yaml"))}))


if __name__ == "__main__":
    build()
