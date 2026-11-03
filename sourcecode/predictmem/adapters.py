"""Agent adapter: route a predicted task/effect type to a procedure."""

from __future__ import annotations

from dataclasses import dataclass

from typing import Any, Callable

from .core import Prediction


class ProcedureRouter:
    """Map a predicted kind to a procedure, with a default fallback.

    Example:
        router = ProcedureRouter(default="act")
        router.register("clean", clean_procedure)
        router.register("heat", heat_procedure)
        router.run(prediction, instruction, observation)
    """

    def __init__(self, default: str = "act"):
        self.default = default
        self._procedures: dict[str, Callable[..., Any]] = {}

    def register(self, kind: str, procedure: Callable[..., Any]) -> None:
        self._procedures[kind] = procedure

    def select(self, prediction: Prediction) -> str:
        return prediction.kind if prediction.kind in self._procedures else self.default

    def run(self, prediction: Prediction, *args: Any, **kwargs: Any) -> tuple[str, Any]:
        name = self.select(prediction)
        return name, self._procedures[name](*args, **kwargs)


@dataclass
class AdapterScope:
    """How much the predictor participates in a benchmark adapter.

    off        : replay/retrieval only; the predictor is not called
    procedure  : the predictor selects a procedure from the predicted task type
    agreement  : the predictor independently predicts the answer; agreement commits
    """

    name: str
    predictor: str = "off"

    def uses_predictor(self) -> bool:
        return self.predictor != "off"


# Chosen from the per-question ablations, not by preference:
# tau2 and LongMemEval lose when the predictor intervenes; ALFWorld gains from procedure
# routing; LoCoMo gains from agreement-gated expansion.
DEFAULT_SCOPES = {
    "tau2": AdapterScope("tau2", "off"),
    "alfworld": AdapterScope("alfworld", "procedure"),
    "longmemeval": AdapterScope("longmemeval", "off"),
    "locomo": AdapterScope("locomo", "agreement"),
}


def scope_for(benchmark: str) -> AdapterScope:
    return DEFAULT_SCOPES.get(benchmark, AdapterScope(benchmark, "off"))
