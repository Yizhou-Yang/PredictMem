"""Explicit HY3 tau2 message boundary; never invent content or change STOP semantics.

Empty tool lists are not tool messages. A genuinely empty final response is an
observable protocol error, not a successful task, and is never silently retried.
Installation runs in both the parent and every spawn worker.
"""
from __future__ import annotations

from collections import Counter
from functools import wraps

COUNTS = Counter()


class EmptyHY3MessageError(ValueError):
    pass


def normalize(message):
    if message.tool_calls == []:
        message.tool_calls = None
        COUNTS["empty_tool_list_to_none"] += 1
    if not message.has_content() and not message.tool_calls:
        COUNTS["empty_final_response_rejected"] += 1
        raise EmptyHY3MessageError(
            f"Empty final {type(message).__name__}: no text/audio or nonempty tools; "
            "protocol failure, no fabricated content or automatic task retry"
        )
    return message


def install():
    import tau2.evaluator.evaluator_nl_assertions as nl
    import tau2.user.user_simulator as simulator
    import tau2.user.user_simulator_base as base
    import tau2.utils.llm_utils as llm

    # Must be applied here, not just by a parent script: spawn imports a new process.
    nl.DEFAULT_LLM_NL_ASSERTIONS = "openai/hy3"
    nl.DEFAULT_LLM_NL_ASSERTIONS_ARGS = {"temperature": 0.0}
    if getattr(llm.generate, "_hy3_transport_safety", False):
        return
    original_generate = llm.generate

    @wraps(original_generate)
    def generate(*args, **kwargs):
        model = kwargs.get("model", args[0] if args else None)
        if model != "openai/hy3":
            raise ValueError(f"Experiment model must be HY3; got {model!r}")
        return normalize(original_generate(*args, **kwargs))

    generate._hy3_transport_safety = True
    llm.generate = generate
    simulator.generate = generate
    # NL assertions uses a from-import binding; patch the actual callable as well.
    if hasattr(nl, "generate"):
        nl.generate = generate
    original_flip = base.UserState.flip_roles

    @wraps(original_flip)
    def flip(self):
        for message in self.messages:
            normalize(message)
        return [normalize(message) for message in original_flip(self)]

    base.UserState.flip_roles = flip
    original_user = simulator.UserSimulator._generate_next_message

    @wraps(original_user)
    def user(self, message, state):
        return normalize(original_user(self, message, state))

    simulator.UserSimulator._generate_next_message = user
