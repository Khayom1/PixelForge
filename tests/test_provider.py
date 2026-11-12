import json
import urllib.error

import pytest

from pixelforge.provider import (
    MAX_RESPONSE_BYTES,
    OpenAICompatibleProvider,
    ProviderError,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit=-1):
        return self.payload if limit < 0 else self.payload[:limit]


def test_provider_sends_model_messages_tools_and_bearer_key(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["authorization"] = request.get_header("Authorization")
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data)
        return FakeResponse(json.dumps({"choices": [{"message": {
            "content": "Ready", "tool_calls": []
        }}]}).encode())

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = OpenAICompatibleProvider(
        "http://localhost:8080/v1/", "local-model", "secret-token", 12
    )
    result = provider.complete([{"role": "user", "content": "hello"}], [])
    assert result.content == "Ready"
    assert captured["url"] == "http://localhost:8080/v1/chat/completions"
    assert captured["authorization"] == "Bearer secret-token"
    assert captured["payload"]["model"] == "local-model"
    assert captured["timeout"] == 12


def test_provider_parses_tool_calls(monkeypatch) -> None:
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: FakeResponse(
        json.dumps({"choices": [{"message": {"content": None, "tool_calls": [
            {"id": "call-1", "type": "function",
             "function": {"name": "list_project_files", "arguments": "{}"}}
        ]}}]}).encode()
    ))
    result = OpenAICompatibleProvider("http://localhost/v1", "test").complete([], [])
    assert result.content == ""
    assert result.tool_calls[0]["function"]["name"] == "list_project_files"


def test_provider_surfaces_http_errors_without_response_body(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise urllib.error.HTTPError(
            "http://localhost", 401, "unauthorized", {},
            __import__("io").BytesIO(b'{"error":"bad key"}'),
        )

    monkeypatch.setattr("urllib.request.urlopen", fail)
    provider = OpenAICompatibleProvider("http://localhost/v1", "test")
    with pytest.raises(ProviderError, match="HTTP 401") as caught:
        provider.complete([], [])
    assert "bad key" not in str(caught.value)


def test_provider_rejects_oversized_response(monkeypatch) -> None:
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *args, **kwargs: FakeResponse(b" " * (MAX_RESPONSE_BYTES + 1)),
    )
    provider = OpenAICompatibleProvider("http://localhost/v1", "test")
    with pytest.raises(ProviderError, match="5 MiB"):
        provider.complete([], [])


def test_provider_rejects_invalid_tool_call_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *args, **kwargs: FakeResponse(json.dumps({
            "choices": [{"message": {"content": "", "tool_calls": "not-a-list"}}]
        }).encode()),
    )
    provider = OpenAICompatibleProvider("http://localhost/v1", "test")
    with pytest.raises(ProviderError, match="Invalid"):
        provider.complete([], [])
