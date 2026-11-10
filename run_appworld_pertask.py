"""AppWorld PredictMem, one task per process (5 runs each), resumable."""

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

os.environ["APPWORLD_ROOT"] = "/data/workspace/PredictMem/vendor/daedalus"
sys.path.insert(0, "/data/workspace/PredictMem/vendor/daedalus")
from appworld.task import load_task_ids  # noqa: E402

BASE = Path("/data/workspace/PredictMem/vendor/daedalus")
OUT = BASE / "outputs/inference/appworld/predictmem"
CONCURRENCY = int(os.environ.get("PM_CONC", "16"))


def jobs():
    for task_id in load_task_ids("test_normal"):
        exp = f"pm_appworld_v4_t{task_id}"
        if (OUT / exp / "evaluation.json").exists():
            continue
        yield task_id, exp


def run(job):
    task_id, exp = job
    log = open(f"/data/workspace/PredictMem/logs/{exp}.log", "a")
    cmd = [
        str(BASE / ".venv/bin/python"), "-m", "daedalus.scripts.inference",
        "--config", "/data/workspace/PredictMem/configs/pm_appworld_controller.yaml",
        "--task-id", task_id, "--num-runs", "5", "--parallel", "1",
        "--experiment-name", exp,
    ]
    try:
        subprocess.run(cmd, cwd=BASE, stdout=log, stderr=log, timeout=10800,
                       env={**os.environ, "APPWORLD_ROOT": str(BASE),
                            "OPENAI_BASE_URL": "http://127.0.0.1:8743/v1",
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
