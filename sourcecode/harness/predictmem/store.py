"""Versioned, append-only effect store with dedupe and eviction."""
from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .records import EffectRecord


def _obs_hash(record: EffectRecord) -> str:
    text = (record.observed.output or record.observed.error or "")[:500]
    return hashlib.sha256(text.encode("utf-8", "ignore")).hexdigest()


@dataclass
class AdmissionResult:
    admitted: bool
    reason: str
    record: EffectRecord | None = None
    superseded: str | None = None


class VersionedEffectStore:
    def __init__(self, path: Path | str, max_records: int = 200, versioning: bool = True):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_records = max_records
        self.versioning = versioning
        self._lock = threading.Lock()
        self._records: list[EffectRecord] = []
        self._seen_obs: set[str] = set()
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = EffectRecord.from_dict(json.loads(line))
            except Exception:
                continue
            self._records.append(rec)
            self._seen_obs.add(_obs_hash(rec))

    def _append(self, record: EffectRecord) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
            fh.flush()

    def valid_records(self) -> list[EffectRecord]:
        with self._lock:
            return [r for r in self._records if r.valid]

    def all_records(self) -> list[EffectRecord]:
        with self._lock:
            return list(self._records)

    def _latest_for_key(self, record: EffectRecord) -> EffectRecord | None:
        key = record.key()
        candidates = [r for r in self._records if r.key() == key and r.valid]
        return candidates[-1] if candidates else None

    def _conflicts(self, old: EffectRecord, new: EffectRecord) -> bool:
        # Conflict when expected success flips or risk level changes materially.
        if old.predicted.expected_success != new.predicted.expected_success:
            return True
        if old.predicted.risk != new.predicted.risk:
            return True
        return False

    def _evict_if_needed(self) -> None:
        if len(self._records) <= self.max_records:
            return
        # Evict lowest priority valid records: low surprise, older, low confidence.
        valid = [r for r in self._records if r.valid]
        valid.sort(key=lambda r: (r.surprise * r.predicted.confidence, r.created_at))
        excess = len(self._records) - self.max_records
        for rec in valid[:excess]:
            rec.valid = False
            rec.rationale = (rec.rationale + " | evicted").strip(" |")

    def admit(self, record: EffectRecord) -> AdmissionResult:
        with self._lock:
            if not record.observed.has_evidence():
                return AdmissionResult(False, "no_evidence")
            h = _obs_hash(record)
            if h in self._seen_obs:
                return AdmissionResult(False, "duplicate_observation")
            superseded = None
            if self.versioning:
                old = self._latest_for_key(record)
                if old is not None and self._conflicts(old, record):
                    old.valid = False
                    old.superseded_by = record.record_id
                    record.version = old.version + 1
                    record.supersedes = old.record_id
                    superseded = old.record_id
            self._records.append(record)
            self._seen_obs.add(h)
            self._evict_if_needed()
            self._append(record)
            return AdmissionResult(True, "admitted", record, superseded)

    def stats(self) -> dict[str, Any]:
        with self._lock:
            valid = [r for r in self._records if r.valid]
            return {
                "total": len(self._records),
                "valid": len(valid),
                "superseded": sum(1 for r in self._records if r.superseded_by),
                "evicted": sum(1 for r in self._records if not r.valid and not r.superseded_by),
            }

    def snapshot(self, path: Path | str) -> None:
        Path(path).write_text(
            json.dumps([r.to_dict() for r in self._records], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
