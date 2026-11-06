#!/usr/bin/env python3
"""One entry point for every benchmark and model profile.

Usage:
  python run_unified.py tau2  --profile hy4      --arm pm
  python run_unified.py tau2  --profile deepseek --arm baseline
  python run_unified.py lme   --profile hy4
  python run_unified.py locomo --profile deepseek

Model switching is env-only: the config loader honours PM_FORCE_MODEL / PM_FORCE_REASONING,
so no YAML file needs editing and no benchmark-specific model handling is repeated here.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

def _find_root(start: Path) -> Path:
    for parent in [start.parent, *start.parents]:
        if (parent / "vendor/daedalus").exists() or (parent / "experiments_results").exists():
            return parent
    return start.parent


ROOT = _find_root(Path(__file__).resolve())
PYTHON = str(ROOT / "vendor/daedalus/.venv/bin/python")
DATASETS = Path("/data/workspace/mem_bench")


@dataclass(frozen=True)
class Profile:
    base_url: str
    model: str
    reasoning: str


PROFILES = {
    "hy4": Profile("http://127.0.0.1:8743/v1", "openai/hy4", "no_think"),
    "deepseek": Profile("http://127.0.0.1:8745/v1", "openai/deepseek-flash", "low"),
}

TAU2_DRIVERS = {
    ("hy4", "baseline"): "run_tau2_v22.py",
    ("hy4", "pm"): "run_tau2_v86.py",
    ("deepseek", "baseline"): "run_tau2_v88ds.py",
    ("deepseek", "pm"): "run_tau2_v89ds.py",
}

QA_SCRIPTS = {
    ("lme", "hy4"): "qa_lme.py",
    ("locomo", "hy4"): "qa_locomo.py",
    ("lme", "deepseek"): "qa_lme.py",
    ("locomo", "deepseek"): "qa_locomo.py",
}


def env_for(profile: Profile, extra: dict[str, str]) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "OPENAI_BASE_URL": profile.base_url,
            "PM_MODEL": profile.model,
            "PM_FORCE_MODEL": profile.model,
            "PM_FORCE_REASONING": profile.reasoning,
            "OPENAI_API_KEY": "dummy",
            "TAU2_NL_JUDGE_MODEL": profile.model,
        }
    )
    env.update(extra)
    return env


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bench", choices=["tau2", "lme", "locomo", "alf"])
    parser.add_argument("--profile", choices=sorted(PROFILES), default="hy4")
    parser.add_argument("--arm", choices=["baseline", "pm"], default="pm")
    parser.add_argument("--conc", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    profile = PROFILES[args.profile]
    extra = {"PM_CONC": args.conc} if args.conc else {}

    if args.bench == "tau2":
        driver = TAU2_DRIVERS.get((args.profile, args.arm))
        if not driver:
            sys.exit(f"no tau2 driver for {args.profile}/{args.arm}")
        cmd = [PYTHON, str(ROOT / driver)]
    elif args.bench == "alf":
        cmd = [str(ROOT / "alfworld_pm/run_alf_proc.sh")] if args.arm == "pm" else [str(ROOT / "alfworld_pm/run_alf_nopred.sh")]
    else:
        script = QA_SCRIPTS.get((args.bench, args.profile))
        if not script:
            sys.exit(f"no script for {args.bench}/{args.profile}")
        script_path = ROOT / "scripts" / script
        if not script_path.exists():
            script_path = ROOT / "sourcecode/scripts" / script
        cmd = [PYTHON, str(script_path)]

    env = env_for(profile, extra)
    print("profile:", args.profile, profile.model, "| cmd:", " ".join(cmd))
    if args.dry_run:
        return
    sys.exit(subprocess.call(cmd, cwd=ROOT, env=env))


if __name__ == "__main__":
    main()
