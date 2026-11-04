"""Generic question-answering benchmark runner.

All benchmark-specific work is reduced to three inputs: a question, a pool of evidence strings
(each already carrying its date/session prefix), and an expansion that returns a larger pool.
Retrieval, prediction, agreement, one-round expansion and commit all live here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Optional

from ..qa import QAEngine
from ..reuse import bm25_rank


@dataclass
class QAExample:
    question: str
    gold: str
    pool: list[str]
    expand: Optional[Callable[[list[str]], list[str]]] = None


def run_one(engine: QAEngine, example: QAExample, k: int = 10, expand_k: int = 20) -> dict:
    base = "\n".join(bm25_rank(example.pool, example.question, k))[:14000]

    def expand(_question: str) -> str:
        pool = example.pool
        if example.expand is not None:
            pool = example.expand(pool)
        return "\n".join(bm25_rank(pool, example.question, expand_k))[:20000]

    result = engine.answer(example.question, base, expand=expand)
    return {
        "q": example.question,
        "gold": example.gold,
        "pred": result.answer,
        "predicted": result.predicted,
        "agree": result.agreed,
        "escalated": result.expanded,
    }


def run(engine: QAEngine, examples: Iterable[QAExample], k: int = 10, expand_k: int = 20) -> list[dict]:
    return [run_one(engine, example, k, expand_k) for example in examples]
