"""Predictor shared by every benchmark: one interface, two prompts."""

from __future__ import annotations

import re

from .core import Prediction, agree
from .llm import LLMClient

EFFECT_PROMPT = (
    "Predict the immediate effect of the proposed action. Do not assume the task succeeds.\n"
    "Return JSON: {\"effect\": \"<short concrete observation>\", \"confidence\": 0.0-1.0}.\n"
    "CONTEXT:\n{context}\nACTION: {action}"
)

ANSWER_PROMPT = (
    "Predict the short answer that this evidence implies for the question. "
    "If the evidence does not determine an answer, output exactly INSUFFICIENT.\n"
    "EVIDENCE:\n{context}\n\nQUESTION: {action}\nPREDICTED ANSWER:"
)


class Predictor:
    def __init__(self, client: LLMClient, kind: str = "answer"):
        self.client = client
        self.kind = kind

    def __call__(self, context: str, action: str) -> Prediction:
        if self.kind == "answer":
            out = self.client.generate(ANSWER_PROMPT.format(context=context[:20000], action=action), 120)
            if out.upper().startswith("INSUFFICIENT"):
                return Prediction(expected_effect="INSUFFICIENT", confidence=0.0, kind="answer")
            return Prediction(expected_effect=out, confidence=1.0, kind="answer")
        out = self.client.generate(EFFECT_PROMPT.format(context=context[:12000], action=action), 150)
        match = re.search(r"\{.*\}", out, re.S)
        if not match:
            return Prediction(expected_effect="", confidence=0.0, kind="effect")
        import json

        try:
            data = json.loads(match.group(0))
        except Exception:
            data = {}
        return Prediction(expected_effect=str(data.get("effect", "")), confidence=float(data.get("confidence", 0) or 0), kind="effect")
