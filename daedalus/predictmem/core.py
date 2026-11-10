"""Unified PredictMem core: predict an effect type, route to a procedure.

Every benchmark supplies two things:
  - a predictor: context -> Prediction(type, expected_effect, confidence)
  - a procedure table: type -> callable that produces the next action
The controller only routes; it never blocks and never terminates.
"""

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Prediction:
    type: str                      # e.g. "count", "date", "clean", "exchange"
    expected_effect: str = ""      # free-text description of the predicted effect
    confidence: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class Decision:
    procedure: str
    prediction: Prediction
    reason: str = "routed"


class Router:
    """Maps a predicted effect type to a procedure; falls back to a default."""

    def __init__(self, procedures: dict[str, Callable[..., Any]], default: str):
        self.procedures = procedures
        self.default = default

    def decide(self, prediction: Prediction) -> Decision:
        name = prediction.type if prediction.type in self.procedures else self.default
        return Decision(name, prediction, f"type={prediction.type}->{name}")

    def run(self, prediction: Prediction, *args, **kwargs):
        decision = self.decide(prediction)
        return decision, self.procedures[decision.procedure](*args, **kwargs)


class PredictMem:
    """Facade: predict(context) -> route -> run procedure."""

    def __init__(self, predict: Callable[[Any], Prediction],
                 procedures: dict[str, Callable[..., Any]], default: str):
        self.predict = predict
        self.router = Router(procedures, default)

    def step(self, context: Any, *args, **kwargs):
        prediction = self.predict(context)
        return self.router.run(prediction, *args, **kwargs)
