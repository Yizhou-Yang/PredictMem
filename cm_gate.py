"""Borrowed from CuratorMem: a per-entry certificate and a withhold action.

PredictMem predicts the *effect of an action* and decides commit/probe/clarify/abstain.
The part worth borrowing is smaller and sharper: a verdict on a stored record is only
admissible when it rests on a record the acting model did not write, and an entry that
fails that test is **withheld**, not annotated.

Why withhold: measured on the CuratorMem side, serving an unendorsed entry with a warning
is worse than serving nothing -- the model reads the warning as an answer. The split was
0.935 mean score for endorsed blocks against 0.344 for unendorsed ones.

This module is deliberately independent of both codebases: it takes a plain record dict.

    gate = Certificate(trusted=("gold", "env", "probe", "consistency"))
    gate.admit(record)            -> True / False
    gate.basis(record)            -> "env" | "probe" | ... | None
    gate.select(records, k=3)     -> the entries the agent is allowed to read
"""

from __future__ import annotations

from typing import Any, Iterable

TRUSTED_PROVENANCE = ("gold", "env", "probe", "consistency")


class Certificate:
    """Admits a stored entry only when its outcome did not come from its author."""

    def __init__(self, trusted: Iterable[str] = TRUSTED_PROVENANCE,
                 min_score: float = 0.5) -> None:
        self.trusted = tuple(trusted)
        self.min_score = min_score

    # ── the two keys ────────────────────────────────────────────────────────
    def basis(self, record: dict[str, Any]) -> str | None:
        """Which trusted source backs this record, if any."""
        prov = str(record.get("score_provenance") or record.get("provenance") or "").lower()
        if prov not in self.trusted:
            return None
        if record.get("self_assessed"):
            return None
        return prov

    def admit(self, record: dict[str, Any]) -> bool:
        if self.basis(record) is None:
            return False
        try:
            return float(record.get("score") or 0.0) >= self.min_score
        except (TypeError, ValueError):
            return False

    # ── what the model may see ──────────────────────────────────────────────
    def select(self, records: list[dict[str, Any]], k: int = 3) -> list[dict[str, Any]]:
        """Endorsed records only -- a failed entry is withheld, never annotated."""
        kept = [r for r in records if self.admit(r)]
        kept.sort(key=lambda r: float(r.get("score") or 0.0), reverse=True)
        return kept[:k]

    def render(self, records: list[dict[str, Any]], k: int = 3) -> str:
        kept = self.select(records, k)
        if not kept:
            return ""
        lines = []
        for r in kept:
            text = str(r.get("answer") or r.get("text") or "").strip()
            if text:
                lines.append("- " + text[:400])
        return "\n".join(lines)
