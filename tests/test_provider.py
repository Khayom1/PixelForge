import json
import urllib.error
import urllib.request

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
        captured["authorization"] = dict(request.header_items()).get("Authorization")
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


@pytest.mark.parametrize(
    "base_url",
    [
        "http://api.example.com/v1",
        "http://192.0.2.10:8080/v1",
        "http://localhost.example/v1",
    ],
)
def test_provider_rejects_api_keys_over_remote_http(base_url) -> None:
    with pytest.raises(ValueError, match="require HTTPS"):
        OpenAICompatibleProvider(base_url, "test", "secret-token")


@pytest.mark.parametrize(
    "base_url",
    [
        "http://localhost:11434/v1",
        "http://localhost.:11434/v1",
        "http://127.0.0.1:11434/v1",
        "http://127.0.0.2:11434/v1",
        "http://[::1]:11434/v1",
    ],
)
def test_provider_allows_api_keys_over_loopback_http(base_url) -> None:
    provider = OpenAICompatibleProvider(base_url, "local-model", "local-token")
    assert provider.api_key == "local-token"


def test_provider_allows_api_keys_over_remote_https() -> None:
    provider = OpenAICompatibleProvider(
        "https://api.example.com/v1", "cloud-model", "secret-token"
    )
    assert provider.api_key == "secret-token"


def test_provider_allows_remote_http_without_api_key() -> None:
    provider = OpenAICompatibleProvider("http://api.example.com/v1", "test")
    assert provider.api_key is None


def test_provider_does_not_forward_api_key_to_redirect_target() -> None:
    request = urllib.request.Request(
        "https://api.example.com/v1/chat/completions",
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    request.add_unredirected_header("Authorization", "Bearer secret-token")

    redirected = urllib.request.HTTPRedirectHandler().redirect_request(
        request,
        None,
        302,
        "Found",
        {},
        "https://attacker.example/collect",
    )

    assert redirected is not None
    assert "Authorization" not in dict(redirected.header_items())


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
