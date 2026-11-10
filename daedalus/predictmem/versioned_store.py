"""Versioned effect store with prediction-error rollback.

A memory version is committed while the innovation (predicted effect minus observed effect)
stays inside its envelope. When it does not, the store rolls back to the previous certified
version and keeps the rejected write as a shadow record, so the predictor can be calibrated on
the writes it rejected.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional


@dataclass
class EffectRecord:
    state: str
    action: str
    predicted: str
    observed: str
    provenance: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    shadow: bool = False

    @property
    def key(self) -> tuple[str, str]:
        return self.state, self.action


class VersionedEffectStore:
    def __init__(self, path: Optional[str | Path] = None):
        self.path = Path(path) if path else None
        self._records: list[EffectRecord] = []
        if self.path and self.path.exists():
            for line in self.path.read_text().splitlines():
                if line.strip():
                    self._records.append(EffectRecord(**json.loads(line)))

    def _append(self, record: EffectRecord) -> None:
        self._records.append(record)
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a") as fh:
                fh.write(json.dumps(asdict(record)) + "\n")

    def commit(self, record: EffectRecord, innovation: float = 0.0, eps: float = 1.0) -> bool:
        """Commit the version, or roll back when innovation > eps. Returns True on commit."""
        if innovation > eps:
            record.shadow = True
            self._append(record)
            return False
        self._append(record)
        return True

    def lookup(self, state: str, action: str) -> Optional[EffectRecord]:
        for record in reversed(self._records):
            if record.key == (state, action) and not record.shadow:
                return record
        return None

    def shadow(self) -> list[EffectRecord]:
        return [r for r in self._records if r.shadow]

    def __len__(self) -> int:
        return len([r for r in self._records if not r.shadow])

    def __iter__(self) -> Iterable[EffectRecord]:
        return (r for r in self._records if not r.shadow)
