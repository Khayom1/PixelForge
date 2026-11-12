"""OpenAI-compatible Chat Completions provider for cloud or local servers."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class ProviderError(RuntimeError):
    """Provider transport or response error."""


@dataclass(frozen=True, slots=True)
class ModelReply:
    content: str
    tool_calls: list[dict[str, Any]]


class OpenAICompatibleProvider:
    def __init__(self, base_url: str, model: str, api_key: str | None = None,
                 timeout_seconds: float = 60.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def complete(self, messages: list[dict[str, Any]],
                 tools: list[dict[str, Any]]) -> ModelReply:
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
            data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read(2048).decode("utf-8", errors="replace")
            raise ProviderError(f"Provider returned HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ProviderError(f"Provider request failed: {exc}") from exc
        try:
            message = data["choices"][0]["message"]
            return ModelReply(message.get("content") or "", message.get("tool_calls") or [])
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("Invalid Chat Completions response.") from exc
