"""Configuration for the PredictMem arm."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GateConfig:
    enabled: bool = True
    tau_warn: float = 0.45
    tau_block: float = 0.75


@dataclass
class AblationConfig:
    no_predictor: bool = False
    admit_all: bool = False
    no_versioning: bool = False
    no_gate: bool = False


@dataclass
class PredictMemConfig:
    enabled: bool = False
    predictor_model: str = "openai/hy3"
    predictor_reasoning_effort: str = "high"
    predictor_temperature: float = 0.0
    judge_model: str = "openai/hy3"
    judge_temperature: float = 0.0
    context_turns: int = 3
    tau_admit: float = 0.55
    weights: dict[str, float] = field(default_factory=lambda: {"semantic": 0.3, "judge": 0.5, "execution": 0.2})
    retriever: str = "bm25"  # bm25 | dense
    top_k: int = 5
    max_records: int = 200
    shared_bank: bool = False
    gate: GateConfig = field(default_factory=GateConfig)
    ablation: AblationConfig = field(default_factory=AblationConfig)

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "PredictMemConfig":
        d = d or {}
        gate = GateConfig(**{k: d.get("gate", {}).get(k, getattr(GateConfig(), k)) for k in ("enabled", "tau_warn", "tau_block")})
        ab = AblationConfig(**{k: d.get("ablation", {}).get(k, getattr(AblationConfig(), k)) for k in ("no_predictor", "admit_all", "no_versioning", "no_gate")})
        weights = dict(d.get("weights") or {"semantic": 0.3, "judge": 0.5, "execution": 0.2})
        return cls(
            enabled=bool(d.get("enabled", False)),
            predictor_model=d.get("predictor_model", "openai/hy3"),
            predictor_reasoning_effort=d.get("predictor_reasoning_effort", "high"),
            predictor_temperature=float(d.get("predictor_temperature", 0.0)),
            judge_model=d.get("judge_model", "openai/hy3"),
            judge_temperature=float(d.get("judge_temperature", 0.0)),
            context_turns=int(d.get("context_turns", 3)),
            tau_admit=float(d.get("tau_admit", 0.55)),
            weights=weights,
            retriever=d.get("retriever", "bm25"),
            top_k=int(d.get("top_k", 5)),
            max_records=int(d.get("max_records", 200)),
            shared_bank=bool(d.get("shared_bank", False)),
            gate=gate,
            ablation=ab,
        )
