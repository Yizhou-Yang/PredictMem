"""ALFWorld runner: text environment, no Docker needed.

Each game is a household task; the environment returns an observation plus the list of
admissible commands, and scores the episode itself (`won`). That makes it the only
action-type benchmark here whose reward is environmental and costs no container.

Arms
  A   no memory
  cm  CuratorMem lessons: after each game the runner asks the critic for one reusable
      lesson and stores it; later games in the same task family may read it.

Output: one JSONL row per game with task type, won, steps, and the injected block length,
so the same analysis code as LoCoMo/tau2 can read it.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request

import yaml

ALFWORLD_REPO = os.environ.get("ALFWORLD_REPO", "/data/workspace/alfworld-repo")
CFG = os.environ.get("ALFWORLD_CFG", os.path.join(ALFWORLD_REPO, "configs/base_config.yaml"))
DATA = os.environ.get("ALFWORLD_DATA", "/data/workspace/alfworld-data")
API = os.environ.get("ALF_API", "http://api.taiji.woa.com/openapi/v2")
KEY = os.environ.get("ALF_KEY", "")
MODEL = os.environ.get("ALF_MODEL", "hy4")
MAX_STEPS = int(os.environ.get("ALF_MAX_STEPS", "30"))


def chat(system: str, user: str, max_tokens: int = 120, timeout: int = 90) -> str:
    body = json.dumps({
        "model": MODEL,
        "messages": ([{"role": "system", "content": system}] if system else [])
                    + [{"role": "user", "content": user}],
        "max_tokens": max_tokens,
        "temperature": 0.0,
    }).encode()
    req = urllib.request.Request(
        API.rstrip("/") + "/chat/completions", data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {KEY}"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                d = json.loads(r.read().decode())
            m = d["choices"][0]["message"]
            return (m.get("content") or m.get("reasoning_content") or "").strip()
        except Exception:
            time.sleep(2 * (attempt + 1))
    return ""


def _cmds(info):
    """Admissible commands come back in the info dict, one list per batch item."""
    try:
        c = (info[0] if isinstance(info, (list, tuple)) else info).get("admissible_commands")
        return list(c) if c else []
    except Exception:
        return []


def pick_command(obs: str, cmds: list[str], lessons: list[str]) -> str:
    learned = ("\nLessons from earlier games:\n" + "\n".join("- " + x for x in lessons)) if lessons else ""
    user = (f"{obs}\n{learned}\n\nAdmissible commands:\n"
            + "\n".join("- " + c for c in cmds[:60])
            + "\n\nReply with exactly one admissible command, nothing else.")
    out = chat("You control a household robot. Reply with one command and no explanation.",
               user, max_tokens=40)
    out = (out or "").strip().splitlines()[0].strip() if out else ""
    for c in cmds:
        if out.lower() == c.lower():
            return c
    for c in cmds:                      # fuzzy: command contained in the reply
        if c.lower() in out.lower():
            return c
    return cmds[0] if cmds else "look"


def lesson_from(task_type: str, won: bool, steps: list[str]) -> str:
    return ("%s: %s after %d steps; last action '%s'"
            % (task_type.split("-")[0], "worked" if won else "failed",
               len(steps), steps[-1] if steps else ""))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="A", choices=["A", "cm"])
    ap.add_argument("--games", type=int, default=20)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    os.environ["ALFWORLD_DATA"] = DATA
    cfg = yaml.safe_load(open(CFG))
    from alfworld.agents.environment import get_environment
    env = get_environment("AlfredTWEnv")(cfg, train_eval="eval_out_of_distribution")
    env = env.init_env(batch_size=1)

    out_path = args.out or f"experiments_results/alfworld_{args.arm}.jsonl"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    lessons: list[str] = []

    for i in range(args.games):
        obs, info = env.reset()
        obs = obs[0] if isinstance(obs, (list, tuple)) else obs
        task_type = ""
        try:
            task_type = str(info[0].get("extra.expert_path", "")) if isinstance(info, (list, tuple)) else ""
        except Exception:
            pass
        cmds = _cmds(info)
        done, won, steps, block_len = False, False, [], 0
        while not done and len(steps) < MAX_STEPS:
            cl = cmds[0] if isinstance(cmds, (list, tuple)) and cmds and isinstance(cmds[0], list) else cmds
            cl = cl or []
            act = pick_command(obs, cl, lessons if args.arm == "cm" else [])
            block_len = len(lessons) if args.arm == "cm" else 0
            steps.append(act)
            obs, _scores, dones, info = env.step([act])
            obs = obs[0] if isinstance(obs, (list, tuple)) else obs
            done = bool(dones[0]) if isinstance(dones, (list, tuple)) else bool(dones)
            if done:
                won = bool(info[0].get("won", False)) if isinstance(info, (list, tuple)) else False
            cmds = _cmds(info)
        if args.arm == "cm":
            lessons.append(lesson_from(task_type, won, steps))
            lessons = lessons[-8:]
        row = {"system": args.arm, "game": i, "task_type": task_type or "",
               "won": won, "steps": len(steps), "lessons": block_len}
        with open(out_path, "a") as f:
            f.write(json.dumps(row) + "\n")
        print(f"  [{args.arm}] {i+1}/{args.games} won={won} steps={len(steps)}", flush=True)


if __name__ == "__main__":
    main()
