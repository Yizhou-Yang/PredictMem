"""Real HY3 round-trip through tau2's NL-assertions evaluator (one bounded call).

Confirms the explicit evaluator adaptation in tau2_hy3_eval.py actually routes to
HY3 and returns a well-formed judgement, instead of only checking imports.
"""
import json
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=False)
if not os.environ.get("OPENAI_BASE_URL") or not os.environ.get("OPENAI_API_KEY"):
    raise SystemExit("Supply OPENAI_BASE_URL and OPENAI_API_KEY at runtime.")
os.environ["OPENAI_API_BASE"] = os.environ["OPENAI_BASE_URL"]

import tau2.evaluator.evaluator_nl_assertions as nl  # noqa: E402

nl.DEFAULT_LLM_NL_ASSERTIONS = "openai/hy3"
nl.DEFAULT_LLM_NL_ASSERTIONS_ARGS = {"temperature": 0.0}

from tau2.data_model.message import AssistantMessage, SystemMessage, UserMessage  # noqa: E402

trajectory = [
    SystemMessage(role="system", content="Customer-service conversation under evaluation."),
    UserMessage(role="user", content="Please return my delivered item."),
    AssistantMessage(role="assistant", content="Your return has been processed and a refund issued."),
]
checks = nl.NLAssertionsEvaluator.evaluate_nl_assertions(
    trajectory, ["The agent processed the customer's return request."]
)
out = {
    "status": "passed",
    "model": "openai/hy3",
    "checks": [{"nl_assertion": c.nl_assertion, "met": c.met,
                "justification": c.justification} for c in checks],
    "scope": "single evaluator round-trip; not a benchmark score",
}
print(json.dumps(out, indent=2))
