import json, os, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE = Path("/data/workspace/PredictMem/vendor/daedalus")
OUT = BASE / "outputs/inference/tau2/predictmem"
RULES = json.load(open("/data/workspace/PredictMem/rule_bank.json"))
sys.path.insert(0, str(BASE))
from tau2.runner import get_tasks

ids = [t.id for t in get_tasks("retail", task_split_name="test") if t.id != "70"]
fast = sorted(ids, key=int)[:10]
CONC = int(os.environ.get("PM_CONC", "10"))

def hint(instr):
    toks = set(re.findall(r"[a-z]+", instr.lower()))
    scored = []
    for r in RULES:
        s = len(toks & set(re.findall(r"[a-z]+", r["instruction"].lower())))
        if s >= 2:
            scored.append((s, r["rule"]))
    scored.sort(reverse=True)
    return "\n".join(f"- {x[1]}" for x in scored[:3])

def jobs():
    for tid in fast:
        exp = f"pm_tau2v57_retail_t{tid}"
        if (OUT / exp / "evaluation.json").exists(): continue
        instr = ""
        for f in (OUT / f"base_tau2v22_retail_t{tid}").glob("run_0/*.json"):
            try: instr = json.load(open(f)).get("task_instruction", "")
            except Exception: pass
            break
        yield tid, exp, hint(instr)

def run(job):
    tid, exp, h = job
    env = {**os.environ, "OPENAI_BASE_URL": "http://127.0.0.1:8743/v1", "OPENAI_API_KEY": "dummy", "PM_WORKFLOW": h}
    subprocess.run([str(BASE/".venv/bin/python"), "-m", "daedalus.scripts.inference",
                    "--config", "/data/workspace/PredictMem/configs/pm_tau2_retail_termcomb.yaml",
                    "--task-id", tid, "--num-runs", "3", "--parallel", "1", "--experiment-name", exp],
                   cwd=BASE, env=env, timeout=3600,
                   stdout=open(f"/data/workspace/PredictMem/logs/{exp}.log", "a"), stderr=subprocess.STDOUT)

if __name__ == "__main__":
    todo = list(jobs()); print(len(todo), "fast tasks", flush=True)
    with ThreadPoolExecutor(max_workers=CONC) as pool:
        list(pool.map(run, todo))
