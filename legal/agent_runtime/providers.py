"""Bounded, loopback-only local model provider adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
import re
import uuid
from threading import Event, RLock
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener, urlopen

from .endpoint import LoopbackEndpoint, LoopbackEndpointPolicy

MAX_PROMPT_CHARS = 100_000
MAX_REQUEST_BYTES = 2 * 1024 * 1024
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_MODEL_NAME_CHARS = 200
_FAST_INTERCHANGE_MODEL_ID = re.compile(r"[a-z][a-z0-9_-]{2,79}\Z")


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

    @property
    def supports_explicit_release(self) -> bool:
        """Whether this provider can explicitly release a warmed model.

        A warm-pool manager must never assume that a generic OpenAI-compatible
        endpoint can unload a resident model.  Providers opt in only when they
        implement an explicit, bounded release operation.
        """

        return False

    def warm(self) -> LocalModelResponse:
        """Run a synthetic, non-matter prompt to initialize a local worker."""

        return self.generate_response("Reply with READY only. This is a local runtime warm-up check.")

    def release(self) -> None:
        raise LocalModelError(
            "local_model_release_unsupported",
            "This local model provider cannot explicitly release a warmed model.",
        )


class _BoundedHttpClient:
    def __init__(
        self,
        endpoint: str,
        *,
        timeout_seconds: int,
        max_response_bytes: int = MAX_RESPONSE_BYTES,
        opener: Callable[..., Any] = urlopen,
        extra_headers: dict[str, str] | None = None,
    ):
        self.endpoint = LoopbackEndpointPolicy().validate(endpoint)
        self.timeout_seconds = max(1, min(int(timeout_seconds), 600))
        self.max_response_bytes = max(1024, min(int(max_response_bytes), MAX_RESPONSE_BYTES))
        self.opener = opener
        self.extra_headers = dict(extra_headers or {})

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
                **self.extra_headers,
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
            if path.startswith("/v1/requests/") or self.extra_headers.get("User-Agent") == "MFL-FI/2":
                try:
                    from legal.security.strict_json import strict_json_loads
                    failure = strict_json_loads(exc.read(4097), max_bytes=4096, require_object=True)
                    code = failure.get("error", {}).get("code", "")
                    if isinstance(code, str) and re.fullmatch(r"fast_interchange_[a-z_]{1,90}", code):
                        raise LocalModelError(code, "The local worker refused or stopped this request.") from exc
                except (ValueError, TypeError, AttributeError):
                    pass
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

    @property
    def supports_explicit_release(self) -> bool:
        return True

    def release(self) -> None:
        """Ask Ollama to unload the model without exposing a remote endpoint."""

        self._http.post_json(
            "/api/generate",
            {"model": self.model_name, "keep_alive": 0, "stream": False},
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


class FastInterchangeLocalClient(LocalGenerationClient):
    """Strict connector for an externally operated FAST INTERCHANGE worker.

    The worker remains a separately installed local service.  The application
    never starts it, discovers it, downloads a model, or accepts an adapter or
    artifact path from the desktop UI.  Its bearer token comes only from the
    host process environment and is deliberately excluded from receipts.
    """

    provider_id = "fast_interchange_local"

    def __init__(
        self,
        *,
        model_name: str,
        endpoint: str = "http://127.0.0.1:8105",
        timeout_seconds: int = 120,
        worker_token: str | None = None,
        max_response_bytes: int = MAX_RESPONSE_BYTES,
        opener: Callable[..., Any] = urlopen,
        registry: Any = None,
        capability: str | None = None,
        allow_test_only: bool = False,
    ):
        clean_model = " ".join(str(model_name or "").replace("\x00", " ").split()).casefold()
        if not _FAST_INTERCHANGE_MODEL_ID.fullmatch(clean_model):
            raise LocalModelError(
                "fast_interchange_model_id_invalid",
                "The FAST INTERCHANGE release-model ID is invalid.",
            )
        token = str(worker_token if worker_token is not None else os.environ.get("MAINE_FAST_INTERCHANGE_WORKER_TOKEN", ""))
        if not 32 <= len(token) <= 256 or not token.isascii() or any(c.isspace() for c in token):
            raise LocalModelError(
                "fast_interchange_worker_token_required",
                "The FAST INTERCHANGE worker token is not configured for this local app process.",
            )
        self.model_name = clean_model
        from legal.fast_interchange.host import load_operator_registry, release_identity
        from legal.fast_interchange.worker import FastInterchangeError
        self._allow_test_only = allow_test_only
        try:
            self._registry = registry if registry is not None else load_operator_registry()
            self._release = self._registry.select(clean_model, allow_test_only=allow_test_only)
            if capability is not None and capability != self._release.capability:
                raise FastInterchangeError("fast_interchange_capability_mismatch")
            self.model_binding = release_identity(self._registry, self._release, allow_test_only=allow_test_only)
        except (FastInterchangeError, ValueError, OSError) as exc:
            raise LocalModelError(getattr(exc, "code", "fast_interchange_admission_unavailable"),
                                  "The selected capability needs a current, trusted model admission.") from exc
        self.request_id = uuid.uuid4().hex
        self._cancel = Event()
        self._lock = RLock()
        self._prepared = False
        self._used = False
        if opener is urlopen:
            class NoRedirect(HTTPRedirectHandler):
                def redirect_request(self, req, fp, code, msg, headers, newurl):
                    raise LocalModelError("fast_interchange_redirect_forbidden", "Local worker redirects are forbidden.")
            # Ignore ambient proxy settings; worker traffic stays on loopback.
            opener = build_opener(ProxyHandler({}), NoRedirect()).open
        self._http = _BoundedHttpClient(
            endpoint,
            timeout_seconds=timeout_seconds,
            max_response_bytes=max_response_bytes,
            opener=opener,
            extra_headers={"Authorization": f"Bearer {token}", "User-Agent": "MFL-FI/2"},
        )
        self._control = _BoundedHttpClient(endpoint, timeout_seconds=5, max_response_bytes=4096,
                                          opener=opener, extra_headers=self._http.extra_headers)
        self.endpoint = self._http.endpoint

    def cancel(self) -> dict[str, Any]:
        self._cancel.set()
        with self._lock:
            prepared = self._prepared
        if not prepared:
            return {"status": "canceling" if self._used else "canceled", "review_required": True}
        return self._control.post_json("/v1/requests/cancel", {"request_id": self.request_id})

    def _check_admission(self) -> None:
        from legal.fast_interchange.host import release_identity
        from legal.fast_interchange.worker import FastInterchangeError
        try:
            current = release_identity(self._registry, self._release, allow_test_only=self._allow_test_only)
            if current != self.model_binding:
                raise ValueError("changed admission")
        except (FastInterchangeError, ValueError, OSError) as exc:
            raise LocalModelError("fast_interchange_admission_changed", "Model admission changed; output withheld.") from exc

    def _check_canceled(self) -> None:
        if self._cancel.is_set():
            raise LocalModelError("fast_interchange_generation_canceled", "Generation canceled; no new answer was accepted.")

    def generate_response(self, prompt: str) -> LocalModelResponse:
        prompt, model = _validate_prompt_model(prompt, self.model_name)
        self._check_admission()
        self._check_canceled()
        with self._lock:
            if self._used:
                raise LocalModelError("fast_interchange_request_replayed", "A new approval is required for another request.")
            self._used = True
        fixed = {"model": model, "request_id": self.request_id,
                 "capability": self._release.capability,
                 "release_fingerprint": self._release.release_fingerprint}
        reservation = self._control.post_json("/v1/requests/prepare", fixed)
        if reservation.get("request_id") != self.request_id or reservation.get("status") != "reserved":
            raise LocalModelError("fast_interchange_reservation_invalid", "The worker did not reserve this request.")
        with self._lock:
            self._prepared = True
        if self._cancel.is_set():
            self.cancel()
            self._check_canceled()
        body = self._http.post_json(
            "/v1/chat/completions",
            {
                **fixed,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "top_p": 1,
                "max_tokens": 1024,
                "stream": False,
            },
        )
        self._check_canceled()
        self._check_admission()
        if any(body.get(key) != value for key, value in fixed.items()) or body.get("review_required") is not True:
            raise LocalModelError("fast_interchange_runtime_identity_mismatch",
                                  "The worker response did not match the approved release and request.")
        if str(body.get("model") or "") != model:
            raise LocalModelError(
                "fast_interchange_runtime_identity_mismatch",
                "The FAST INTERCHANGE worker returned a different release-model identity.",
            )
        choices = body.get("choices")
        if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
            raise LocalModelError("local_model_invalid_payload", "The local model returned no choices.")
        first = choices[0]
        if str(first.get("finish_reason") or "") != "stop":
            raise LocalModelError(
                "fast_interchange_completion_incomplete",
                "The FAST INTERCHANGE worker did not return a completed response.",
            )
        message = first.get("message")
        if not isinstance(message, dict) or set(message) != {"role", "content"} or message.get("role") != "assistant" or not isinstance(message.get("content"), str):
            raise LocalModelError("local_model_invalid_payload", "The local model returned no message.")
        text = str(message.get("content") or "").strip()
        if not text:
            raise LocalModelError("local_model_empty_response", "The local model returned no text.")
        return LocalModelResponse(
            text=text,
            provider_id=self.provider_id,
            model_id=model,
            endpoint_class=self.endpoint.endpoint_class,
            usage=dict(body.get("usage") or {}),
            finish_reason="stop",
        )


def build_local_client(*, provider: str, endpoint: str, model_name: str, timeout_seconds: int = 120, capability: str | None = None) -> LocalGenerationClient:
    provider_key = str(provider or "").strip().lower().replace("-", "_")
    if provider_key == "ollama":
        return OllamaLocalClient(model_name=model_name, endpoint=endpoint, timeout_seconds=timeout_seconds)
    if provider_key in {"openai_compatible", "openai_compatible_local", "lm_studio", "llama_cpp"}:
        return OpenAICompatibleLocalClient(model_name=model_name, endpoint=endpoint, timeout_seconds=timeout_seconds)
    if provider_key in {"fast_interchange", "fast_interchange_local"}:
        return FastInterchangeLocalClient(model_name=model_name, endpoint=endpoint, timeout_seconds=timeout_seconds, capability=capability)
    raise ValueError("unsupported_local_model_provider")
