"""Overlay HY3 transport/model settings on the pinned ExpeL reference configs.

ExpeL (Zhao et al. 2024, "ExpeL: LLM Agents Are Experiential Learners") is reimplemented
upstream in ``references/expel/`` on daedalus's harness. These configs keep that code
untouched and only swap the solver and every auxiliary role (insight extraction, reflection)
to HY3, matching how the DAEDALUS and ACE configs are overlaid.

ExpeL replaces SelfSuite (no public code) as a reusable-benchmark, code-available
experiential-learning baseline. It shares the exact same AppWorld / tau2 harness, solver,
traces and scoring as DAEDALUS and ACE. Comparability still requires complete
runs, matched protocol, frozen banks and verified terminal outcomes.

Accumulation gathers experiences (ReAct+Reflexion, parallel over tasks) then extracts a
single revisable insight list; inference injects that list plus the top-k similar successful
trajectories into the solver prompt. Unlike ACE, ``run.parallel`` here is a pure throughput
knob (tasks are independent), so it is set from ``PREDICTMEM_PARALLEL`` rather than pinned
to 1.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor" / "daedalus"
EXPEL_SRC = VENDOR / "references" / "expel" / "configs"

# Throughput parallelism for accumulation and inference (both are embarrassingly
# parallel over tasks; unlike ACE, >1 does not change the algorithm). HY3 accepts
# high throughput, so this is raised above the official 20 (see protocol).
PARALLEL = int(os.environ.get("PREDICTMEM_PARALLEL", "24"))
# Separate throughput setting only; not a repair for the global task-pool deadline.
# Force-reaped workers alone do not establish CPU/HY3 overload.
PARALLEL_APPWORLD = int(os.environ.get("PREDICTMEM_PARALLEL_APPWORLD", "12"))


def build() -> None:
    out = ROOT / "configs"
    out.mkdir(exist_ok=True)
    written: list[str] = []
    for benchmark in ("tau2", "appworld"):
        name = f"hy3_{benchmark}"
        for phase in ("accumulation", "inference"):
            cfg = copy.deepcopy(
                yaml.safe_load((EXPEL_SRC / f"{benchmark}_{phase}.yaml").read_text())
            )
            cfg["experiment_name"] = name
            cfg["category"] = "hy3-reproduction"
            cfg["agent"] = {"model": "openai/hy3", "temperature": 1.0,
                            "reasoning_effort": "high", "max_turns": 30}
            expel = dict(cfg.get("expel") or {})
            expel.update(
                extraction_model="openai/hy3",
                extraction_reasoning_effort="high",
                reflection_model="openai/hy3",
                reflection_reasoning_effort="high",
            )
            par = PARALLEL_APPWORLD if benchmark == "appworld" else PARALLEL
            if phase == "accumulation":
                # Keep the shared DAEDALUS extraction field honest too, though ExpeL
                # reads expel.extraction_model for its insight extractor.
                cfg.setdefault("accumulation", {}).update(extraction_model="openai/hy3")
                cfg.setdefault("run", {})["parallel"] = par
            else:
                cfg.setdefault("run", {})["parallel"] = par
                # pin to this HY3 run's own insight pool
                expel["insights_path"] = f"outputs/baselines/expel/memory/{name}/pool.json"
            cfg["expel"] = expel
            if benchmark == "tau2":
                cfg.setdefault("tau2", {}).update(
                    user_llm="openai/hy3",
                    user_llm_args={"temperature": 0.0, "reasoning_effort": "high"})
            cfg["cost_accounting"] = {"enabled": True, "require_complete_estimates": False}
            target = out / f"expel_{benchmark}_{phase}.yaml"
            target.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
            written.append(target.name)
    print(json.dumps({"expel_configs_written": sorted(written)}))


if __name__ == "__main__":
    build()
