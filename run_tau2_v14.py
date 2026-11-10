"""Run tau2 PredictMem on retail+airline+telecom, per task, isolated processes."""

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, "/data/workspace/PredictMem/vendor/daedalus")
from tau2.runner import get_tasks  # noqa: E402

BASE = Path("/data/workspace/PredictMem/vendor/daedalus")
OUT = BASE / "outputs/inference/tau2/predictmem"
CONCURRENCY = int(os.environ.get("PM_CONC", "12"))
DOMAINS = ["retail"]


def jobs():
    for domain in DOMAINS:
        for task in get_tasks(domain, task_split_name="test"):
            if domain == "retail" and task.id == "70":
                continue
            exp = f"pm_tau2v14_{domain}_t{task.id}"
            if (OUT / exp / "evaluation.json").exists():
                continue
            yield domain, task.id, exp


def run(job):
    domain, task_id, exp = job
    cfg = f"/data/workspace/PredictMem/configs/pm_tau2_{domain}.yaml"
    log = open(f"/data/workspace/PredictMem/logs/{exp}.log", "a")
    cmd = [
        str(BASE / ".venv/bin/python"), "-m", "daedalus.scripts.inference",
        "--config", cfg, "--task-id", task_id, "--num-runs", "5",
        "--parallel", "1", "--experiment-name", exp,
    ]
    try:
        subprocess.run(cmd, cwd=BASE, stdout=log, stderr=log, timeout=7200,
                       env={**os.environ, "OPENAI_BASE_URL": "http://127.0.0.1:8743/v1",
                            "OPENAI_API_KEY": "dummy"})
    except Exception as exc:
        log.write(f"\nDRIVER_ERROR {exc}\n")
    finally:
        log.close()
    return exp


def main():
    todo = list(jobs())
    print(f"{len(todo)} tasks, concurrency {CONCURRENCY}", flush=True)
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        for exp in pool.map(run, todo):
            print("done", exp, flush=True)


if __name__ == "__main__":
    main()
