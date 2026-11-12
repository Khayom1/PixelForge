import io
import json
import urllib.error

import pytest

from pixelforge.provider import OpenAICompatibleProvider, ProviderError


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload


def test_provider_sends_model_messages_tools_and_bearer_key(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["authorization"] = request.get_header("Authorization")
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data)
        return FakeResponse({"choices": [{"message": {
            "content": "Ready", "tool_calls": []
        }}]})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = OpenAICompatibleProvider("http://localhost:8080/v1/", "local-model",
                                        "secret-token", 12)
    result = provider.complete([{"role": "user", "content": "hello"}], [])
    assert result.content == "Ready"
    assert captured["url"] == "http://localhost:8080/v1/chat/completions"
    assert captured["authorization"] == "Bearer secret-token"
    assert captured["payload"]["model"] == "local-model"
    assert captured["timeout"] == 12


def test_provider_parses_tool_calls(monkeypatch) -> None:
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: FakeResponse({
        "choices": [{"message": {"content": None, "tool_calls": [
            {"id": "call-1", "type": "function",
             "function": {"name": "list_project_files", "arguments": "{}"}}
        ]}}]
    }))
    result = OpenAICompatibleProvider("http://localhost/v1", "test").complete([], [])
    assert result.content == ""
    assert result.tool_calls[0]["function"]["name"] == "list_project_files"


def test_provider_surfaces_http_errors_without_crashing(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise urllib.error.HTTPError("http://localhost", 401, "unauthorized", {},
                                     io.BytesIO(b'{"error":"bad key"}'))

    monkeypatch.setattr("urllib.request.urlopen", fail)
    provider = OpenAICompatibleProvider("http://localhost/v1", "test")
    with pytest.raises(ProviderError, match="HTTP 401"):
        provider.complete([], [])
