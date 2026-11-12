from pixelforge.provider import ModelReply
from pixelforge.runtime import AgentRuntime
from pixelforge.tools import build_registry
from pixelforge.workspace import Workspace


class FakeProvider:
    def __init__(self):
        self.calls = 0

    def complete(self, messages, tools):
        self.calls += 1
        if self.calls == 1:
            return ModelReply("", [{
                "id": "call-1", "type": "function",
                "function": {"name": "write_text_file",
                             "arguments": '{"path":"notes.txt","content":"created by agent"}'},
            }])
        return ModelReply("Done. I created notes.txt.", [])


def test_agent_tool_loop_and_trace(tmp_path) -> None:
    workspace = Workspace(tmp_path / "workspace")
    provider = FakeProvider()
    trace = tmp_path / "trace.jsonl"
    runtime = AgentRuntime(provider, build_registry(workspace), trace_path=trace)
    assert runtime.run("Create a notes file.") == "Done. I created notes.txt."
    assert workspace.read_text("notes.txt") == "created by agent"
    assert provider.calls == 2
    assert '"event": "tool_result"' in trace.read_text()


def test_agent_step_limit(tmp_path) -> None:
    import pytest

    class NeverDone:
        def complete(self, messages, tools):
            return ModelReply("", [{
                "id": "loop", "type": "function",
                "function": {"name": "list_project_files", "arguments": "{}"},
            }])

    runtime = AgentRuntime(NeverDone(), build_registry(Workspace(tmp_path)), max_steps=1)
    with pytest.raises(RuntimeError, match="limit"):
        runtime.run("Keep going.")
