from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .durable_io import atomic_write_bytes, read_bounded_regular_file


_VAULT_KEY_LOCK = threading.Lock()
_MAX_PROTECTED_KEY_BYTES = 16 * 1024
_VAULT_KEY_CACHE: dict[Path, bytes] = {}


@dataclass(frozen=True)
class EncryptedBlob:
    algorithm: str
    kdf: str
    salt: str
    nonce: str
    ciphertext: str
    mac: str

    def as_dict(self) -> dict[str, str]:
        return {
            "algorithm": self.algorithm,
            "kdf": self.kdf,
            "salt": self.salt,
            "nonce": self.nonce,
            "ciphertext": self.ciphertext,
            "mac": self.mac,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, str]) -> EncryptedBlob:
        return cls(
            algorithm=payload["algorithm"],
            kdf=payload["kdf"],
            salt=payload["salt"],
            nonce=payload["nonce"],
            ciphertext=payload["ciphertext"],
            mac=payload.get("mac", ""),
        )


class LocalEnvelopeEncryptor:
    """Authenticated AES-GCM envelope with transparent legacy-read migration."""

    algorithm = "aes-256-gcm"
    kdf = "pbkdf2_hmac_sha256_200000"
    legacy_algorithm = "local-pbkdf2-sha256-xor-hmac-demo-envelope"
    development_default = "local-development-key-change-me"

    def __init__(self, passphrase: str):
        if not passphrase or len(passphrase) < 12:
            raise ValueError("matter store encryption passphrase must be at least 12 characters")
        self.legacy_passphrases: list[bytes] = []
        if passphrase == self.development_default:
            self.passphrase = default_matter_passphrase().encode("utf-8")
            self.legacy_passphrases.append(passphrase.encode("utf-8"))
        else:
            self.passphrase = passphrase.encode("utf-8")

    @staticmethod
    def _derive_keys_for(passphrase: bytes, salt: bytes) -> tuple[bytes, bytes]:
        key_material = hashlib.pbkdf2_hmac("sha256", passphrase, salt, 200_000, dklen=64)
        return key_material[:32], key_material[32:]

    def _derive_keys(self, salt: bytes) -> tuple[bytes, bytes]:
        return self._derive_keys_for(self.passphrase, salt)

    @staticmethod
    def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
        output = bytearray()
        counter = 0
        while len(output) < length:
            output.extend(hashlib.sha256(key + nonce + counter.to_bytes(8, "big")).digest())
            counter += 1
        return bytes(output[:length])

    def encrypt(self, plaintext: bytes) -> EncryptedBlob:
        salt = os.urandom(16)
        nonce = os.urandom(12)
        enc_key, _mac_key = self._derive_keys(salt)
        associated_data = f"{self.algorithm}|{self.kdf}".encode("ascii")
        ciphertext = AESGCM(enc_key).encrypt(nonce, plaintext, associated_data)
        return EncryptedBlob(
            algorithm=self.algorithm,
            kdf=self.kdf,
            salt=base64.b64encode(salt).decode("ascii"),
            nonce=base64.b64encode(nonce).decode("ascii"),
            ciphertext=base64.b64encode(ciphertext).decode("ascii"),
            mac="",
        )

    def decrypt(self, blob: EncryptedBlob) -> bytes:
        salt = base64.b64decode(blob.salt)
        nonce = base64.b64decode(blob.nonce)
        ciphertext = base64.b64decode(blob.ciphertext)
        if blob.algorithm == self.algorithm:
            enc_key, _mac_key = self._derive_keys(salt)
            associated_data = f"{self.algorithm}|{self.kdf}".encode("ascii")
            try:
                return AESGCM(enc_key).decrypt(nonce, ciphertext, associated_data)
            except Exception as exc:
                raise ValueError("encrypted matter blob integrity check failed") from exc
        if blob.algorithm == self.legacy_algorithm:
            return self._decrypt_legacy(blob, salt, nonce, ciphertext)
        raise ValueError(f"unsupported encrypted blob algorithm: {blob.algorithm}")

    def _decrypt_legacy(
        self,
        blob: EncryptedBlob,
        salt: bytes,
        nonce: bytes,
        ciphertext: bytes,
    ) -> bytes:
        expected_mac = base64.b64decode(blob.mac)
        for passphrase in [self.passphrase, *self.legacy_passphrases]:
            enc_key, mac_key = self._derive_keys_for(passphrase, salt)
            actual_mac = hmac.new(mac_key, nonce + ciphertext, hashlib.sha256).digest()
            if hmac.compare_digest(expected_mac, actual_mac):
                stream = self._keystream(enc_key, nonce, len(ciphertext))
                return bytes(a ^ b for a, b in zip(ciphertext, stream, strict=True))
        raise ValueError("encrypted matter blob integrity check failed")

    def encrypt_json(self, payload: dict) -> dict[str, str]:
        plaintext = json.dumps(payload, sort_keys=True).encode("utf-8")
        return self.encrypt(plaintext).as_dict()

    def decrypt_json(self, payload: dict[str, str]) -> dict:
        plaintext = self.decrypt(EncryptedBlob.from_dict(payload))
        return json.loads(plaintext.decode("utf-8"))


