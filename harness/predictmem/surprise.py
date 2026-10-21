"""Surprise computation: semantic, LLM-judge, execution mismatch."""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Callable
from dataclasses import dataclass

from .records import Observation, Prediction

_TOKEN = re.compile(r"[A-Za-z0-9_]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall((text or "").lower())


def cosine_similarity(a: str, b: str) -> float:
    ca, cb = Counter(_tokens(a)), Counter(_tokens(b))
    if not ca or not cb:
        return 0.0
    dot = sum(v * cb.get(k, 0) for k, v in ca.items())
    na = math.sqrt(sum(v * v for v in ca.values()))
    nb = math.sqrt(sum(v * v for v in cb.values()))
    return dot / (na * nb) if na and nb else 0.0


@dataclass
class SurpriseResult:
    score: float
    parts: dict[str, float]
    rationale: str


class SurpriseScorer:
    def __init__(self, weights: dict[str, float] | None = None):
        self.weights = weights or {"semantic": 0.3, "judge": 0.5, "execution": 0.2}

    def semantic(self, predicted: Prediction, observed: Observation) -> float:
        pred_text = " ".join([predicted.expected_observation] + list(predicted.expected_state_changes))
        obs_text = observed.output or observed.error
        return max(0.0, min(1.0, 1.0 - cosine_similarity(pred_text, obs_text)))

    def execution(self, predicted: Prediction, observed: Observation) -> float:
        return 0.0 if bool(predicted.expected_success) == bool(observed.success) else 1.0

    def score(
        self,
        predicted: Prediction,
        observed: Observation,
        judge: Callable[[Prediction, Observation], tuple[float, str]] | None = None,
    ) -> SurpriseResult:
        s_sem = self.semantic(predicted, observed)
        s_exec = self.execution(predicted, observed)
        s_judge, judge_reason = 0.5, "judge_unavailable"
        if judge is not None:
            try:
                s_judge, judge_reason = judge(predicted, observed)
                s_judge = max(0.0, min(1.0, float(s_judge)))
            except Exception as exc:  # pragma: no cover - defensive
                s_judge, judge_reason = s_sem, f"judge_error:{type(exc).__name__}"
        w = self.weights
        total = (
            w.get("semantic", 0.3) * s_sem
            + w.get("judge", 0.5) * s_judge
            + w.get("execution", 0.2) * s_exec
        )
        total = max(0.0, min(1.0, total))
        rationale = (
            f"semantic={s_sem:.2f} judge={s_judge:.2f} execution={s_exec:.2f}; "
            f"judge_reason={judge_reason[:200]}"
        )
        return SurpriseResult(total, {"semantic": s_sem, "judge": s_judge, "execution": s_exec}, rationale)
