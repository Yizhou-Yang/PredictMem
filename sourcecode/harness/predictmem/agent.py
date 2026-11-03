"""PredictMem agent: predict effect, gate risky actions, admit on surprise."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from daedalus.benchmarks.appworld.agent import ReActAgent
from daedalus.core.llm.client import LLMClient

from .gate import EffectGate
from .predictor import EffectPredictor
from .records import (
    EffectRecord,
    Observation,
    action_signature,
    context_signature,
    task_signature,
)
from .store import VersionedEffectStore
from .surprise import SurpriseScorer


class PredictMemReActAgent(ReActAgent):
    def __init__(self, cfg, run_idx: int | None = None):
        super().__init__(cfg, run_idx=run_idx)
        pm = cfg.predictmem
        self.pm = pm
        predictor_client = LLMClient(
            model=pm.predictor_model,
            temperature=pm.predictor_temperature,
            reasoning_effort=pm.predictor_reasoning_effort,
        )
        judge_client = LLMClient(
            model=pm.judge_model,
            temperature=pm.judge_temperature,
            reasoning_effort=pm.predictor_reasoning_effort,
        )
        self.predictor = EffectPredictor(predictor_client, context_turns=pm.context_turns)
        self.judge_client = judge_client
        self.scorer = SurpriseScorer(pm.weights)
        self.gate = EffectGate(tau_warn=pm.gate.tau_warn, tau_block=pm.gate.tau_block, top_k=pm.top_k)
        self._store: VersionedEffectStore | None = None
        self._events_path: Path | None = None
        self._instruction = ""
        self._task_id = ""
        self._last_prediction = None
        self._last_gate = None

    # ------------------------------------------------------------------ per task
    def _reset_per_task_state(self, instruction: str, task_id: str = "") -> None:
        super()._reset_per_task_state(instruction, task_id=task_id)
        self._instruction = instruction or ""
        self._task_id = task_id or ""
        base = Path(self.trace_dir) / "predictmem"
        base.mkdir(parents=True, exist_ok=True)
        self._store = VersionedEffectStore(
            base / f"{task_id or 'task'}.jsonl",
            max_records=self.pm.max_records,
            versioning=not self.pm.ablation.no_versioning,
        )
        self._events_path = base / "events.jsonl"
        self._last_prediction = None
        self._last_gate = None

    def _log_event(self, event: dict[str, Any]) -> None:
        if self._events_path is None:
            return
        event = {"task_id": self._task_id, "ts": time.time(), **event}
        with self._events_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")

    # ------------------------------------------------------------------ hooks
    def _before_execute(self, code, messages, logger, turn_idx):
        if self.pm.ablation.no_predictor:
            from .records import Prediction

            prediction = Prediction(
                expected_observation="(predictor disabled)",
                expected_success=True,
                risk="low",
                confidence=0.0,
            )
        else:
            prediction = self.predictor.predict(self._instruction, messages, code)
        self._last_prediction = prediction

        decision = None
        if self.pm.gate.enabled and not self.pm.ablation.no_gate and self._store is not None:
            decision = self.gate.decide(code, self._store.valid_records(), turn_idx)
        self._last_gate = decision
        if decision is not None and decision.level == "block":
            note = (
                "PredictMem gate: this action matches a stored effect with high risk "
                f"(score={decision.risk_score:.2f}). It was not executed. "
                "Inspect the current state with a read-only action, or choose a safer alternative."
            )
            self._log_event({"turn": turn_idx, "gate": {"level": "block", "score": decision.risk_score}, "action_sha": action_signature(code)})
            return code, note
        if decision is not None and decision.level == "warn":
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "PredictMem warning: memory predicts this action may have a harmful effect "
                        f"(risk score={decision.risk_score:.2f}). Verify the current state before relying on the result."
                    ),
                }
            )
            self._log_event({"turn": turn_idx, "gate": {"level": "warn", "score": decision.risk_score}, "action_sha": action_signature(code)})
        return code, None

    def _after_execute(self, code, output, success, messages, logger, turn_idx):
        if self._store is None or self._last_prediction is None:
            return
        observed = Observation.from_execution(output, success)
        judge = None
        if not self.pm.ablation.no_predictor:
            judge = self.predictor.judge
        result = self.scorer.score(self._last_prediction, observed, judge=judge)
        admitted = False
        admission_reason = "below_threshold"
        record_id = None
        if success is not None and observed.has_evidence():
            if self.pm.ablation.admit_all or result.score > self.pm.tau_admit:
                record = EffectRecord.new(
                    task_id=self._task_id,
                    task_signature=task_signature(self._instruction),
                    context_signature=context_signature(messages, self.pm.context_turns),
                    turn_idx=turn_idx,
                    action=code,
                    action_signature=action_signature(code),
                    predicted=self._last_prediction,
                    observed=observed,
                    surprise=result.score,
                    surprise_parts=result.parts,
                    rationale=result.rationale,
                    provenance={
                        "predictor_model": self.pm.predictor_model,
                        "judge_model": self.pm.judge_model,
                    },
                )
                admission = self._store.admit(record)
                admitted = admission.admitted
                admission_reason = admission.reason
                record_id = record.record_id if admitted else None
        self._log_event(
            {
                "turn": turn_idx,
                "action_sha": action_signature(code),
                "prediction": self._last_prediction.to_dict(),
                "observation": observed.to_dict(),
                "surprise": {"score": result.score, "parts": result.parts, "rationale": result.rationale},
                "admitted": admitted,
                "admission_reason": admission_reason,
                "record_id": record_id,
                "gate": None if self._last_gate is None else {"level": self._last_gate.level, "score": self._last_gate.risk_score},
            }
        )

    # ------------------------------------------------------------------ memory injection
    def _get_retrieved_memories(self, query, messages, turn_idx):
        # PredictMem does not use DAEDALUS heuristic retrieval; effect records are
        # consumed by the gate and can be rendered by the subclass below.
        return []

    def solve_task(self, *args, **kwargs):
        trace = super().solve_task(*args, **kwargs)
        if self._store is not None:
            try:
                self._store.snapshot(Path(self.trace_dir) / "predictmem" / f"{self._task_id or 'task'}_bank.json")
            except Exception:
                pass
        return trace
