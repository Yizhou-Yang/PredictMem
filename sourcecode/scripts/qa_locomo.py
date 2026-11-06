"""LoCoMo with an answer-predictor and a commit rule.

The predictor independently predicts the answer implied by the evidence. The policy answers
from the same evidence. The controller commits when the two answers agree; otherwise it
escalates to the full conversation once, re-predicts, and commits the policy answer.

This keeps the predictor an effect predictor (it predicts the answer a correct agent would
produce), and it never abstains.
"""

import json
import os
import re
import string
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import litellm

DATA = "/data/workspace/mem_bench/locomo10.json"
MODEL = os.environ.get("PM_MODEL", "openai/hy4")
API = os.environ.get("OPENAI_BASE_URL", "http://127.0.0.1:8743/v1")
K = int(os.environ.get("PM_K", "20"))
START = int(os.environ.get("PM_START", "764"))
N = int(os.environ.get("PM_N", "778"))


def llm(prompt, max_tokens=200):
    r = litellm.completion(model=MODEL, api_base=API, api_key="dummy",
                           messages=[{"role": "user", "content": prompt}],
                           temperature=0.0, max_tokens=max_tokens,
                           reasoning_effort="no_think", timeout=180)
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


def utts(conv):
    out = []
    dates = conv.get("session_dates") or {}
    for key, sess in conv.get("conversation", {}).items():
        stamp = dates.get(key) or key
        for t in sess:
            if isinstance(t, str):
                txt, spk = t, ""
            else:
                txt, spk = t.get("text") or t.get("content") or "", t.get("speaker", "")
            if txt:
                out.append(f"[{stamp}] {spk}: {txt}")
    return out


def bm25(us, q, k):
    qc = Counter(norm(q).split())
    scored = []
    for u in us:
        c = Counter(norm(u).split())
        ov = sum(min(c[w], qc[w]) for w in qc)
        if ov:
            scored.append((ov, u))
    scored.sort(key=lambda x: -x[0])
    return [u for _, u in scored[:k]]


def predict_answer(q, evidence):
    return llm("Predict the short answer that this evidence implies for the question. "
               "If the evidence does not determine an answer, output exactly INSUFFICIENT.\n"
               f"EVIDENCE:\n{evidence}\n\nQUESTION: {q}\nPREDICTED ANSWER:", 120)


def policy_answer(q, evidence):
    return llm("Answer the question using only the evidence. Each line starts with its session date. "
               "If asked when, convert relative expressions to an explicit date. Short phrase.\n"
               f"EVIDENCE:\n{evidence}\n\nQUESTION: {q}\nANSWER:", 150)


def work(item):
    q, gold, conv = item
    us = utts(conv)
    evidence = "\n".join(bm25(us, q, K))[:14000]
    pred = predict_answer(q, evidence)
    ans = policy_answer(q, evidence)
    agree = bool(pred) and pred.upper() != "INSUFFICIENT" and (
        norm(pred) == norm(ans) or (norm(pred) and norm(pred) in norm(ans)) or (norm(ans) and norm(ans) in norm(pred)))
    escalated = 0
    if not agree:
        full = "\n".join(us)[:30000]
        pred2 = predict_answer(q, full)
        ans2 = policy_answer(q, full)
        escalated = 1
        if pred2.upper() != "INSUFFICIENT" and (norm(pred2) in norm(ans2) or norm(ans2) in norm(pred2)):
            ans = ans2
    return {"q": q, "gold": gold, "pred": ans, "predicted": pred,
            "agree": agree, "escalated": escalated, "f1": f1(ans, gold)}


def main():
    raw = json.load(open(DATA))
    items = []
    for conv in raw:
        for qa in conv.get("qa", []):
            q, a = qa.get("question"), qa.get("answer")
            if not q or not a:
                continue
            items.append((q, str(a), conv))
    items = items[START:START + N] if N else items[START:]
    rows = list(ThreadPoolExecutor(max_workers=6).map(work, items))
    json.dump(rows, open("/tmp/locomo_predcommit_rows.json", "w"), indent=2)
    print("n", len(rows), "F1", round(sum(r["f1"] for r in rows) / len(rows), 4),
          "agree", round(sum(1 for r in rows if r["agree"]) / len(rows), 3),
          "escalated", round(sum(r["escalated"] for r in rows) / len(rows), 3))


if __name__ == "__main__":
    main()
