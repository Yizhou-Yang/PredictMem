"""Verify the tau2 HY3-evaluator shim re-points the hard-coded judge (no live calls)."""


def test_shim_repoints_hardcoded_judge():
    # Check the pristine upstream binding in an isolated interpreter. Other tests
    # legitimately import the shim first, so checking shared module state is invalid.
    import os
    from pathlib import Path
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[1]
    code = (
        "import tau2.evaluator.evaluator_nl_assertions as nl; "
        "assert nl.DEFAULT_LLM_NL_ASSERTIONS == 'gpt-4.1-2025-04-14'; "
        f"import sys; sys.path.insert(0, {str(root / 'scripts')!r}); "
        "import tau2_hy3_eval; "
        "assert nl.DEFAULT_LLM_NL_ASSERTIONS == 'openai/hy3'; "
        "assert nl.DEFAULT_LLM_NL_ASSERTIONS_ARGS == {'temperature': 0.0}"
    )
    subprocess.run([sys.executable, "-B", "-c", code],
                   cwd=root / "vendor/daedalus", env=os.environ.copy(),
                   check=True, capture_output=True, text=True, timeout=45)


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