def _vault_key_root() -> Path:
    configured = str(os.environ.get("MFL_VAULT_KEY_ROOT") or "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "MaineFamilyLawLLM" / "vault"
    return Path.home() / ".local" / "state" / "maine-family-law-llm" / "vault"


def default_matter_passphrase() -> str:
    """Load or create a per-user random secret protected by the operating system."""

    root = _vault_key_root()
    root.mkdir(parents=True, exist_ok=True)
    protected_path = root / ("master-key.dpapi" if os.name == "nt" else "master-key.local")
    # Multiple API workers can reach first-use concurrently. Serialize the
    # create/read transition so a caller never returns a key that another
    # thread immediately replaced with a different protected key.
    with _VAULT_KEY_LOCK:
        cached = _VAULT_KEY_CACHE.get(protected_path)
        if cached is not None:
            secret = cached
        elif protected_path.is_file():
            protected = read_bounded_regular_file(
                protected_path, max_bytes=_MAX_PROTECTED_KEY_BYTES
            )
            secret = _unprotect(protected)
            _VAULT_KEY_CACHE[protected_path] = secret
        else:
            secret = secrets.token_bytes(32)
            protected = _protect(secret)
            atomic_write_bytes(protected_path, protected, mode=0o600)
            persisted = read_bounded_regular_file(
                protected_path, max_bytes=_MAX_PROTECTED_KEY_BYTES
            )
            if not hmac.compare_digest(persisted, protected):
                raise ValueError("matter vault protected key persistence verification failed")
            _VAULT_KEY_CACHE[protected_path] = secret
    if len(secret) != 32:
        raise ValueError("matter vault master key is invalid")
    return base64.urlsafe_b64encode(secret).decode("ascii")


def _protect(secret: bytes) -> bytes:
    if os.name == "nt":
        try:
            return _windows_dpapi(secret, protect=True)
        except Exception as exc:
            raise ValueError("Windows DPAPI could not protect the matter vault key") from exc
    return secret


def _unprotect(protected: bytes) -> bytes:
    if os.name == "nt":
        last_error: Exception | None = None
        # Some Windows profiles transiently return ERROR_INVALID_DATA for a
        # newly persisted, otherwise valid DPAPI blob. Retry the same immutable
        # bytes briefly; never regenerate or replace an unreadable existing key.
        for attempt in range(6):
            try:
                return _windows_dpapi(protected, protect=False)
            except Exception as exc:
                last_error = exc
                if attempt < 5:
                    time.sleep(0.05 * (2**attempt))
        raise ValueError("Windows DPAPI could not unlock the matter vault key") from last_error
    return protected


def _windows_dpapi(data: bytes, *, protect: bool) -> bytes:
    """Call Windows DPAPI directly and copy the OS-owned output buffer.

    The direct call avoids an intermittent invalid-blob failure observed in the
    Python 3.14 pywin32 wrapper during concurrent first-use. DPAPI still uses
    the current-user scope and no optional entropy, matching the prior format.
    """

    if os.name != "nt":
        raise OSError("windows_dpapi_unavailable")
    if not data or len(data) > _MAX_PROTECTED_KEY_BYTES:
        raise ValueError("invalid DPAPI input length")

    import ctypes
    from ctypes import wintypes

    class DataBlob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]

    buffer = ctypes.create_string_buffer(data, len(data))
    input_blob = DataBlob(
        len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))
    )
    output_blob = DataBlob()
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(DataBlob),
        wintypes.LPCWSTR,
        ctypes.POINTER(DataBlob),
        wintypes.LPVOID,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(DataBlob),
    ]
    crypt32.CryptProtectData.restype = wintypes.BOOL
    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(DataBlob),
        wintypes.LPVOID,
        ctypes.POINTER(DataBlob),
        wintypes.LPVOID,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(DataBlob),
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
    kernel32.LocalFree.restype = wintypes.HLOCAL

    if protect:
        ok = crypt32.CryptProtectData(
            ctypes.byref(input_blob),
            "MaineFamilyLawLLM",
            None,
            None,
            None,
            0,
            ctypes.byref(output_blob),
        )
    else:
        ok = crypt32.CryptUnprotectData(
            ctypes.byref(input_blob),
            None,
            None,
            None,
            None,
            0,
            ctypes.byref(output_blob),
        )
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if not output_blob.pbData or output_blob.cbData <= 0:
            raise ValueError("DPAPI returned an empty output")
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        if output_blob.pbData:
            kernel32.LocalFree(ctypes.cast(output_blob.pbData, wintypes.HLOCAL))


def vault_security_status() -> dict[str, object]:
    path = _vault_key_root() / ("master-key.dpapi" if os.name == "nt" else "master-key.local")
    return {
        "schema_version": "matter_vault_security_v1",
        "status": "ready" if path.is_file() else "key_will_be_created_on_first_use",
        "envelope_algorithm": LocalEnvelopeEncryptor.algorithm,
        "key_protection": "windows_dpapi_current_user"
        if os.name == "nt"
        else "user_file_permissions",
        "legacy_read_migration_supported": True,
        "master_key_present": path.is_file(),
        "master_key_exported": False,
        "review_required": False,
    }


__all__ = [
    "EncryptedBlob",
    "LocalEnvelopeEncryptor",
    "default_matter_passphrase",
    "vault_security_status",
]
