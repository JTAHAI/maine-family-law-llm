from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from legal.agent_runtime.providers import (
    LocalModelError,
    SentinelOllamaLocalClient,
    build_local_client,
)
from legal.agent_runtime.runtime import LocalAgentRuntime
from maine_family_law_llm import api


class _SentinelHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler contract
        size = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(size).decode("utf-8"))
        self.server.requests.append((self.path, payload))  # type: ignore[attr-defined]
        if payload["model"] == "qwen3:14b":
            self.send_error(503)
            return
        body = json.dumps(
            {
                "model": payload["model"],
                "message": {"role": "assistant", "content": "Source review [1]. Review required."},
                "done_reason": "stop",
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return


@pytest.fixture()
def sentinel_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _SentinelHandler)
    server.requests = []  # type: ignore[attr-defined]
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def _environment(server) -> dict[str, str]:
    return {
        "AI_PROVIDER_ADAPTER": "sentinel_ollama",
        "SENTINEL_MODEL_GATEWAY_URL": f"http://127.0.0.1:{server.server_port}/api/chat",
        "SENTINEL_LAW_PRIMARY_MODEL": "qwen3:14b",
        "SENTINEL_LAW_FALLBACK_MODEL": "qwen3:8b",
        "AI_MODEL_ALLOWLIST": "qwen3:14b,qwen3:8b",
    }


def test_sentinel_is_host_configured_loopback_only_and_falls_back_after_primary_failure(sentinel_server):
    client = SentinelOllamaLocalClient(environment=_environment(sentinel_server), timeout_seconds=5)

    result = client.generate_response("Use only approved source [1].")

    assert result.provider_id == "sentinel_ollama"
    assert result.model_id == "qwen3:8b"
    assert result.usage["fallback_used"] is True
    assert [row[0] for row in sentinel_server.requests] == ["/api/chat", "/api/chat"]
    assert [row[1]["model"] for row in sentinel_server.requests] == ["qwen3:14b", "qwen3:8b"]
    assert all(row[1]["stream"] is False for row in sentinel_server.requests)
    assert "source-bound review assistant" in sentinel_server.requests[-1][1]["messages"][0]["content"]


def test_sentinel_requires_explicit_host_enablement_and_allowlist(sentinel_server):
    environment = _environment(sentinel_server)
    environment.pop("AI_PROVIDER_ADAPTER")
    with pytest.raises(LocalModelError) as disabled:
        SentinelOllamaLocalClient(environment=environment)
    assert disabled.value.code == "sentinel_ollama_not_enabled"

    environment = _environment(sentinel_server)
    environment["AI_MODEL_ALLOWLIST"] = "qwen3:14b"
    with pytest.raises(LocalModelError) as allowlist:
        SentinelOllamaLocalClient(environment=environment)
    assert allowlist.value.code == "sentinel_ollama_model_not_allowlisted"


def test_sentinel_rejects_non_loopback_gateway_and_ignores_browser_model_arguments(monkeypatch, sentinel_server):
    environment = _environment(sentinel_server)
    environment["SENTINEL_MODEL_GATEWAY_URL"] = "https://example.invalid/api/chat"
    with pytest.raises(ValueError, match="loopback"):
        SentinelOllamaLocalClient(environment=environment)

    for key, value in _environment(sentinel_server).items():
        monkeypatch.setenv(key, value)
    client = build_local_client(
        provider="sentinel_ollama",
        endpoint="https://example.invalid/overridden",
        model_name="untrusted-browser-model",
    )
    assert client.model_name == "qwen3:14b"
    assert client.endpoint.host == "127.0.0.1"


@pytest.mark.parametrize(
    ("payload", "expected_code"),
    [
        ({"model": "qwen3:8b", "message": {"role": "assistant", "content": "x"}}, "sentinel_ollama_runtime_identity_mismatch"),
        ({"model": "qwen3:14b", "done": False, "message": {"role": "assistant", "content": "x"}}, "sentinel_ollama_completion_incomplete"),
        ({"model": "qwen3:14b", "message": {"role": "assistant", "content": None}}, "local_model_invalid_payload"),
        ({"model": "qwen3:14b", "message": {"role": "assistant", "content": "x", "tool_calls": [{}]}}, "sentinel_ollama_tool_output_forbidden"),
    ],
)
def test_sentinel_rejects_invalid_response_before_any_fallback(sentinel_server, monkeypatch, payload, expected_code):
    client = SentinelOllamaLocalClient(environment=_environment(sentinel_server), timeout_seconds=5)
    monkeypatch.setattr(client._http, "post_json", lambda *_args, **_kwargs: payload)

    with pytest.raises(LocalModelError) as error:
        client.generate_response("Use only approved source [1].")

    assert error.value.code == expected_code


def test_sentinel_fallback_is_limited_to_availability_failures(sentinel_server, monkeypatch):
    client = SentinelOllamaLocalClient(environment=_environment(sentinel_server), timeout_seconds=5)
    calls: list[str] = []

    def invalid_output(_prompt: str, model: str):
        calls.append(model)
        raise LocalModelError("local_model_invalid_payload", "invalid")

    monkeypatch.setattr(client, "_request_model", invalid_output)
    with pytest.raises(LocalModelError) as error:
        client.generate_response("Use only approved source [1].")

    assert error.value.code == "local_model_invalid_payload"
    assert calls == ["qwen3:14b"]


def test_sentinel_route_cannot_run_without_a_verified_artifact_resource_and_task_profile():
    class SentinelClient:
        provider_id = "sentinel_ollama"

    readiness = api._local_agent_hardware_readiness(LocalAgentRuntime(SentinelClient()))

    assert readiness["status"] == "blocked_unqualified_sentinel_profile"
    assert "sentinel_artifact_not_admitted" in readiness["blockers"]
    assert readiness["network_used"] is False
