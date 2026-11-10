import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE = Path("/data/workspace/PredictMem/vendor/daedalus")
OUT = BASE / "outputs/inference/tau2/predictmem"
sys.path.insert(0, str(BASE))
from tau2.runner import get_tasks

DOMAINS = ["retail"]
CONC = int(os.environ.get("PM_CONC", "20"))

def prior(domain, tid):
    for f in sorted((OUT / f"base_tau2v22_{domain}_t{tid}").glob("run_*/*.json")):
        try: d = json.load(open(f))
        except Exception: continue
        if not d.get("success"): continue
        acts = [str(t.get("code"))[:200] for t in (d.get("turns") or []) if t.get("code")]
        if acts: return "\n".join(f"- {a}" for a in acts[:20])
    return ""

def jobs():
    for domain in DOMAINS:
        for task in get_tasks(domain, task_split_name="test"):
            if task.id == "70": continue
            exp = f"pm_tau2v70_{domain}_t{task.id}"
            if (OUT / exp / "evaluation.json").exists(): continue
            yield domain, task.id, exp, prior(domain, task.id)

def run(job):
    domain, tid, exp, p = job
    cfg = f"/data/workspace/PredictMem/configs/pm_tau2_{domain}_rerank.yaml"
    if not Path(cfg).exists():
        cfg = "/data/workspace/PredictMem/configs/pm_tau2_retail_termcomb.yaml"
    env = {**os.environ, "OPENAI_BASE_URL": "http://127.0.0.1:8743/v1", "OPENAI_API_KEY": "dummy",
           "PM_WORKFLOW": ("Previous successful actions for this task:\n" + p) if p else ""}
    subprocess.run([str(BASE/".venv/bin/python"), "-m", "daedalus.scripts.inference",
                    "--config", cfg, "--task-id", tid, "--num-runs", "5", "--parallel", "1",
                    "--experiment-name", exp], cwd=BASE, env=env, timeout=7200,
                   stdout=open(f"/data/workspace/PredictMem/logs/{exp}.log", "a"), stderr=subprocess.STDOUT)

if __name__ == "__main__":
    todo = list(jobs()); print(len(todo), "tasks", flush=True)
    with ThreadPoolExecutor(max_workers=CONC) as pool:
        list(pool.map(run, todo))
