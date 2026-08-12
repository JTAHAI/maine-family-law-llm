"""Bounded, loopback-only local model provider adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .endpoint import LoopbackEndpoint, LoopbackEndpointPolicy

MAX_PROMPT_CHARS = 100_000
MAX_REQUEST_BYTES = 2 * 1024 * 1024
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_MODEL_NAME_CHARS = 200


class LocalModelError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class LocalModelResponse:
    text: str
    provider_id: str
    model_id: str
    endpoint_class: str
    usage: dict[str, Any] = field(default_factory=dict)
    finish_reason: str | None = None


class LocalGenerationClient:
    provider_id: str
    model_name: str
    endpoint: LoopbackEndpoint

    def generate_response(self, prompt: str) -> LocalModelResponse:
        raise NotImplementedError

    def generate(self, prompt: str) -> str:
        return self.generate_response(prompt).text


class _BoundedHttpClient:
    def __init__(
        self,
        endpoint: str,
        *,
        timeout_seconds: int,
        max_response_bytes: int = MAX_RESPONSE_BYTES,
        opener: Callable[..., Any] = urlopen,
    ):
        self.endpoint = LoopbackEndpointPolicy().validate(endpoint)
        self.timeout_seconds = max(1, min(int(timeout_seconds), 600))
        self.max_response_bytes = max(1024, min(int(max_response_bytes), MAX_RESPONSE_BYTES))
        self.opener = opener

    def post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(data) > MAX_REQUEST_BYTES:
            raise LocalModelError("local_model_request_too_large", "The local model request exceeded its size limit.")
        request = Request(
            self.endpoint.url(path),
            data=data,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "MaineFamilyLawLLM-LocalAgent/1",
            },
            method="POST",
        )
        try:
            with self.opener(request, timeout=self.timeout_seconds) as response:
                declared = response.headers.get("Content-Length") if getattr(response, "headers", None) else None
                if declared:
                    try:
                        declared_size = int(declared)
                    except ValueError:
                        declared_size = 0
                    if declared_size > self.max_response_bytes:
                        raise LocalModelError("local_model_response_too_large", "The local model response exceeded its size limit.")
                raw = response.read(self.max_response_bytes + 1)
        except LocalModelError:
            raise
        except HTTPError as exc:
            raise LocalModelError("local_model_http_error", f"Local model returned HTTP {exc.code}.") from exc
        except URLError as exc:
            raise LocalModelError("local_model_unavailable", "The loopback local model server is unavailable.") from exc
        except TimeoutError as exc:
            raise LocalModelError("local_model_timeout", "The loopback local model request timed out.") from exc
        if len(raw) > self.max_response_bytes:
            raise LocalModelError("local_model_response_too_large", "The local model response exceeded its size limit.")
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LocalModelError("local_model_invalid_json", "The local model returned invalid JSON.") from exc
        if not isinstance(decoded, dict):
            raise LocalModelError("local_model_invalid_payload", "The local model returned an unsupported response shape.")
        return decoded


def _validate_prompt_model(prompt: str, model_name: str) -> tuple[str, str]:
    clean_prompt = str(prompt or "").replace("\x00", "")
    if not clean_prompt.strip():
        raise LocalModelError("local_model_prompt_required", "A prompt is required.")
    if len(clean_prompt) > MAX_PROMPT_CHARS:
        raise LocalModelError("local_model_prompt_too_large", "The local model prompt exceeded its size limit.")
    clean_model = " ".join(str(model_name or "").replace("\x00", " ").split())
    if not clean_model or len(clean_model) > MAX_MODEL_NAME_CHARS:
        raise LocalModelError("local_model_name_invalid", "The local model name is invalid.")
    return clean_prompt, clean_model


class OllamaLocalClient(LocalGenerationClient):
    provider_id = "ollama"

    def __init__(
        self,
        *,
        model_name: str = "qwen2.5:7b",
        endpoint: str = "http://127.0.0.1:11434",
        timeout_seconds: int = 120,
        max_response_bytes: int = MAX_RESPONSE_BYTES,
        opener: Callable[..., Any] = urlopen,
    ):
        self.model_name = model_name
        self._http = _BoundedHttpClient(
            endpoint,
            timeout_seconds=timeout_seconds,
            max_response_bytes=max_response_bytes,
            opener=opener,
        )
        self.endpoint = self._http.endpoint

    def generate_response(self, prompt: str) -> LocalModelResponse:
        prompt, model = _validate_prompt_model(prompt, self.model_name)
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1, "top_p": 0.9, "num_predict": 2048},
        }
        body = self._http.post_json("/api/generate", payload)
        text = str(body.get("response") or "").strip()
        if not text:
            raise LocalModelError("local_model_empty_response", "The local model returned no text.")
        usage = {
            key: body.get(key)
            for key in ("prompt_eval_count", "eval_count", "total_duration", "load_duration")
            if body.get(key) is not None
        }
        return LocalModelResponse(
            text=text,
            provider_id=self.provider_id,
            model_id=str(body.get("model") or model),
            endpoint_class=self.endpoint.endpoint_class,
            usage=usage,
            finish_reason=str(body.get("done_reason") or "stop"),
        )


class OpenAICompatibleLocalClient(LocalGenerationClient):
    provider_id = "openai_compatible_local"

    def __init__(
        self,
        *,
        model_name: str,
        endpoint: str = "http://127.0.0.1:1234",
        timeout_seconds: int = 120,
        max_response_bytes: int = MAX_RESPONSE_BYTES,
        opener: Callable[..., Any] = urlopen,
    ):
        self.model_name = model_name
        self._http = _BoundedHttpClient(
            endpoint,
            timeout_seconds=timeout_seconds,
            max_response_bytes=max_response_bytes,
            opener=opener,
        )
        self.endpoint = self._http.endpoint

    def generate_response(self, prompt: str) -> LocalModelResponse:
        prompt, model = _validate_prompt_model(prompt, self.model_name)
        body = self._http.post_json(
            "/v1/chat/completions",
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "top_p": 0.9,
                "max_tokens": 2048,
                "stream": False,
            },
        )
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise LocalModelError("local_model_invalid_payload", "The local model returned no choices.")
        first = choices[0]
        message = first.get("message")
        if not isinstance(message, dict):
            raise LocalModelError("local_model_invalid_payload", "The local model returned no message.")
        text = str(message.get("content") or "").strip()
        if not text:
            raise LocalModelError("local_model_empty_response", "The local model returned no text.")
        return LocalModelResponse(
            text=text,
            provider_id=self.provider_id,
            model_id=str(body.get("model") or model),
            endpoint_class=self.endpoint.endpoint_class,
            usage=dict(body.get("usage") or {}),
            finish_reason=str(first.get("finish_reason") or "stop"),
        )


def build_local_client(*, provider: str, endpoint: str, model_name: str, timeout_seconds: int = 120) -> LocalGenerationClient:
    provider_key = str(provider or "").strip().lower().replace("-", "_")
    if provider_key == "ollama":
        return OllamaLocalClient(model_name=model_name, endpoint=endpoint, timeout_seconds=timeout_seconds)
    if provider_key in {"openai_compatible", "openai_compatible_local", "lm_studio", "llama_cpp"}:
        return OpenAICompatibleLocalClient(model_name=model_name, endpoint=endpoint, timeout_seconds=timeout_seconds)
    raise ValueError("unsupported_local_model_provider")
