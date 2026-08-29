from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Any

import pytest

from legal.agent_runtime.providers import (
    FastInterchangeLocalClient,
    LocalModelError,
    OllamaLocalClient,
    OpenAICompatibleLocalClient,
)


class _LocalModelHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler contract
        content_length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
        self.server.seen_requests.append((self.path, payload))  # type: ignore[attr-defined]
        self.server.seen_authorizations.append(self.headers.get("Authorization"))  # type: ignore[attr-defined]

        if self.path == "/v1/requests/prepare":
            body = {"request_id": payload["request_id"], "status": "reserved"}
        elif self.path == "/api/generate":
            body: dict[str, Any] = {
                "model": payload["model"],
                "response": "Ollama loopback answer [1]. Review required.",
                "done_reason": "stop",
                "prompt_eval_count": 24,
                "eval_count": 10,
            }
        elif self.path == "/v1/chat/completions":
            body = {
                "model": payload["model"],
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "OpenAI-compatible loopback answer [1]. Review required.",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 18, "completion_tokens": 9},
            }
            if "request_id" in payload:
                body.update({key: payload[key] for key in ("request_id", "capability", "release_fingerprint")})
                body["review_required"] = True
        elif self.path == "/oversized":
            raw = b"x" * 4096
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        else:
            self.send_error(404)
            return

        raw = json.dumps(body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


@pytest.fixture()
def local_model_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _LocalModelHandler)
    server.seen_requests = []  # type: ignore[attr-defined]
    server.seen_authorizations = []  # type: ignore[attr-defined]
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_ollama_adapter_round_trips_only_over_literal_loopback(local_model_server):
    endpoint = f"http://127.0.0.1:{local_model_server.server_port}"
    client = OllamaLocalClient(model_name="test-ollama", endpoint=endpoint, timeout_seconds=5)
    result = client.generate_response("Use only the approved context.")

    assert result.provider_id == "ollama"
    assert result.model_id == "test-ollama"
    assert result.endpoint_class == "loopback_http"
    assert result.usage["prompt_eval_count"] == 24
    path, payload = local_model_server.seen_requests[-1]
    assert path == "/api/generate"
    assert payload["stream"] is False


def test_openai_compatible_adapter_round_trips_only_over_literal_loopback(local_model_server):
    endpoint = f"http://127.0.0.1:{local_model_server.server_port}"
    client = OpenAICompatibleLocalClient(
        model_name="test-openai-local",
        endpoint=endpoint,
        timeout_seconds=5,
    )
    result = client.generate_response("Use only the approved context.")

    assert result.provider_id == "openai_compatible_local"
    assert result.model_id == "test-openai-local"
    assert result.endpoint_class == "loopback_http"
    assert result.usage["completion_tokens"] == 9
    path, payload = local_model_server.seen_requests[-1]
    assert path == "/v1/chat/completions"
    assert payload["stream"] is False


def test_adapter_rejects_declared_oversized_response_before_read(local_model_server):
    endpoint = f"http://127.0.0.1:{local_model_server.server_port}"
    client = OllamaLocalClient(
        model_name="test-ollama",
        endpoint=endpoint,
        timeout_seconds=5,
        max_response_bytes=1024,
    )
    with pytest.raises(LocalModelError, match="exceeded its size limit") as exc_info:
        client._http.post_json("/oversized", {"model": "test"})
    assert exc_info.value.code == "local_model_response_too_large"


def test_fast_interchange_adapter_uses_the_closed_authenticated_worker_contract(local_model_server, tmp_path):
    from test_fast_interchange_worker import _registry
    endpoint = f"http://127.0.0.1:{local_model_server.server_port}"
    client = FastInterchangeLocalClient(
        model_name="family-evidence-small-r1",
        endpoint=endpoint,
        timeout_seconds=5,
        worker_token="w" * 40,
        registry=_registry(tmp_path), capability="evidence_review", allow_test_only=True,
    )

    result = client.generate_response("Use only the approved source context.")

    assert result.provider_id == "fast_interchange_local"
    assert result.model_id == "family-evidence-small-r1"
    assert result.finish_reason == "stop"
    path, payload = local_model_server.seen_requests[-1]
    assert path == "/v1/chat/completions"
    assert payload == {
        "model": "family-evidence-small-r1",
        "messages": [{"role": "user", "content": "Use only the approved source context."}],
        "temperature": 0,
        "top_p": 1,
        "max_tokens": 1024,
        "stream": False,
        "request_id": client.request_id,
        "capability": "evidence_review",
        "release_fingerprint": "a" * 64,
    }
    assert local_model_server.seen_authorizations[-1] == "Bearer " + "w" * 40
    assert not client.supports_explicit_release


def test_fast_interchange_adapter_refuses_missing_secret_and_invalid_release_model_id(monkeypatch):
    monkeypatch.delenv("MAINE_FAST_INTERCHANGE_WORKER_TOKEN", raising=False)
    with pytest.raises(LocalModelError, match="token is not configured") as secret_error:
        FastInterchangeLocalClient(model_name="family-evidence-small-r1")
    assert secret_error.value.code == "fast_interchange_worker_token_required"
    with pytest.raises(LocalModelError, match="release-model ID is invalid"):
        FastInterchangeLocalClient(model_name="../unsafe", worker_token="w" * 40)
