"""Bounded, encrypted idempotency protection for local API mutations.

The local workbench has many independently developed mutation routes.  Keeping
duplicate suppression in individual handlers is error prone and it makes a
network retry capable of creating a second private work product.  This module
provides one deliberately small HTTP boundary instead.  A caller supplied key
is bound to the request method, route, tenant, role, browser session, active
matter, and a hash of the request body.  The replayed JSON response is kept
only in encrypted local runtime state; neither the registry index nor its audit
trail stores record text, a prompt, a path, a raw request, or a raw response.

Compatibility is intentional: older local API callers that do not send an
idempotency key keep working, but receive an explicit ``not_provided`` status.
The shipped workbench sends a fresh key for each user mutation and reuses it
when the same options object is retried.  Deployments may set
``MFL_REQUIRE_IDEMPOTENCY_KEYS=1`` after legacy callers are migrated.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


_KEY_HEADER = "X-MFLL-Idempotency-Key"
_STATUS_HEADER = "X-MFLL-Idempotency-Status"
_KEY_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{7,127}")
_MUTATION_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_MAX_STATE_BYTES = 4 * 1024 * 1024
_MAX_RESPONSE_BYTES = 512 * 1024
_MAX_ENTRIES = 160
_COMPLETE_TTL_SECONDS = 20 * 60
_PENDING_TTL_SECONDS = 5 * 60
_LOCK = threading.RLock()


class IdempotencyError(RuntimeError):
    """Safe machine-readable error returned by the idempotency boundary."""

    def __init__(self, code: str, *, status_code: int = 409) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: Any) -> str:
    if isinstance(value, bytes):
        return hashlib.sha256(value).hexdigest()
    return hashlib.sha256(_canonical(value)).hexdigest()


def _default_root() -> Path:
    configured = str(os.environ.get("MFL_IDEMPOTENCY_STATE_ROOT") or os.environ.get("MFL_RUNTIME_STATE_ROOT") or "").strip()
    if configured:
        return Path(configured).expanduser().resolve(strict=False) / "idempotency"
    if os.name == "nt":
        return (Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "MaineFamilyLawLLM" / "runtime" / "idempotency").resolve(strict=False)
    return (Path.home() / ".local" / "state" / "maine-family-law-llm" / "idempotency").resolve(strict=False)


def _safe_scope_part(value: Any, *, fallback: str) -> str:
    candidate = str(value or "").strip()
    return candidate[:160] if candidate else fallback


class IdempotencyRegistry:
    """Encrypted, bounded replay registry shared by canonical API routes."""

    schema_version = "local_idempotency_registry_v1"

    def __init__(self, root: str | Path | None = None, *, encryption_key: str | None = None) -> None:
        self.root = Path(root or _default_root()).expanduser().resolve(strict=False)
        self.path = self.root / "registry.json.enc"
        self.lock_path = self.root / ".registry.lock"
        key = encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me"
        self.encryptor = LocalEnvelopeEncryptor(key)

    def _empty(self) -> dict[str, Any]:
        return {"schema_version": self.schema_version, "revision": 0, "entries": {}, "audit": []}

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty()
        try:
            state = self.encryptor.decrypt_json(strict_json_load_path(self.path, max_bytes=_MAX_STATE_BYTES, require_object=True))
        except Exception as exc:  # pragma: no cover - defensive corrupted-state boundary
            raise IdempotencyError("idempotency_registry_unavailable", status_code=503) from exc
        if not isinstance(state, dict) or state.get("schema_version") != self.schema_version:
            raise IdempotencyError("idempotency_registry_unavailable", status_code=503)
        if not isinstance(state.get("entries"), dict) or not isinstance(state.get("audit"), list):
            raise IdempotencyError("idempotency_registry_unavailable", status_code=503)
        return state

    def _save(self, state: dict[str, Any]) -> None:
        try:
            atomic_write_bytes(self.path, _canonical(self.encryptor.encrypt_json(state)), mode=0o600)
        except Exception as exc:  # pragma: no cover - disk failure boundary
            raise IdempotencyError("idempotency_registry_write_failed", status_code=503) from exc

    @staticmethod
    def _prune(state: dict[str, Any], *, now: float) -> None:
        entries = dict(state.get("entries") or {})
        for fingerprint, row in list(entries.items()):
            if not isinstance(row, dict) or float(row.get("expires_at") or 0) <= now:
                entries.pop(fingerprint, None)
        if len(entries) > _MAX_ENTRIES:
            ordered = sorted(entries.items(), key=lambda item: float(dict(item[1]).get("updated_at") or 0), reverse=True)
            entries = dict(ordered[:_MAX_ENTRIES])
        state["entries"] = entries
        state["audit"] = list(state.get("audit") or [])[-(_MAX_ENTRIES * 3):]

    @staticmethod
    def _audit(state: dict[str, Any], *, event_type: str, fingerprint: str, request_hash: str, response_hash: str = "") -> None:
        previous = str((state.get("audit") or [{}])[-1].get("event_hash") or "")
        basis = {
            "event_type": event_type,
            "recorded_at": int(time.time()),
            "binding_hash": fingerprint,
            "request_hash": request_hash,
            "response_hash": response_hash,
            "previous_hash": previous,
        }
        state["audit"] = [*list(state.get("audit") or []), {**basis, "event_hash": _digest(basis)}]

    def begin(self, *, binding: dict[str, str], key: str, request_hash: str) -> dict[str, Any]:
        """Reserve a key or return its authenticated replay response."""

        normalized_key = str(key or "").strip()
        if not _KEY_RE.fullmatch(normalized_key):
            raise IdempotencyError("idempotency_key_invalid", status_code=400)
        key_hash = _digest(normalized_key.encode("utf-8"))
        binding_hash = _digest({**binding, "key_hash": key_hash})
        now = time.time()
        with _LOCK, exclusive_file_lock(self.lock_path):
            state = self._load()
            self._prune(state, now=now)
            entries = state["entries"]
            existing = entries.get(binding_hash)
            if isinstance(existing, dict):
                if str(existing.get("request_hash") or "") != request_hash:
                    raise IdempotencyError("idempotency_key_reused_for_different_request")
                status = str(existing.get("status") or "")
                if status == "completed":
                    encoded = str(existing.get("response_b64") or "")
                    try:
                        response_body = base64.b64decode(encoded.encode("ascii"), validate=True)
                    except Exception as exc:  # pragma: no cover - encrypted-state corruption boundary
                        raise IdempotencyError("idempotency_registry_unavailable", status_code=503) from exc
                    self._audit(state, event_type="idempotency_replayed", fingerprint=binding_hash, request_hash=request_hash, response_hash=str(existing.get("response_hash") or ""))
                    state["revision"] = int(state.get("revision") or 0) + 1
                    self._save(state)
                    return {"state": "replay", "status_code": int(existing.get("status_code") or 200), "body": response_body, "content_type": str(existing.get("content_type") or "application/json")}
                raise IdempotencyError("idempotency_request_in_progress", status_code=409)
            entries[binding_hash] = {
                "status": "pending",
                "request_hash": request_hash,
                "created_at": now,
                "updated_at": now,
                "expires_at": now + _PENDING_TTL_SECONDS,
            }
            self._audit(state, event_type="idempotency_reserved", fingerprint=binding_hash, request_hash=request_hash)
            state["revision"] = int(state.get("revision") or 0) + 1
            self._save(state)
        return {"state": "new", "binding_hash": binding_hash}

    def complete(self, *, binding_hash: str, request_hash: str, status_code: int, body: bytes, content_type: str) -> None:
        if len(body) > _MAX_RESPONSE_BYTES:
            self.release(binding_hash=binding_hash, request_hash=request_hash, event_type="idempotency_response_too_large")
            raise IdempotencyError("idempotency_response_too_large", status_code=413)
        now = time.time()
        with _LOCK, exclusive_file_lock(self.lock_path):
            state = self._load()
            self._prune(state, now=now)
            row = dict((state.get("entries") or {}).get(binding_hash) or {})
            if row.get("status") != "pending" or row.get("request_hash") != request_hash:
                raise IdempotencyError("idempotency_registry_unavailable", status_code=503)
            response_hash = _digest(body)
            row.update({
                "status": "completed",
                "status_code": int(status_code),
                "content_type": str(content_type or "application/json")[:120],
                "response_b64": base64.b64encode(body).decode("ascii"),
                "response_hash": response_hash,
                "updated_at": now,
                "expires_at": now + _COMPLETE_TTL_SECONDS,
            })
            state["entries"][binding_hash] = row
            self._audit(state, event_type="idempotency_completed", fingerprint=binding_hash, request_hash=request_hash, response_hash=response_hash)
            state["revision"] = int(state.get("revision") or 0) + 1
            self._save(state)

    def release(self, *, binding_hash: str, request_hash: str, event_type: str = "idempotency_released") -> None:
        with _LOCK, exclusive_file_lock(self.lock_path):
            state = self._load()
            row = dict((state.get("entries") or {}).get(binding_hash) or {})
            if row.get("status") == "pending" and row.get("request_hash") == request_hash:
                state["entries"].pop(binding_hash, None)
                self._audit(state, event_type=event_type, fingerprint=binding_hash, request_hash=request_hash)
                state["revision"] = int(state.get("revision") or 0) + 1
                self._save(state)

    def status(self) -> dict[str, Any]:
        """Return content-free policy health for the production UI."""

        with _LOCK, exclusive_file_lock(self.lock_path):
            state = self._load()
            self._prune(state, now=time.time())
            self._save(state)
            entries = list(dict(state.get("entries") or {}).values())
        return {
            "schema_version": self.schema_version,
            "status": "ready",
            "active_entries": len(entries),
            "completed_entries": sum(1 for row in entries if row.get("status") == "completed"),
            "pending_entries": sum(1 for row in entries if row.get("status") == "pending"),
            "response_storage": "encrypted_local_runtime_state",
            "scope_binding": ["method", "route", "tenant", "role", "browser_session", "active_matter", "request_hash"],
            "legacy_callers": "allowed_with_explicit_not_provided_status",
            "review_required": True,
            "network_used": False,
        }


def _mutation_binding(request: Request, matter_scope_resolver: Callable[[], str] | None) -> dict[str, str]:
    role = _safe_scope_part(request.headers.get("X-User-Role"), fallback="reviewer").casefold()
    tenant = _safe_scope_part(request.headers.get("X-Tenant-Id"), fallback="local-desktop")
    session = _safe_scope_part(request.headers.get("X-MFLL-Client-Session"), fallback="legacy-local-session").casefold()
    try:
        matter = _safe_scope_part(matter_scope_resolver() if matter_scope_resolver else request.headers.get("X-MFLL-Matter-Id"), fallback="no_active_matter")
    except Exception:
        matter = "matter_scope_unavailable"
    # Raw route and matter labels do not enter the persistent state; only their
    # digest participates in the encrypted binding.
    return {
        "method": request.method.upper(),
        "route_hash": _digest(request.url.path),
        "tenant_hash": _digest(tenant),
        "role_hash": _digest(role),
        "session_hash": _digest(session),
        "matter_hash": _digest(matter),
    }


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Apply encrypted duplicate suppression to every HTTP mutation route."""

    def __init__(self, app: Any, *, registry_factory: Callable[[], IdempotencyRegistry] | None = None, matter_scope_resolver: Callable[[], str] | None = None) -> None:
        super().__init__(app)
        self.registry_factory = registry_factory or IdempotencyRegistry
        self.matter_scope_resolver = matter_scope_resolver

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:  # type: ignore[override]
        if request.method.upper() not in _MUTATION_METHODS or not request.url.path.startswith("/api/") or request.url.path == "/ask/stream":
            return await call_next(request)
        # A model result may contain private context whose capability has since
        # expired/revoked. Never replay it around the route's live checks. The
        # host's single-use approval prevents a retried request generating twice.
        if request.url.path in {"/api/local-agent/preview", "/api/local-agent/run", "/api/local-agent/cancel"} or request.url.path.startswith("/api/model-packs/"):
            response = await call_next(request)
            response.headers[_STATUS_HEADER] = "single_use_approval"
            return response
        key = str(request.headers.get(_KEY_HEADER) or "").strip()
        if not key:
            if os.environ.get("MFL_REQUIRE_IDEMPOTENCY_KEYS", "").strip() == "1":
                return JSONResponse(status_code=428, content={"detail": "idempotency_key_required", "review_required": True}, headers={_STATUS_HEADER: "required"})
            response = await call_next(request)
            response.headers[_STATUS_HEADER] = "not_provided"
            return response
        try:
            body = await request.body()
            registry = self.registry_factory()
            reservation = registry.begin(binding=_mutation_binding(request, self.matter_scope_resolver), key=key, request_hash=_digest(body))
        except IdempotencyError as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.code, "review_required": True}, headers={_STATUS_HEADER: "blocked"})
        if reservation["state"] == "replay":
            response = Response(content=reservation["body"], status_code=reservation["status_code"], media_type=reservation["content_type"])
            response.headers[_STATUS_HEADER] = "replayed"
            return response
        binding_hash = str(reservation["binding_hash"])
        request_hash = _digest(body)
        try:
            response = await call_next(request)
        except Exception:
            registry.release(binding_hash=binding_hash, request_hash=request_hash, event_type="idempotency_handler_exception")
            raise
        content_type = str(response.headers.get("content-type") or "application/json")
        # Only bounded JSON route responses are replayed. File/stream exports
        # are protected at their mutation/session-creation route, never by
        # buffering a private download in memory.
        if not content_type.lower().startswith("application/json") or not 200 <= int(response.status_code) < 500:
            registry.release(binding_hash=binding_hash, request_hash=request_hash, event_type="idempotency_noncacheable_response")
            response.headers[_STATUS_HEADER] = "not_cached"
            return response
        chunks: list[bytes] = []
        total = 0
        async for chunk in response.body_iterator:  # type: ignore[attr-defined]
            chunk_bytes = bytes(chunk)
            total += len(chunk_bytes)
            chunks.append(chunk_bytes)
        rendered = b"".join(chunks)
        if total > _MAX_RESPONSE_BYTES:
            registry.release(binding_hash=binding_hash, request_hash=request_hash, event_type="idempotency_response_too_large")
            replayable = Response(content=rendered, status_code=response.status_code, media_type=content_type)
            replayable.headers[_STATUS_HEADER] = "not_cached_response_too_large"
            return replayable
        try:
            registry.complete(binding_hash=binding_hash, request_hash=request_hash, status_code=response.status_code, body=rendered, content_type=content_type)
        except IdempotencyError as exc:
            replayable = Response(content=rendered, status_code=response.status_code, media_type=content_type)
            replayable.headers[_STATUS_HEADER] = "not_cached"
            replayable.headers["X-MFLL-Idempotency-Error"] = exc.code
            return replayable
        replayable = Response(content=rendered, status_code=response.status_code, media_type=content_type)
        replayable.headers[_STATUS_HEADER] = "recorded"
        return replayable


__all__ = ["IdempotencyError", "IdempotencyMiddleware", "IdempotencyRegistry"]
