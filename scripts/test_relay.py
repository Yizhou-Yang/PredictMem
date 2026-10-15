"""Offline checks for the research transport boundary (no real API calls)."""
import pytest
from relay import payload


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


def test_streaming_fails_explicitly():
    with pytest.raises(ValueError, match="Streaming"):
        payload({"messages": [], "stream": True})
