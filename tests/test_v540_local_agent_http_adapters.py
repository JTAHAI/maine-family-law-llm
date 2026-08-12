from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Any

import pytest

from legal.agent_runtime.providers import (
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

        if self.path == "/api/generate":
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
