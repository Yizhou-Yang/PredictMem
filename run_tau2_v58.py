import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE = Path("/data/workspace/PredictMem/vendor/daedalus")
OUT = BASE / "outputs/inference/tau2/predictmem"
sys.path.insert(0, str(BASE))
from tau2.runner import get_tasks

ids = [t.id for t in get_tasks("retail", task_split_name="test") if t.id != "70"]
fast = sorted(ids, key=int)[:10]
CONC = int(os.environ.get("PM_CONC", "10"))

def prior(tid):
    for f in (OUT / f"base_tau2v22_retail_t{tid}").glob("run_0/*.json"):
        try: d = json.load(open(f))
        except Exception: return ""
        if not d.get("success"): return ""
        acts = [str(t.get("code"))[:200] for t in (d.get("turns") or []) if t.get("code")]
        return "\n".join(f"- {a}" for a in acts[:20])
    return ""

def jobs():
    for tid in fast:
        exp = f"pm_tau2v58_retail_t{tid}"
        if (OUT / exp / "evaluation.json").exists(): continue
        yield tid, exp, prior(tid)

def run(job):
    tid, exp, p = job
    env = {**os.environ, "OPENAI_BASE_URL": "http://127.0.0.1:8743/v1", "OPENAI_API_KEY": "dummy",
           "PM_WORKFLOW": ("Previous successful actions for this task:\n" + p) if p else ""}
    subprocess.run([str(BASE/".venv/bin/python"), "-m", "daedalus.scripts.inference",
                    "--config", "/data/workspace/PredictMem/configs/pm_tau2_retail_termcomb.yaml",
                    "--task-id", tid, "--num-runs", "3", "--parallel", "1", "--experiment-name", exp],
                   cwd=BASE, env=env, timeout=3600,
                   stdout=open(f"/data/workspace/PredictMem/logs/{exp}.log", "a"), stderr=subprocess.STDOUT)

if __name__ == "__main__":
    todo = list(jobs()); print(len(todo), "fast tasks", flush=True)
    with ThreadPoolExecutor(max_workers=CONC) as pool:
        list(pool.map(run, todo))
