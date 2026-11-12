"""Bounded model/tool loop with compact JSONL tracing."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Protocol

from pixelforge.provider import ModelReply
from pixelforge.tools import ToolRegistry

MAX_TOOL_CALLS_PER_STEP = 8
MAX_TOOL_CALLS_PER_RUN = 32
MAX_TOOL_ARGUMENT_BYTES = 64 * 1024
MAX_TOOL_RESULT_BYTES = 256 * 1024
MAX_TOTAL_RESULT_BYTES = 1024 * 1024


class Provider(Protocol):
    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelReply: ...


class AgentRuntime:
    def __init__(
        self,
        provider: Provider,
        tools: ToolRegistry,
        max_steps: int = 8,
        trace_path: str | Path | None = None,
    ) -> None:
        if max_steps < 1 or max_steps > 32:
            raise ValueError("max_steps must be between 1 and 32.")
        self.provider = provider
        self.tools = tools
        self.max_steps = max_steps
        self.trace_path = Path(trace_path) if trace_path else None

    def _trace(self, event: dict[str, Any]) -> None:
        if not self.trace_path:
            return
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        with self.trace_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"timestamp": time.time(), **event}) + "\n")

    @staticmethod
    def _validated_call(call: dict[str, Any]) -> tuple[str, str, str]:
        call_id = call.get("id")
        function = call.get("function")
        if not isinstance(call_id, str) or not call_id or len(call_id) > 128:
            raise RuntimeError("Model returned a tool call with an invalid ID.")
        if not isinstance(function, dict):
            raise RuntimeError("Model returned a malformed tool call.")
        name = function.get("name")
        arguments = function.get("arguments", "{}")
        if not isinstance(name, str) or not name or len(name) > 128:
            raise RuntimeError("Model returned a tool call with an invalid name.")
        if not isinstance(arguments, str):
            raise RuntimeError(f"Tool arguments for {name} must be a JSON string.")
        if len(arguments.encode("utf-8")) > MAX_TOOL_ARGUMENT_BYTES:
            raise RuntimeError(f"Tool arguments for {name} exceed the 64 KiB limit.")
        return call_id, name, arguments

    def run(self, prompt: str, system_prompt: str | None = None) -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Prompt cannot be empty.")
        run_id = uuid.uuid4().hex
        messages = [
            {
                "role": "system",
                "content": system_prompt
                or (
                    "You are PixelForge, an expert 2D game development agent. Use project tools "
                    "to inspect and modify files. Be honest about what you have tested. Never claim "
                    "a build or runtime test passed unless a verification tool actually ran it."
                ),
            },
            {"role": "user", "content": prompt},
        ]
        total_tool_calls = 0
        total_result_bytes = 0

        for step in range(1, self.max_steps + 1):
            reply = self.provider.complete(messages, self.tools.schemas())
            if not isinstance(reply, ModelReply):
                raise RuntimeError("Provider returned an invalid response object.")
            if not isinstance(reply.content, str) or not isinstance(reply.tool_calls, list):
                raise RuntimeError("Provider returned malformed message content or tool calls.")
            self._trace(
                {
                    "run_id": run_id,
                    "step": step,
                    "event": "model_response",
                    "tool_call_count": len(reply.tool_calls),
                }
            )
            if not reply.tool_calls:
                if not reply.content.strip():
                    raise RuntimeError("Model returned neither a final answer nor a tool call.")
                return reply.content
            if len(reply.tool_calls) > MAX_TOOL_CALLS_PER_STEP:
                raise RuntimeError(
                    f"Model requested {len(reply.tool_calls)} tools in one step; "
                    f"limit is {MAX_TOOL_CALLS_PER_STEP}."
                )
            if total_tool_calls + len(reply.tool_calls) > MAX_TOOL_CALLS_PER_RUN:
                raise RuntimeError(
                    f"Agent reached the total tool-call limit of {MAX_TOOL_CALLS_PER_RUN}."
                )

            validated = [self._validated_call(call) for call in reply.tool_calls]
            call_ids = [call_id for call_id, _, _ in validated]
            if len(set(call_ids)) != len(call_ids):
                raise RuntimeError("Model returned duplicate tool-call IDs.")

            messages.append(
                {
                    "role": "assistant",
                    "content": reply.content or None,
                    "tool_calls": reply.tool_calls,
                }
            )
            for call_id, name, arguments in validated:
                result = self.tools.execute(name, arguments)
                encoded_result = json.dumps(result, ensure_ascii=False)
                result_size = len(encoded_result.encode("utf-8"))
                remaining = MAX_TOTAL_RESULT_BYTES - total_result_bytes
                if result_size > MAX_TOOL_RESULT_BYTES or result_size > remaining:
                    result = {
                        "ok": False,
                        "error": "Tool result omitted because the run output budget was exceeded.",
                    }
                    encoded_result = json.dumps(result)
                    result_size = len(encoded_result)
                total_result_bytes += result_size
                total_tool_calls += 1
                self._trace(
                    {
                        "run_id": run_id,
                        "step": step,
                        "event": "tool_result",
                        "tool": name,
                        "ok": result.get("ok", False),
                    }
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": name,
                        "content": encoded_result,
                    }
                )

        raise RuntimeError(f"Agent reached the configured limit of {self.max_steps} steps.")
