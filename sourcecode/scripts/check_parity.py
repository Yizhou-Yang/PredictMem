"""Parity gate: the SDK must reproduce the stored benchmark rows.

Usage:
  OPENAI_BASE_URL=... PREDICTMEM_MODEL=... python scripts/check_parity.py --bench locomo --n 50

Exit code 0 only when the SDK mean F1 is within --tol of the stored rows on the sampled
questions. A change that fails here must not replace the frozen benchmark path.
"""

from __future__ import annotations

import argparse
import json
import re
import string
from collections import Counter
from pathlib import Path

from predictmem import LLMClient, LLMConfig, QAEngine
from predictmem.reuse import bm25_rank

ROOT = Path(__file__).resolve().parents[2]
ROWS = {
    "locomo": ROOT / "experiments_results/traces/memory/locomo_predcommit_rows.json",
    "longmemeval": ROOT / "experiments_results/traces/memory/lme_safe_rows.json",
}


def normalize(text: str) -> str:
    text = str(text).lower()
    text = "".join(ch for ch in text if ch not in string.punctuation)
    return re.sub(r"\s+", " ", text).strip()


def f1(pred: str, gold: str) -> float:
    p, g = normalize(pred).split(), normalize(gold).split()
    if not p or not g:
        return 0.0
    same = sum((Counter(p) & Counter(g)).values())
    if not same:
        return 0.0
    precision, recall = same / len(p), same / len(g)
    return 2 * precision * recall / (precision + recall)


def locomo_pool(conv: dict) -> list[str]:
    out, dates = [], conv.get("session_dates") or {}
    for key, sess in conv.get("conversation", {}).items():
        stamp = dates.get(key) or key
        for turn in sess:
            if isinstance(turn, str):
                text, speaker = turn, ""
            else:
                text, speaker = turn.get("text") or turn.get("content") or "", turn.get("speaker", "")
            if text:
                out.append(f"[{stamp}] {speaker}: {text}")
    return out


def build_pools(data_path: str) -> dict[str, list[str]]:
    pools = {}
    for conv in json.loads(Path(data_path).read_text()):
        pool = locomo_pool(conv)
        for qa in conv.get("qa", []):
            if qa.get("question") and qa.get("answer"):
                pools[qa["question"]] = pool
    return pools


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bench", choices=sorted(ROWS), default="locomo")
    parser.add_argument("--n", type=int, default=50)
    parser.add_argument("--tol", type=float, default=0.02)
    parser.add_argument("--data", default="", help="path to locomo10.json")
    args = parser.parse_args()
    if not args.data:
        raise SystemExit("pass --data <locomo10.json> so the SDK can rebuild the evidence pool")

    pools = build_pools(args.data)
    rows = json.loads(ROWS[args.bench].read_text())[: args.n]
    engine = QAEngine(LLMClient(LLMConfig.from_env()))
    sdk, stored = [], []
    for row in rows:
        pool = pools.get(row["q"], [])
        base = "\n".join(bm25_rank(pool, row["q"], 20))[:14000]
        wider = "\n".join(pool)[:30000]
        result = engine.answer(row["q"], base, expand=lambda _q, wider=wider: wider)
        sdk.append(f1(result.answer, row.get("gold", "")))
        stored.append(float(row.get("f1", 0)))
    sdk_mean = sum(sdk) / len(sdk)
    stored_mean = sum(stored) / len(stored)
    delta = abs(sdk_mean - stored_mean)
    print(f"{args.bench}: sdk={sdk_mean:.4f} stored={stored_mean:.4f} delta={delta:.4f} tol={args.tol}")
    raise SystemExit(0 if delta <= args.tol else 1)


if __name__ == "__main__":
    main()
