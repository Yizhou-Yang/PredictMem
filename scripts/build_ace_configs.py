"""Overlay HY3 transport/model settings on the pinned ACE reference configs.

ACE (Agentic Context Engineering, Zhang et al. 2026) is reimplemented upstream in
``references/ace/`` on daedalus's harness. These configs keep that code untouched and
only swap the three roles' models to HY3, matching how the DAEDALUS configs are
overlaid. The accumulation phase keeps the paper's sequential wave (``parallel: 1``),
which is the only faithful offline loop; ``>1`` switches to the ComBEE reducer, a
different algorithm not used in the paper.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor" / "daedalus"
ACE_SRC = VENDOR / "references" / "ace" / "configs"

# Inference parallelism. HY3 accepts high throughput, so this is raised above the
# official 20 (see reproduction_protocol.json). Accumulation stays sequential (see
# below) regardless of this value.
PARALLEL = int(os.environ.get("PREDICTMEM_PARALLEL", "24"))
# Separate throughput setting only. The confirmed truncation defect was a global
# 1500-second task-pool deadline, not evidence that parallel 24 overloaded the CPU.
PARALLEL_APPWORLD = int(os.environ.get("PREDICTMEM_PARALLEL_APPWORLD", "12"))


def build() -> None:
    out = ROOT / "configs"
    out.mkdir(exist_ok=True)
    written: list[str] = []
    for benchmark in ("tau2", "appworld"):
        name = f"hy3_{benchmark}"
        for phase in ("accumulation", "inference"):
            cfg = copy.deepcopy(yaml.safe_load((ACE_SRC / f"{benchmark}_{phase}.yaml").read_text()))
            cfg["experiment_name"] = name
            cfg["category"] = "hy3-reproduction"
            cfg["agent"] = {"model": "openai/hy3", "temperature": 1.0,
                            "reasoning_effort": "high", "max_turns": 30}
            ace = dict(cfg.get("ace") or {})
            ace.update(reflector_model="openai/hy3", reflector_reasoning_effort="high",
                       curator_model="openai/hy3", curator_reasoning_effort="high",
                       # pin to this HY3 run's own playbook artifact
                       playbook_path=f"outputs/baselines/ace/memory/{name}/playbook.txt")
            cfg["ace"] = ace
            if phase == "accumulation":
                cfg.setdefault("accumulation", {}).update(extraction_model="openai/hy3")
                # paper's sequential offline loop; wave size 1 (see module docstring)
                cfg.setdefault("run", {})["parallel"] = 1
            else:
                cfg["run"] = {"num_runs": 5,
                              "parallel": PARALLEL_APPWORLD if benchmark == "appworld" else PARALLEL}
            if benchmark == "tau2":
                cfg.setdefault("tau2", {}).update(
                    user_llm="openai/hy3",
                    user_llm_args={"temperature": 0.0, "reasoning_effort": "high"})
            cfg["cost_accounting"] = {"enabled": True, "require_complete_estimates": False}
            target = out / f"ace_{benchmark}_{phase}.yaml"
            target.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
            written.append(target.name)
    print(json.dumps({"ace_configs_written": sorted(written)}))


if __name__ == "__main__":
    build()
