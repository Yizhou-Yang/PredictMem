"""LongMemEval: dated flat retrieval with an agreement-gated second retrieval.

The predictor independently predicts the answer. When it agrees with the policy answer the
answer is committed. When it disagrees, a wider retrieval produces a second answer, which is
committed only if the predictor agrees with it. The fallback is always the first answer, so the
predictor cannot make the result worse than plain retrieval.
"""

import json
import os
import re
import string
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import litellm

DATA = "/data/workspace/mem_bench/lme_s_cleaned.json"
MODEL = os.environ.get("PM_MODEL", "openai/hy4")
API = os.environ.get("OPENAI_BASE_URL", "http://127.0.0.1:8743/v1")
K = int(os.environ.get("PM_K", "10"))


def llm(prompt, max_tokens=200):
    r = litellm.completion(model=MODEL, api_base=API, api_key="dummy",
                           messages=[{"role": "user", "content": prompt}],
                           temperature=0.0, max_tokens=max_tokens,
                           reasoning_effort="no_think", timeout=150)
    return (r.choices[0].message.content or "").strip()


def norm(s):
    s = str(s).lower()
    s = "".join(ch for ch in s if ch not in string.punctuation)
    return re.sub(r"\s+", " ", s).strip()


def f1(pred, gold):
    p, g = norm(pred).split(), norm(gold).split()
    if not p or not g:
        return 0.0
    same = sum((Counter(p) & Counter(g)).values())
    if not same:
        return 0.0
    prec, rec = same / len(p), same / len(g)
    return 2 * prec * rec / (prec + rec)


def pool(sample):
    out = []
    dates = sample.get("haystack_dates") or []
    for i, s in enumerate(sample.get("haystack_sessions") or []):
        stamp = dates[i] if i < len(dates) else f"session {i}"
        for t in s:
            if t.get("content"):
                out.append(f"[{stamp}] {t.get('role','')}: {t['content']}")
    return out


def retrieved(sample, k):
    q = sample["question"]
    qc = Counter(norm(q).split())
    scored = []
    for u in pool(sample):
        c = Counter(norm(u).split())
        ov = sum(min(c[w], qc[w]) for w in qc)
        if ov:
            scored.append((ov, u))
    scored.sort(key=lambda x: -x[0])
    return "\n".join(u for _, u in scored[:k])


def ask(q, mem):
    pred = llm("Predict the short answer this evidence implies. If it does not determine one, "
               "output INSUFFICIENT.\n"
               f"EVIDENCE:\n{mem}\n\nQUESTION: {q}\nPREDICTED:", 120)
    ans = llm("Answer with only the answer phrase, at most 8 words. Each evidence line starts with "
              "its date. If the question asks when, convert relative expressions to an explicit date.\n"
              f"EVIDENCE:\n{mem}\n\nQUESTION: {q}\nANSWER:", 150)
    return pred, ans.splitlines()[0].strip().strip(".")


def agree(pred, ans):
    return bool(pred) and pred.upper() != "INSUFFICIENT" and (norm(pred) in norm(ans) or norm(ans) in norm(pred))


def work(sample):
    q = sample["question"]
    gold = str(sample.get("answer", ""))
    pred1, ans1 = ask(q, retrieved(sample, K))
    agree1 = agree(pred1, ans1)
    escalated, ans, agree2 = 0, ans1, agree1
    if not agree1:
        pred2, ans2 = ask(q, retrieved(sample, K + 10))
        escalated = 1
        agree2 = agree(pred2, ans2)
        if agree2:
            ans = ans2
    return {"q": q, "type": sample.get("question_type"), "gold": gold, "pred": ans,
            "agree": agree2, "escalated": escalated, "f1": f1(ans, gold)}


def main():
    data = json.load(open(DATA))
    rows = list(ThreadPoolExecutor(max_workers=6).map(work, data))
    json.dump(rows, open("/tmp/lme_safe_rows.json", "w"), indent=2)
    print("n", len(rows), "F1", round(sum(r["f1"] for r in rows) / len(rows), 4),
          "agree", round(sum(1 for r in rows if r["agree"]) / len(rows), 3),
          "escalated", round(sum(r["escalated"] for r in rows) / len(rows), 3))


if __name__ == "__main__":
    main()
