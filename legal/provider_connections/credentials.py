from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

try:  # pragma: no cover - import depends on host platform
    import win32cred  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - fallback for non-Windows test hosts
    win32cred = None  # type: ignore[assignment]


class CredentialBackend(Protocol):
    def CredWrite(self, credential: dict[str, Any], flags: int) -> Any: ...
    def CredRead(self, target: str, cred_type: int, flags: int) -> dict[str, Any]: ...
    def CredDelete(self, target: str, cred_type: int, flags: int) -> Any: ...
    def CredEnumerate(self, filter: str, flags: int) -> tuple[int, list[dict[str, Any]]]: ...


class WindowsCredentialError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class StoredCredential:
    provider_id: str
    namespace: str
    target_name: str
    username: str
    credential_status: str
    exists: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "namespace": self.namespace,
            "target_name": self.target_name,
            "username": self.username,
            "credential_status": self.credential_status,
            "exists": self.exists,
        }


def _backend() -> CredentialBackend:
    if win32cred is None:
        raise WindowsCredentialError("credential_backend_unavailable", "Windows Credential Manager is unavailable on this host.")
    return win32cred  # type: ignore[return-value]


def _cred_type(backend: CredentialBackend | None = None) -> int:
    backend = backend or _backend()
    return int(getattr(backend, "CRED_TYPE_GENERIC", 1))


def _cred_persist(backend: CredentialBackend | None = None) -> int:
    backend = backend or _backend()
    return int(getattr(backend, "CRED_PERSIST_LOCAL_MACHINE", 2))


class WindowsCredentialStore:
    """Store provider secrets in Windows Credential Manager only."""

    def __init__(self, *, namespace: str = "maine-family-law-llm", backend: CredentialBackend | None = None) -> None:
        self.namespace = namespace
        self._backend = backend if backend is not None else win32cred

    @property
    def backend_available(self) -> bool:
        return self._backend is not None

    def _require_backend(self) -> CredentialBackend:
        if self._backend is None:
            raise WindowsCredentialError(
                "credential_backend_unavailable",
                "Windows Credential Manager is unavailable on this host.",
            )
        return self._backend

    def _target_name(self, provider_id: str, secret_name: str, account_label: str) -> str:
        clean_provider = str(provider_id or "").strip().replace(" ", "_")
        clean_secret = str(secret_name or "api_key").strip().replace(" ", "_")
        clean_account = str(account_label or "default").strip().replace(" ", "_")
        return f"{self.namespace}:{clean_provider}:{clean_account}:{clean_secret}"

    def store_secret(self, provider_id: str, secret_name: str, secret_value: str, *, account_label: str = "default") -> StoredCredential:
        target_name = self._target_name(provider_id, secret_name, account_label)
        backend = self._require_backend()
        credential = {
            "Type": _cred_type(backend),
            "TargetName": target_name,
            "CredentialBlob": str(secret_value or "").encode("utf-16-le"),
            "Persist": _cred_persist(backend),
            "UserName": str(account_label or provider_id or "default"),
        }
        try:
            backend.CredWrite(credential, 0)
        except Exception as exc:  # pragma: no cover - backend specific failure path
            raise WindowsCredentialError("credential_store_failed", "Failed to store provider credentials in Windows Credential Manager.") from exc
        return StoredCredential(provider_id=provider_id, namespace=self.namespace, target_name=target_name, username=credential["UserName"], credential_status="stored", exists=True)

    def read_secret(self, provider_id: str, secret_name: str, *, account_label: str = "default") -> str:
        target_name = self._target_name(provider_id, secret_name, account_label)
        backend = self._require_backend()
        try:
            credential = backend.CredRead(target_name, _cred_type(backend), 0)
        except Exception as exc:  # pragma: no cover - backend specific failure path
            raise WindowsCredentialError("credential_not_found", "The requested provider credential was not found.") from exc
        blob = credential.get("CredentialBlob", b"")
        if isinstance(blob, bytes):
            return blob.decode("utf-16-le")
        if isinstance(blob, str):
            return blob
        return str(blob)

    def delete_secret(self, provider_id: str, secret_name: str, *, account_label: str = "default") -> StoredCredential:
        target_name = self._target_name(provider_id, secret_name, account_label)
        backend = self._require_backend()
        try:
            backend.CredDelete(target_name, _cred_type(backend), 0)
        except Exception as exc:  # pragma: no cover - backend specific failure path
            raise WindowsCredentialError("credential_delete_failed", "Failed to delete the provider credential.") from exc
        return StoredCredential(provider_id=provider_id, namespace=self.namespace, target_name=target_name, username=str(account_label or provider_id or "default"), credential_status="deleted", exists=False)

    def delete_provider_credentials(self, provider_id: str) -> int:
        prefix = f"{self.namespace}:{str(provider_id or '').strip().replace(' ', '_')}:"
        deleted = 0
        backend = self._require_backend()
        try:
            _, rows = backend.CredEnumerate(prefix, 0)
        except Exception as exc:  # pragma: no cover - backend specific failure path
            raise WindowsCredentialError("credential_enumeration_failed", "Failed to enumerate provider credentials.") from exc
        for row in rows or []:
            target_name = str(row.get("TargetName") or "")
            if not target_name.startswith(prefix):
                continue
            backend.CredDelete(target_name, _cred_type(backend), 0)
            deleted += 1
        return deleted

    def credential_status(self, provider_id: str, secret_name: str = "api_key", *, account_label: str = "default") -> StoredCredential:
        target_name = self._target_name(provider_id, secret_name, account_label)
        if self._backend is None:
            return StoredCredential(
                provider_id=provider_id,
                namespace=self.namespace,
                target_name=target_name,
                username=str(account_label or provider_id or "default"),
                credential_status="backend_unavailable",
                exists=False,
            )
        try:
            credential = self._backend.CredRead(target_name, _cred_type(self._backend), 0)
        except Exception:
            return StoredCredential(provider_id=provider_id, namespace=self.namespace, target_name=target_name, username=str(account_label or provider_id or "default"), credential_status="missing", exists=False)
        username = str(credential.get("UserName") or account_label or provider_id or "default")
        return StoredCredential(provider_id=provider_id, namespace=self.namespace, target_name=target_name, username=username, credential_status="stored", exists=True)
