"""Core objects shared by every adapter."""

from __future__ import annotations

import json
import re
import string
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Optional


@dataclass
class Prediction:
    """An independent prediction of what an action will produce."""

    expected_effect: str = ""
    confidence: float = 0.0
    kind: str = "effect"
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class Decision:
    commit: bool
    reason: str
    prediction: Prediction
    expansion: str = ""


@dataclass
class EffectRecord:
    state: str
    action: str
    predicted: str
    observed: str
    provenance: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    @property
    def key(self) -> tuple[str, str]:
        return self.state, self.action


def normalize(text: str) -> str:
    text = str(text).lower()
    text = "".join(ch for ch in text if ch not in string.punctuation)
    return re.sub(r"\s+", " ", text).strip()


def agree(predicted: str, proposed: str) -> bool:
    """Agreement test used by the controller: one normalized answer contains the other."""
    p, q = normalize(predicted), normalize(proposed)
    if not p or not q:
        return False
    return p == q or p in q or q in p


class EffectStore:
    """Append-only effect records with (state, action) versioning and JSONL persistence."""

    def __init__(self, path: Optional[str | Path] = None):
        self.path = Path(path) if path else None
        self._records: list[EffectRecord] = []
        if self.path and self.path.exists():
            for line in self.path.read_text().splitlines():
                if line.strip():
                    self._records.append(EffectRecord(**json.loads(line)))

    def add(self, record: EffectRecord) -> None:
        # a later record with the same key supersedes the earlier one
        self._records = [r for r in self._records if r.key != record.key]
        self._records.append(record)
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a") as fh:
                fh.write(json.dumps(asdict(record)) + "\n")

    def lookup(self, state: str, action: str) -> Optional[EffectRecord]:
        for record in reversed(self._records):
            if record.key == (state, action):
                return record
        return None

    def search(self, query: str, k: int = 5) -> list[EffectRecord]:
        q = set(normalize(query).split())
        scored = []
        for record in self._records:
            words = set(normalize(record.state + " " + record.action).split())
            overlap = len(q & words)
            if overlap:
                scored.append((overlap, record))
        scored.sort(key=lambda item: -item[0])
        return [record for _, record in scored[:k]]

    def __len__(self) -> int:
        return len(self._records)

    def __iter__(self) -> Iterable[EffectRecord]:
        return iter(self._records)


class PredictMem:
    """Predict, compare, then either commit or expand the search once."""

    def __init__(self, predict: Callable[[str, str], Prediction]):
        self.predict = predict

    def step(
        self,
        state: str,
        proposed: str,
        expand: Optional[Callable[[str], str]] = None,
    ) -> tuple[Decision, str]:
        prediction = self.predict(state, proposed)
        if agree(prediction.expected_effect, proposed):
            return Decision(True, "agreement", prediction), proposed
        if expand is None:
            return Decision(True, "no_expansion_available", prediction), proposed
        expanded_state = expand(state)
        second = self.predict(expanded_state, proposed)
        if agree(second.expected_effect, proposed):
            return Decision(True, "agreement_after_expansion", second), proposed
        return Decision(True, "commit_after_one_expansion", second), proposed
