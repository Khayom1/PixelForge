"""Bounded model/tool loop with compact JSONL tracing."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Protocol

from pixelforge.provider import ModelReply
from pixelforge.tools import ToolRegistry


class Provider(Protocol):
    def complete(self, messages: list[dict[str, Any]],
                 tools: list[dict[str, Any]]) -> ModelReply: ...


class AgentRuntime:
    def __init__(self, provider: Provider, tools: ToolRegistry, max_steps: int = 8,
                 trace_path: str | Path | None = None) -> None:
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

    def run(self, prompt: str, system_prompt: str | None = None) -> str:
        if not prompt.strip():
            raise ValueError("Prompt cannot be empty.")
        run_id = uuid.uuid4().hex
        messages = [
            {"role": "system", "content": system_prompt or (
                "You are PixelForge, an expert 2D game development agent. Use project tools "
                "to inspect and modify files. Be honest about what you have tested. Never claim "
                "a build or runtime test passed unless a verification tool actually ran it."
            )},
            {"role": "user", "content": prompt},
        ]
        for step in range(1, self.max_steps + 1):
            reply = self.provider.complete(messages, self.tools.schemas())
            self._trace({"run_id": run_id, "step": step, "event": "model_response",
                         "tool_call_count": len(reply.tool_calls)})
            if not reply.tool_calls:
                return reply.content
            messages.append({"role": "assistant", "content": reply.content or None,
                             "tool_calls": reply.tool_calls})
            for call in reply.tool_calls:
                function = call.get("function") or {}
                name = function.get("name", "")
                result = self.tools.execute(name, function.get("arguments", "{}"))
                self._trace({"run_id": run_id, "step": step, "event": "tool_result",
                             "tool": name, "ok": result.get("ok", False)})
                messages.append({"role": "tool", "tool_call_id": call.get("id", ""),
                                 "name": name, "content": json.dumps(result)})
        raise RuntimeError(f"Agent reached the configured limit of {self.max_steps} steps.")
