"""The controller shared by every benchmark.

One rule: commit on agreement, expand once on disagreement, then commit. It never abstains and
never terminates, so the worst case is the base policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .core import Prediction, agree


@dataclass
class Outcome:
    action: str
    predicted: str
    committed: bool
    expanded: bool
    reason: str


def run(
    predict: Callable[[str, str], Prediction],
    state: str,
    action: str,
    expand: Callable[[str], str] | None = None,
) -> Outcome:
    first = predict(state, action)
    if agree(first.expected_effect, action):
        return Outcome(action, first.expected_effect, True, False, "agreement")
    if expand is None:
        return Outcome(action, first.expected_effect, True, False, "no_expansion")
    wider = expand(state)
    second = predict(wider, action)
    if agree(second.expected_effect, action):
        return Outcome(action, second.expected_effect, True, True, "agreement_after_expansion")
    return Outcome(action, second.expected_effect, True, True, "commit_after_one_expansion")
