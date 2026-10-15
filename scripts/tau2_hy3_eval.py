"""Explicit, labeled HY3 adaptation for tau2's internal NL-assertions judge.

tau2 hard-codes its natural-language assertion evaluator to
``gpt-4.1-2025-04-14`` (``tau2.config.DEFAULT_LLM_NL_ASSERTIONS``) and binds that
value into ``tau2.evaluator.evaluator_nl_assertions`` at import time, so neither
DAEDALUS's ``generation.judge_model`` nor the ``references/*`` methods reach it.
This script re-points that module-level binding to HY3 before invoking the
upstream entry point, then dispatches to the requested driver.

PROTOCOL CHANGE — not a silent alias. The official tau2 evaluator is gpt-4.1;
here the same HY3 backbone judges HY3-generated trajectories, which introduces a
self-evaluation bias. Any tau2 number produced through this path must be reported
as a separate "HY3 evaluator" arm and not compared directly against official
tau2 results. This file exists so the change is explicit and auditable.
"""
from __future__ import annotations

import sys

import tau2.evaluator.evaluator_nl_assertions as _nl

_nl.DEFAULT_LLM_NL_ASSERTIONS = "openai/hy3"
_nl.DEFAULT_LLM_NL_ASSERTIONS_ARGS = {"temperature": 0.0}


def _entry() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(
            "usage: tau2_hy3_eval.py "
            "{generation|inference|ace_accumulation|ace_inference} <upstream args...>"
        )
    entry, rest = sys.argv[1], sys.argv[2:]
    sys.argv = [sys.argv[0], *rest]
    if entry == "generation":
        from daedalus.scripts.generation import main
        main()
    elif entry == "inference":
        from daedalus.scripts.inference import main
        main()
    elif entry == "ace_accumulation":
        from references.ace.accumulation import main
        main()
    elif entry == "ace_inference":
        import references.ace.run as ace_run
        ace_run.main(ace_run.METHOD)
    else:
        raise SystemExit(f"unknown entry point: {entry}")


if __name__ == "__main__":
    _entry()
