"""Agent adapter: route a predicted task/effect type to a procedure."""

from __future__ import annotations

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
