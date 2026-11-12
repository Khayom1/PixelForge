"""OpenAI-compatible Chat Completions provider for cloud or local servers."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

MAX_RESPONSE_BYTES = 5 * 1024 * 1024


class ProviderError(RuntimeError):
    """Provider transport or response error."""


@dataclass(frozen=True, slots=True)
class ModelReply:
    content: str
    tool_calls: list[dict[str, Any]]


class OpenAICompatibleProvider:
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ModelReply:
        if not self.model.strip():
            raise ProviderError("A model name is required.")
        payload: dict[str, Any] = {"model": self.model, "messages": messages}
        if tools:
            payload.update({"tools": tools, "tool_choice": "auto"})
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise ProviderError("Provider response exceeded the 5 MiB safety limit.")
            data = json.loads(body.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            # Error bodies can echo request data; expose only the status, never the body.
            raise ProviderError(f"Provider returned HTTP {exc.code} ({exc.reason}).") from exc
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise ProviderError(f"Provider request failed: {exc.__class__.__name__}.") from exc

        try:
            message = data["choices"][0]["message"]
            if not isinstance(message, dict):
                raise TypeError("message must be an object")
            content = message.get("content") or ""
            tool_calls = message.get("tool_calls") or []
            if not isinstance(content, str):
                raise TypeError("message content must be text")
            if not isinstance(tool_calls, list) or any(
                not isinstance(call, dict) for call in tool_calls
            ):
                raise TypeError("tool_calls must be a list of objects")
            return ModelReply(content, tool_calls)
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("Invalid Chat Completions response.") from exc
