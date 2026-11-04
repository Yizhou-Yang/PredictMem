"""Reuse layer shared by every benchmark: stored effects, skeleton replay, retrieval."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from .core import EffectRecord, EffectStore, normalize

CALL_RE = re.compile(r"^\s*([A-Za-z_][\w]*)\s*\((.*)\)\s*$", re.S)
ARG_RE = re.compile(r"([A-Za-z_][\w]*)\s*=")


def skeletonize(action: str) -> str:
    """Keep the tool name and argument names, drop the values.

    Replaying a stored call with stale identifiers (order ids, user ids) fails on a new episode;
    replaying the skeleton lets the policy fill the current values.
    """
    match = CALL_RE.match(str(action))
    if not match:
        return str(action)[:200]
    name, body = match.group(1), match.group(2)
    keys = ARG_RE.findall(body)
    return f"{name}(" + ", ".join(f"{k}=<from current task>" for k in keys) + ")" if keys else f"{name}()"


def bm25_rank(pool: Iterable[str], query: str, k: int = 10) -> list[str]:
    q = Counter(normalize(query).split())
    scored = []
    for text in pool:
        c = Counter(normalize(text).split())
        overlap = sum(min(c[w], q[w]) for w in q)
        if overlap:
            scored.append((overlap, text))
    scored.sort(key=lambda item: -item[0])
    return [text for _, text in scored[:k]]


@dataclass
class Reuse:
    """Two reads of the same effect store."""

    store: EffectStore

    def replay_skeleton(self, state: str, action_prefix: str, limit: int = 20) -> list[str]:
        hits = self.store.search(state + " " + action_prefix, k=limit)
        return [skeletonize(record.action) for record in hits]

    def retrieve(self, records: list[EffectRecord], query: str, k: int = 10) -> list[str]:
        pool = [f"[{r.provenance.get('date','')}] {r.observed}" for r in records]
        return bm25_rank(pool, query, k)
