import os

import pytest

from pixelforge.provider import ModelReply
from pixelforge.runtime import AgentRuntime
from pixelforge.tools import Tool, build_registry
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


def test_agent_rejects_symlinked_trace_directory(tmp_path) -> None:
    workspace = Workspace(tmp_path / "workspace")
    outside = tmp_path / "outside"
    outside.mkdir()
    (workspace.root / ".pixelforge").symlink_to(outside, target_is_directory=True)
    runtime = AgentRuntime(
        FakeProvider(),
        build_registry(workspace),
        trace_path=workspace.root / ".pixelforge" / "traces.jsonl",
    )

    with pytest.raises(RuntimeError, match="Trace path"):
        runtime.run("Inspect the project.")

    assert not (outside / "traces.jsonl").exists()


def test_agent_rejects_symlinked_trace_file(tmp_path) -> None:
    workspace = Workspace(tmp_path / "workspace")
    trace_directory = workspace.root / ".pixelforge"
    trace_directory.mkdir()
    outside_trace = tmp_path / "outside.jsonl"
    outside_trace.write_text("preserve this file\n", encoding="utf-8")
    trace_path = trace_directory / "traces.jsonl"
    trace_path.symlink_to(outside_trace)
    runtime = AgentRuntime(
        FakeProvider(),
        build_registry(workspace),
        trace_path=trace_path,
    )

    with pytest.raises(RuntimeError, match="Trace path"):
        runtime.run("Inspect the project.")

    assert outside_trace.read_text(encoding="utf-8") == "preserve this file\n"


def test_agent_rejects_hard_linked_trace_file(tmp_path) -> None:
    workspace = Workspace(tmp_path / "workspace")
    trace_directory = workspace.root / ".pixelforge"
    trace_directory.mkdir()
    protected_file = tmp_path / "protected.jsonl"
    protected_file.write_text("preserve this file\n", encoding="utf-8")
    trace_path = trace_directory / "traces.jsonl"
    os.link(protected_file, trace_path)
    runtime = AgentRuntime(
        FakeProvider(),
        build_registry(workspace),
        trace_path=trace_path,
    )

    with pytest.raises(RuntimeError, match="Trace path"):
        runtime.run("Inspect the project.")

    assert protected_file.read_text(encoding="utf-8") == "preserve this file\n"


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="named pipes are unavailable")
def test_agent_rejects_non_regular_trace_target_without_blocking(tmp_path) -> None:
    workspace = Workspace(tmp_path / "workspace")
    trace_directory = workspace.root / ".pixelforge"
    trace_directory.mkdir()
    trace_path = trace_directory / "traces.jsonl"
    os.mkfifo(trace_path)
    runtime = AgentRuntime(
        FakeProvider(),
        build_registry(workspace),
        trace_path=trace_path,
    )

    with pytest.raises(RuntimeError, match="Trace path"):
        runtime.run("Inspect the project.")


def test_agent_step_limit(tmp_path) -> None:
    class NeverDone:
        def complete(self, messages, tools):
            return ModelReply("", [{
                "id": "loop", "type": "function",
                "function": {"name": "list_project_files", "arguments": "{}"},
            }])

    runtime = AgentRuntime(NeverDone(), build_registry(Workspace(tmp_path)), max_steps=1)
    with pytest.raises(RuntimeError, match="limit"):
        runtime.run("Keep going.")


def test_agent_rejects_too_many_tool_calls_in_one_turn(tmp_path) -> None:
    class Flood:
        def complete(self, messages, tools):
            return ModelReply("", [
                {
                    "id": f"call-{index}",
                    "type": "function",
                    "function": {"name": "list_project_files", "arguments": "{}"},
                }
                for index in range(9)
            ])

    runtime = AgentRuntime(Flood(), build_registry(Workspace(tmp_path)))
    with pytest.raises(RuntimeError, match="one step"):
        runtime.run("List files repeatedly.")


def test_agent_enforces_total_tool_call_budget(tmp_path) -> None:
    class Flood:
        def complete(self, messages, tools):
            return ModelReply("", [
                {
                    "id": f"call-{index}-{len(messages)}",
                    "type": "function",
                    "function": {"name": "list_project_files", "arguments": "{}"},
                }
                for index in range(8)
            ])

    runtime = AgentRuntime(Flood(), build_registry(Workspace(tmp_path)))
    with pytest.raises(RuntimeError, match="total tool-call limit"):
        runtime.run("Continue.")


def test_agent_rejects_malformed_tool_arguments(tmp_path) -> None:
    class Malformed:
        def complete(self, messages, tools):
            return ModelReply("", [{
                "id": "call-1",
                "type": "function",
                "function": {"name": "list_project_files", "arguments": {"unexpected": "object"}},
            }])

    runtime = AgentRuntime(Malformed(), build_registry(Workspace(tmp_path)))
    with pytest.raises(TypeError, match="JSON string"):
        runtime.run("List files.")


def test_agent_rejects_oversized_user_prompt_before_provider_call(tmp_path) -> None:
    class NoCalls:
        called = False

        def complete(self, messages, tools):
            self.called = True
            return ModelReply("unexpected", [])

    provider = NoCalls()
    runtime = AgentRuntime(provider, build_registry(Workspace(tmp_path)))
    with pytest.raises(ValueError, match="64 KiB"):
        runtime.run("x" * (64 * 1024 + 1))
    assert provider.called is False


def test_agent_rejects_oversized_system_prompt(tmp_path) -> None:
    runtime = AgentRuntime(FakeProvider(), build_registry(Workspace(tmp_path)))
    with pytest.raises(ValueError, match="32 KiB"):
        runtime.run("Small task.", system_prompt="x" * (32 * 1024 + 1))


def test_agent_rejects_oversized_model_content(tmp_path) -> None:
    class Verbose:
        def complete(self, messages, tools):
            return ModelReply("x" * (128 * 1024 + 1), [])

    runtime = AgentRuntime(Verbose(), build_registry(Workspace(tmp_path)))
    with pytest.raises(RuntimeError, match="128 KiB"):
        runtime.run("Small task.")


def test_agent_replaces_oversized_tool_result_with_bounded_error(tmp_path) -> None:
    class ResultInspector:
        def __init__(self):
            self.received = None
            self.calls = 0

        def complete(self, messages, tools):
            self.calls += 1
            if self.calls == 1:
                return ModelReply("", [{
                    "id": "large-call",
                    "type": "function",
                    "function": {"name": "large_output", "arguments": "{}"},
                }])
            self.received = messages[-1]["content"]
            return ModelReply("Result safely bounded.", [])

    registry = build_registry(Workspace(tmp_path))
    registry.register(Tool(
        name="large_output",
        description="Return an intentionally oversized result for testing.",
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
        handler=lambda _args: {"payload": "x" * (256 * 1024)},
    ))
    provider = ResultInspector()
    runtime = AgentRuntime(provider, registry)
    assert runtime.run("Check output limits.") == "Result safely bounded."
    assert provider.received is not None
    assert "omitted because the run output budget was exceeded" in provider.received
    assert len(provider.received.encode("utf-8")) < 1024
