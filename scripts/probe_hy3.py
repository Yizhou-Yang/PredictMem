"""Real, bounded HY3 text + tool-call round trip via official DAEDALUS client."""
import json
import os
from pathlib import Path
import time

from dotenv import load_dotenv
from daedalus.core.logging.accounting import CostAccounting

ROOT = Path(__file__).resolve().parents[1]


def main():
    load_dotenv(ROOT / ".env", override=False)
    if not os.environ.get("OPENAI_BASE_URL") or not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("Supply endpoint and key at runtime.")
    os.environ["OPENAI_API_BASE"] = os.environ["OPENAI_BASE_URL"]
    acc = CostAccounting.standalone(ROOT / "outputs" / "transport_probe",
                                    experiment_name="hy3_transport_probe")
    llm = acc.client("openai/hy3", "solver", component="transport_probe", temperature=0.0,
                     reasoning_effort="high", timeout=600)
    started = time.monotonic()
    plain = llm.generate([{"role": "user", "content": "Reply exactly: OK"}], max_tokens=4096)
    assert plain.content.strip() == "OK", "Plain-text check failed"
    tools = [{"type": "function", "function": {
        "name": "sum_numbers", "description": "Return the sum of two integers.",
        "parameters": {"type": "object", "properties": {
            "a": {"type": "integer"}, "b": {"type": "integer"}},
            "required": ["a", "b"], "additionalProperties": False}}}]
    messages = [{"role": "user", "content": "Use sum_numbers to compute 2 plus 3."}]
    call = llm.generate(messages, tools=tools,
                        tool_choice="auto",
                        max_tokens=4096)
    if not call.tool_calls or len(call.tool_calls) != 1:
        print(json.dumps({"status": "failed", "stage": "native_tool_call",
                          "response_content": call.content,
                          "raw_choices": call.raw.get("choices"),
                          "prompt_tokens": call.prompt_tokens,
                          "completion_tokens": call.completion_tokens}, indent=2))
        raise SystemExit("Expected one native tool call; do not start benchmark runs.")
    tc = call.tool_calls[0]
    params = json.loads(tc.arguments)
    assert tc.name == "sum_numbers" and params == {"a": 2, "b": 3}, "Unexpected tool arguments"
    messages += [{"role": "assistant", "content": call.content or None,
                  "tool_calls": [{"id": tc.id, "type": "function", "function": {
                      "name": tc.name, "arguments": tc.arguments}}]},
                 {"role": "tool", "tool_call_id": tc.id, "content": "5"},
                 {"role": "user", "content": "Return exactly the numeric result and nothing else."}]
    answer = llm.generate(messages, max_tokens=4096)
    assert answer.content.strip() == "5", "Tool result not grounded in final answer"
    summary = {"status": "passed", "logical_calls": 3, "text_ok": plain.content.strip() == "OK",
               "native_function_call": True, "tool_result_roundtrip": True,
               "requested_model": "openai/hy3", "returned_models": [
                   r.returned_model for r in (plain, call, answer)],
               "prompt_tokens": sum(r.prompt_tokens for r in (plain, call, answer)),
               "completion_tokens": sum(r.completion_tokens for r in (plain, call, answer)),
               "elapsed_seconds": round(time.monotonic() - started, 3),
               "price_available": all(r.estimated_cost_usd is not None for r in (plain, call, answer)),
               "reasoning_effort": "high requested; effective provider behavior not independently measured",
               "historical_probe_accounting": {k: acc.summary().get(k) for k in (
                   "estimated_total_cost_usd", "cost_complete", "num_completed_calls",
                   "num_failed_without_usage", "num_launches", "tokens_total")},
               "accounting_scope": "all probe launches, including earlier compatibility failures; not just this three-call run",
               "scope": "transport check only, not a benchmark score"}
    dest = ROOT / "results" / "hy3_transport_probe.json"
    dest.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
