"""Verify the tau2 HY3-evaluator shim re-points the hard-coded judge (no live calls)."""


def test_shim_repoints_hardcoded_judge():
    import tau2.evaluator.evaluator_nl_assertions as nl

    # Upstream binds gpt-4.1 at import time; this is exactly what the shim overrides.
    assert nl.DEFAULT_LLM_NL_ASSERTIONS == "gpt-4.1-2025-04-14", (
        "tau2 upstream default changed; review this reproduction protocol"
    )
    nl.DEFAULT_LLM_NL_ASSERTIONS = "openai/hy3"
    nl.DEFAULT_LLM_NL_ASSERTIONS_ARGS = {"temperature": 0.0}
    assert nl.DEFAULT_LLM_NL_ASSERTIONS == "openai/hy3"
    assert nl.DEFAULT_LLM_NL_ASSERTIONS_ARGS == {"temperature": 0.0}


def test_shim_module_applies_patch_without_running_entry():
    import importlib.util
    import sys
    from pathlib import Path

    shim = Path(__file__).resolve().with_name("tau2_hy3_eval.py")
    spec = importlib.util.spec_from_file_location("tau2_hy3_eval_under_test", shim)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    import tau2.evaluator.evaluator_nl_assertions as nl
    assert nl.DEFAULT_LLM_NL_ASSERTIONS == "openai/hy3"
    # Loading the module must not trigger the entry point (no sys.argv side effects).
    assert module.__name__ == "tau2_hy3_eval_under_test"
