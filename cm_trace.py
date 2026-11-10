"""Borrowed from CuratorMem: keep the read path auditable in the trace.

PredictMem's runners write a row per task, but nothing records *why* a piece of memory
was served -- which read path fired, or what licensed each entry. That makes a
withhold-vs-annotate comparison unrecomputable after the fact, and it is what hid a
broken gate for a whole sweep on the other side.

Usage:

    from cm_trace import drop_fields
    row.update(drop_fields())        # after each task

The gate in `cm_gate.py` increments these; nothing else has to.
"""

from __future__ import annotations

BRANCH: dict[str, int] = {}
ENDORSE: list = []


def note_served(bases: list) -> None:
    """Call once per read that produced a non-empty block."""
    BRANCH["served"] = BRANCH.get("served", 0) + 1
    ENDORSE.extend(bases)
    if any(b is not None for b in bases):
        BRANCH["served_endorsed"] = BRANCH.get("served_endorsed", 0) + 1
    else:
        BRANCH["served_unendorsed"] = BRANCH.get("served_unendorsed", 0) + 1


def note_silenced() -> None:
    """Call when the gate deliberately served nothing."""
    BRANCH["silenced"] = BRANCH.get("silenced", 0) + 1


def drop_fields() -> dict:
    """Take the counters accumulated since the last task, and clear them."""
    global BRANCH, ENDORSE
    out = {"read_branches": dict(BRANCH), "endorse_bases": list(ENDORSE)}
    BRANCH = {}
    ENDORSE = []
    return out
