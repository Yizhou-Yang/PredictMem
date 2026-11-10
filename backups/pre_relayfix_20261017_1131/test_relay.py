"""Offline checks for the research transport boundary (no real API calls)."""
import pytest
from relay import audit_record, payload


def test_payload_preserves_native_tools_and_model():
    body = {"model": "hy3", "messages": [{"role": "user", "content": "hello"}],
            "tools": [{"type": "function", "function": {"name": "f"}}],
            "tool_choice": "auto", "reasoning_effort": "high", "temperature": 0.0}
    assert payload(body) == {**body, "stream": False}


def test_no_implicit_effort_or_message_rewriting():
    body = {"model": "hy3", "messages": [{"role": "tool", "tool_call_id": "x", "content": "ok"}]}
    out = payload(body)
    assert "reasoning_effort" not in out
    assert out["messages"] == body["messages"]


def test_unknown_fields_fail_instead_of_silent_drop():
    with pytest.raises(ValueError, match="Unsupported request fields"):
        payload({"messages": [], "unsupported": True})


def test_audit_record_has_no_prompt_or_secret():
    request = {"model": "hy3", "messages": [{"role": "user", "content": "SECRET-PROMPT"}],
               "reasoning_effort": "high"}
    data = {"id": "up1", "model": "hy3", "usage": {"prompt_tokens": 9, "completion_tokens": 4},
            "choices": [{"finish_reason": "length", "message": {"content": "SECRET-OUT"}}]}
    record = audit_record("r1", 0.0, 200, data=data, request=request)
    text = repr(record)
    assert "SECRET" not in text and "Bearer" not in text
    assert record["finish_reason"] == "length" and record["completion_tokens"] == 4
    assert record["n_messages"] == 1 and record["reasoning_effort"] == "high"


def test_streaming_fails_explicitly():
    with pytest.raises(ValueError, match="Streaming"):
        payload({"messages": [], "stream": True})
