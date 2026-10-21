"""Data model for PredictMem: predictions, observations, effect records."""
from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()


_CODE_WS = re.compile(r"\s+")
_COMMENTS = re.compile(r"#.*")


def normalize_action(code: str) -> str:
    """Normalize code for dedupe/version keys: strip comments, collapse whitespace."""
    text = _COMMENTS.sub("", code or "")
    text = _CODE_WS.sub(" ", text).strip()
    return text


def action_signature(code: str) -> str:
    return _sha(normalize_action(code))


def task_signature(instruction: str) -> str:
    return _sha(_CODE_WS.sub(" ", (instruction or "").strip().lower()))


def context_signature(messages: list[dict[str, str]], k: int = 3) -> str:
    tail = messages[-2 * k :] if messages else []
    text = "\n".join(f"{m.get('role','')}:{m.get('content','')}" for m in tail)
    return _sha(text)


@dataclass
class Prediction:
    expected_observation: str = ""
    expected_state_changes: list[str] = field(default_factory=list)
    expected_success: bool = True
    risk: str = "low"  # low | medium | high
    confidence: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Prediction":
        return cls(
            expected_observation=str(d.get("expected_observation", "")),
            expected_state_changes=list(d.get("expected_state_changes") or []),
            expected_success=bool(d.get("expected_success", True)),
            risk=str(d.get("risk", "low")).lower(),
            confidence=float(d.get("confidence", 0.5)),
        )


@dataclass
class Observation:
    success: bool = True
    output: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_execution(cls, output: str, success: bool) -> "Observation":
        text = output or ""
        return cls(success=success, output=text, error="" if success else text[:2000])

    def has_evidence(self) -> bool:
        return bool((self.output or "").strip()) or bool((self.error or "").strip())


@dataclass
class EffectRecord:
    record_id: str
    task_id: str
    task_signature: str
    context_signature: str
    turn_idx: int
    action: str
    action_signature: str
    predicted: Prediction
    observed: Observation
    surprise: float
    surprise_parts: dict[str, float]
    rationale: str
    provenance: dict[str, Any]
    version: int = 1
    supersedes: str | None = None
    superseded_by: str | None = None
    valid: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @staticmethod
    def new(**kwargs: Any) -> "EffectRecord":
        kwargs.setdefault("record_id", uuid.uuid4().hex)
        return EffectRecord(**kwargs)

    def key(self) -> tuple[str, str, str]:
        return (self.task_signature, self.action_signature, self.context_signature)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "EffectRecord":
        return cls(
            record_id=d["record_id"],
            task_id=d.get("task_id", ""),
            task_signature=d.get("task_signature", ""),
            context_signature=d.get("context_signature", ""),
            turn_idx=int(d.get("turn_idx", 0)),
            action=d.get("action", ""),
            action_signature=d.get("action_signature", ""),
            predicted=Prediction.from_dict(d.get("predicted") or {}),
            observed=Observation(**{k: d.get("observed", {}).get(k, "") for k in ("success", "output", "error")}),
            surprise=float(d.get("surprise", 0.0)),
            surprise_parts=dict(d.get("surprise_parts") or {}),
            rationale=d.get("rationale", ""),
            provenance=dict(d.get("provenance") or {}),
            version=int(d.get("version", 1)),
            supersedes=d.get("supersedes"),
            superseded_by=d.get("superseded_by"),
            valid=bool(d.get("valid", True)),
            created_at=d.get("created_at", ""),
        )

    def retrieval_text(self, max_output: int = 300) -> str:
        return " | ".join(
            [
                self.action[:500],
                self.predicted.expected_observation[:500],
                self.observed.output[:max_output],
            ]
        )
