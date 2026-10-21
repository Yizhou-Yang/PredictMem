"""Effect gate: warn/block actions that memory predicts to be harmful."""
from __future__ import annotations

from dataclasses import dataclass, field

from .records import EffectRecord
from .retrieval import BM25Index, Retrieved


@dataclass
class GateDecision:
    level: str  # pass | warn | block
    risk_score: float
    retrieved: list[Retrieved] = field(default_factory=list)
    reason: str = ""


class EffectGate:
    def __init__(self, tau_warn: float = 0.45, tau_block: float = 0.75, top_k: int = 5):
        self.tau_warn = tau_warn
        self.tau_block = tau_block
        self.top_k = top_k

    @staticmethod
    def _risk_weight(record: EffectRecord) -> float:
        weight = {"high": 1.0, "medium": 0.6, "low": 0.2}.get(record.predicted.risk, 0.4)
        if not record.observed.success:
            weight = min(1.0, weight + 0.2)
        return weight

    def decide(self, code: str, records: list[EffectRecord], turn_idx: int) -> GateDecision:
        if not records:
            return GateDecision("pass", 0.0, [], "empty_memory")
        index = BM25Index(records)
        retrieved = index.search(code, top_k=self.top_k, turn_idx=turn_idx)
        if not retrieved:
            return GateDecision("pass", 0.0, [], "no_match")
        max_raw = max((r.similarity for r in retrieved), default=1.0) or 1.0
        best = 0.0
        for item in retrieved:
            sim = min(1.0, item.similarity / max_raw)
            score = sim * item.record.predicted.confidence * self._risk_weight(item.record)
            best = max(best, score)
        if best >= self.tau_block:
            return GateDecision("block", best, retrieved, "high_risk_match")
        if best >= self.tau_warn:
            return GateDecision("warn", best, retrieved, "risk_match")
        return GateDecision("pass", best, retrieved, "below_threshold")
