"""BM25 retrieval over effect records with confidence and recency weighting."""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from .records import EffectRecord

_TOKEN = re.compile(r"[A-Za-z0-9_]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall((text or "").lower())


@dataclass
class Retrieved:
    record: EffectRecord
    score: float
    similarity: float


class BM25Index:
    def __init__(self, records: Iterable[EffectRecord], k1: float = 1.5, b: float = 0.75):
        self.records = list(records)
        self.k1, self.b = k1, b
        self.docs = [Counter(tokenize(r.retrieval_text())) for r in self.records]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avg_len = (sum(self.lengths) / len(self.lengths)) if self.lengths else 0.0
        self.df: Counter = Counter()
        for d in self.docs:
            for term in d:
                self.df[term] += 1
        self.n = len(self.docs)

    def search(self, query: str, top_k: int = 5, turn_idx: int = 0) -> list[Retrieved]:
        q = tokenize(query)
        if not q or not self.docs:
            return []
        scored: list[Retrieved] = []
        for rec, doc, length in zip(self.records, self.docs, self.lengths):
            score = 0.0
            for term in q:
                if term not in doc:
                    continue
                idf = math.log(1 + (self.n - self.df[term] + 0.5) / (self.df[term] + 0.5))
                tf = doc[term]
                denom = tf + self.k1 * (1 - self.b + self.b * (length / (self.avg_len or 1)))
                score += idf * (tf * (self.k1 + 1)) / (denom or 1)
            if score <= 0:
                continue
            recency = 1.0 / (1.0 + max(0, turn_idx - rec.turn_idx) / 10.0)
            weighted = score * (0.5 + 0.5 * rec.predicted.confidence) * recency
            scored.append(Retrieved(rec, weighted, score))
        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[:top_k]
