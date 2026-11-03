"""LLM-backed effect predictor and surprise judge."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .records import Observation, Prediction

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)
_PROMPT_DIR = Path(__file__).parent / "prompts"


def _extract_json(text: str) -> dict[str, Any]:
    match = _JSON_RE.search(text or "")
    if not match:
        raise ValueError("no JSON object in response")
    return json.loads(match.group(0))


def _render_context(messages: list[dict[str, str]], k: int) -> str:
    tail = messages[-2 * k :] if messages else []
    lines = []
    for msg in tail:
        role = msg.get("role", "?")
        content = (msg.get("content") or "").strip()
        lines.append(f"[{role}] {content[:1200]}")
    return "\n".join(lines) if lines else "(empty)"


class EffectPredictor:
    def __init__(self, client: Any, context_turns: int = 3):
        self.client = client
        self.context_turns = context_turns
        self._predict_prompt = (_PROMPT_DIR / "predict.txt").read_text(encoding="utf-8")
        self._judge_prompt = (_PROMPT_DIR / "judge.txt").read_text(encoding="utf-8")

    def predict(self, instruction: str, messages: list[dict[str, str]], code: str) -> Prediction:
        prompt = self._predict_prompt.replace("<<INSTRUCTION>>", instruction[:4000]).replace(
            "<<CONTEXT>>", _render_context(messages, self.context_turns)
        ).replace("<<CODE>>", code[:6000])
        try:
            response = self.client.generate([{"role": "user", "content": prompt}])
            payload = _extract_json(getattr(response, "content", str(response)))
            return Prediction.from_dict(payload)
        except Exception:
            # Conservative fallback: unknown effect, low confidence, medium risk.
            return Prediction(
                expected_observation="(prediction unavailable)",
                expected_state_changes=[],
                expected_success=True,
                risk="medium",
                confidence=0.0,
            )

    def judge(self, predicted: Prediction, observed: Observation) -> tuple[float, str]:
        prompt = self._judge_prompt.replace(
            "<<PREDICTED>>", json.dumps(predicted.to_dict(), ensure_ascii=False)[:3000]
        ).replace("<<OBSERVED>>", json.dumps(observed.to_dict(), ensure_ascii=False)[:3000])
        try:
            response = self.client.generate([{"role": "user", "content": prompt}])
            payload = _extract_json(getattr(response, "content", str(response)))
            return float(payload.get("score", 0.5)), str(payload.get("reason", ""))[:300]
        except Exception as exc:
            return 0.5, f"judge_failed:{type(exc).__name__}"
