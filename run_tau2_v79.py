import json, os, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE = Path("/data/workspace/PredictMem/vendor/daedalus")
OUT = BASE / "outputs/inference/tau2/predictmem"
sys.path.insert(0, str(BASE))
from tau2.runner import get_tasks
import litellm

MODEL = os.environ.get("PM_MODEL", "openai/hy4-preview")
API = os.environ.get("OPENAI_BASE_URL", "http://127.0.0.1:8743/v1")
CONC = int(os.environ.get("PM_CONC", "16"))
DOMAINS = ["retail"]

def traces(domain):
    out = []
    for f in sorted(Path(f"{OUT}").glob(f"base_tau2v22_{domain}_t*/run_*/*.json")):
        try: d = json.load(open(f))
        except Exception: continue
        if not d.get("success"): continue
        acts = [str(t.get("code"))[:160] for t in (d.get("turns") or []) if t.get("code")]
        if acts:
            out.append((d.get("task_instruction", ""), "\n".join(f"- {a}" for a in acts[:20]), str(f).split("_t")[-1].split("/")[0]))
    return out

def judge_applicable(task, seq):
    p = ("Can this action sequence accomplish the task? Answer JSON {\"ok\": true/false} only.\n"
         f"TASK: {task[:800]}\nACTIONS:\n{seq[:2500]}")
    try:
        r = litellm.completion(model=MODEL, api_base=API, api_key="dummy",
                               messages=[{"role": "user", "content": p}],
                               temperature=0.0, max_tokens=60, reasoning_effort="no_think", timeout=60)
        m = re.search(r"\{.*\}", r.choices[0].message.content or "", re.S)
        return bool(json.loads(m.group(0)).get("ok")) if m else False
    except Exception:
        return False

def hint(domain, tid, instr, bank):
    same = [s for t, s, i in bank if i == tid]
    if same:
        return same[0]
    toks = set(re.findall(r"[a-z]+", instr.lower()))
    cand = sorted(((len(toks & set(re.findall(r"[a-z]+", t.lower()))), s) for t, s, i in bank if i != tid), reverse=True)
    if cand and cand[0][0] >= 3 and judge_applicable(instr, cand[0][1]):
        return cand[0][1]
    return ""

def jobs():
    bank = traces("retail")
    tasks = [t for t in get_tasks("retail", task_split_name="test") if t.id != "70"][:10]
    for task in tasks:
        if task.id == "70": continue
        exp = f"pm_tau2v79_retail_t{task.id}"
        if (OUT / exp / "evaluation.json").exists(): continue
        instr = ""
        for f in (OUT / f"base_tau2v22_retail_t{task.id}").glob("run_0/*.json"):
            try: instr = json.load(open(f)).get("task_instruction", "")
            except Exception: pass
            break
        yield task.id, exp, hint("retail", task.id, instr, bank)

def run(job):
    tid, exp, h = job
    env = {**os.environ, "OPENAI_BASE_URL": os.environ.get("PM_BASE_URL", "http://127.0.0.1:8743/v1"), "OPENAI_API_KEY": "dummy",
           "PM_WORKFLOW": ("Previous successful actions for this task:\n" + h) if h else ""}
    subprocess.run([str(BASE/".venv/bin/python"), "-m", "daedalus.scripts.inference",
                    "--config", "/data/workspace/PredictMem/configs/pm_tau2_retail_predgate.yaml",
                    "--task-id", tid, "--num-runs", "3", "--parallel", "1", "--experiment-name", exp],
                   cwd=BASE, env=env, timeout=7200,
                   stdout=open(f"/data/workspace/PredictMem/logs/{exp}.log", "a"), stderr=subprocess.STDOUT)

if __name__ == "__main__":
    todo = list(jobs()); print(len(todo), "tasks", flush=True)
    with ThreadPoolExecutor(max_workers=CONC) as pool:
        list(pool.map(run, todo))
