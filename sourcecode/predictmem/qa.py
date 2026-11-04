"""Question-answering adapter: independent answer prediction plus agreement-gated search."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Optional

from .core import Prediction, agree
from .predict import Predictor
from .llm import LLMClient


@dataclass
class QAResult:
    answer: str
    predicted: str
    agreed: bool
    expanded: bool


PREDICT_PROMPT = (
    "Predict the short answer that this evidence implies for the question. "
    "If the evidence does not determine an answer, output exactly INSUFFICIENT.\n"
    "EVIDENCE:\n{evidence}\n\nQUESTION: {question}\nPREDICTED ANSWER:"
)

ANSWER_PROMPT = (
    "Answer with ONLY the answer phrase, at most 8 words, no explanation. "
    "Use only the evidence.\n"
    "EVIDENCE:\n{evidence}\n\nQUESTION: {question}\nANSWER:"
)


class QAEngine:
    """Drop-in QA helper. `expand(question)` should return more evidence."""

    def __init__(self, client: Optional[LLMClient] = None):
        self.client = client or LLMClient()
        self.predictor = Predictor(self.client, kind="answer")

    def _predict(self, question: str, evidence: str) -> str:
        return self.predictor(evidence, question).expected_effect

    def _answer(self, question: str, evidence: str) -> str:
        out = self.client.generate(ANSWER_PROMPT.format(evidence=evidence[:20000], question=question), 150)
        out = re.sub(r"^(based on|according to)[^:]*:", "", out, flags=re.I).strip()
        return out.split("\n")[0].strip().strip(".")

    def predict(self, state: str, proposed: str) -> Prediction:
        """Adapter for PredictMem.step(state=evidence, proposed=question)."""
        predicted = self._predict(proposed, state)
        return Prediction(expected_effect=predicted, confidence=1.0 if predicted != "INSUFFICIENT" else 0.0)

    def answer(
        self,
        question: str,
        evidence: str,
        expand: Optional[Callable[[str], str]] = None,
    ) -> QAResult:
        predicted = self._predict(question, evidence)
        answer = self._answer(question, evidence)
        agreed = predicted != "INSUFFICIENT" and agree(predicted, answer)
        if agreed or expand is None:
            return QAResult(answer=answer, predicted=predicted, agreed=agreed, expanded=False)
        wider = expand(question)
        predicted2 = self._predict(question, wider)
        answer2 = self._answer(question, wider)
        agreed2 = predicted2 != "INSUFFICIENT" and agree(predicted2, answer2)
        return QAResult(
            answer=answer2 if agreed2 else answer,
            predicted=predicted2,
            agreed=agreed2,
            expanded=True,
        )
