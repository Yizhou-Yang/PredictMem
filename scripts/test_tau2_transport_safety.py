"""No-API message and fresh-worker evaluator regression."""
import os
from pathlib import Path
import subprocess
import sys
import pytest
from tau2.data_model.message import AssistantMessage, UserMessage
from tau2_transport_safety import normalize, EmptyHY3MessageError


@pytest.mark.parametrize("content", [None, "", "   "])
def test_empty_final_not_success(content):
    with pytest.raises(EmptyHY3MessageError):
        normalize(AssistantMessage(role="assistant", content=content, tool_calls=[]))


def test_empty_tool_list_with_text_is_text():
    message = UserMessage(role="user", content="Keep this content.", tool_calls=[])
    assert normalize(message).content == "Keep this content."
    assert message.tool_calls is None


def test_stop_is_not_blocked():
    from tau2.user.user_simulator import UserSimulator
    message = normalize(UserMessage(role="user", content="###STOP###", tool_calls=[]))
    assert UserSimulator.is_stop(message)


def test_nonempty_tool_call_unchanged():
    from tau2.data_model.message import ToolCall
    message = UserMessage(role="user", tool_calls=[ToolCall(id="a",name="test",arguments={})])
    assert normalize(message).tool_calls[0].name == "test"


def test_spawn_equivalent_fresh_interpreter_route():
    root = Path(__file__).resolve().parents[1]
    code = (
        f"import sys; sys.path.insert(0, {str(root/'scripts')!r}); "
        "from tau2_transport_safety import install; install(); "
        "import tau2.evaluator.evaluator_nl_assertions as nl; "
        "import tau2.utils.llm_utils as u; "
        "assert nl.DEFAULT_LLM_NL_ASSERTIONS == 'openai/hy3'; "
        "assert u.generate._hy3_transport_safety; "
        "import tau2.user.user_simulator as s; assert s.generate is u.generate"
    )
    subprocess.run([sys.executable,"-B","-c",code],cwd=root/"vendor/daedalus",
                   env=os.environ.copy(),check=True,timeout=60,capture_output=True,text=True)
