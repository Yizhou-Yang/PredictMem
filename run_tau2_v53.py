import json, os, subprocess, re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE = Path("/data/workspace/PredictMem/vendor/daedalus")
OUT = BASE / "outputs/inference/tau2/predictmem"
BANK = json.load(open("/data/workspace/PredictMem/wf_bank.json"))
import sys
sys.path.insert(0, str(BASE))
from tau2.runner import get_tasks

ids = [t.id for t in get_tasks("retail", task_split_name="test") if t.id != "70"]
holdout = sorted(ids, key=int)[20:]
CONC = int(os.environ.get("PM_CONC", "16"))

def best_wf(instr):
    toks = set(re.findall(r"[a-z]+", instr.lower()))
    best, score = "", -1
    for b in BANK:
        s = len(toks & set(re.findall(r"[a-z]+", b["instruction"].lower())))
        if s > score: best, score = b["workflow"], s
    return best

def jobs():
    for tid in holdout:
        exp = f"pm_tau2v53_retail_t{tid}"
        if (OUT / exp / "evaluation.json").exists(): continue
        instr = ""
        for f in (OUT / f"base_tau2v22_retail_t{tid}").glob("run_0/*.json"):
            try: instr = json.load(open(f)).get("task_instruction", "")
            except Exception: pass
            break
        yield tid, exp, best_wf(instr)

def run(job):
    tid, exp, wf = job
    env = {**os.environ, "OPENAI_BASE_URL": "http://127.0.0.1:8743/v1", "OPENAI_API_KEY": "dummy", "PM_WORKFLOW": wf}
    subprocess.run([str(BASE/".venv/bin/python"), "-m", "daedalus.scripts.inference",
                    "--config", "/data/workspace/PredictMem/configs/pm_tau2_retail_hy4.yaml",
                    "--task-id", tid, "--num-runs", "5", "--parallel", "1", "--experiment-name", exp],
                   cwd=BASE, env=env, timeout=7200,
                   stdout=open(f"/data/workspace/PredictMem/logs/{exp}.log", "a"), stderr=subprocess.STDOUT)

def main():
    todo = list(jobs()); print(len(todo), "holdout tasks", flush=True)
    with ThreadPoolExecutor(max_workers=CONC) as pool:
        list(pool.map(run, todo))

if __name__ == "__main__":
    main()
