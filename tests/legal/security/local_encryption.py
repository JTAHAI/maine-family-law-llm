from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass


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
    def from_dict(cls, payload: dict[str, str]) -> "EncryptedBlob":
        return cls(
            algorithm=payload["algorithm"],
            kdf=payload["kdf"],
            salt=payload["salt"],
            nonce=payload["nonce"],
            ciphertext=payload["ciphertext"],
            mac=payload["mac"],
        )


class LocalEnvelopeEncryptor:
    """Dependency-free local encrypted envelope for matter-store tests and demos.

    This intentionally keeps private matter files out of plaintext source/runtime exports.
    Enterprise deployments should replace it with a vetted KMS/FIPS-backed envelope.
    """

    algorithm = "local-pbkdf2-sha256-xor-hmac-demo-envelope"
    kdf = "pbkdf2_hmac_sha256_200000"

    def __init__(self, passphrase: str):
        if not passphrase or len(passphrase) < 12:
            raise ValueError("matter store encryption passphrase must be at least 12 characters")
        self.passphrase = passphrase.encode("utf-8")

    def _derive_keys(self, salt: bytes) -> tuple[bytes, bytes]:
        key_material = hashlib.pbkdf2_hmac("sha256", self.passphrase, salt, 200_000, dklen=64)
        return key_material[:32], key_material[32:]

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
        nonce = os.urandom(16)
        enc_key, mac_key = self._derive_keys(salt)
        stream = self._keystream(enc_key, nonce, len(plaintext))
        ciphertext = bytes(a ^ b for a, b in zip(plaintext, stream, strict=True))
        mac = hmac.new(mac_key, nonce + ciphertext, hashlib.sha256).digest()
        return EncryptedBlob(
            algorithm=self.algorithm,
            kdf=self.kdf,
            salt=base64.b64encode(salt).decode("ascii"),
            nonce=base64.b64encode(nonce).decode("ascii"),
            ciphertext=base64.b64encode(ciphertext).decode("ascii"),
            mac=base64.b64encode(mac).decode("ascii"),
        )

    def decrypt(self, blob: EncryptedBlob) -> bytes:
        if blob.algorithm != self.algorithm:
            raise ValueError(f"unsupported encrypted blob algorithm: {blob.algorithm}")
        salt = base64.b64decode(blob.salt)
        nonce = base64.b64decode(blob.nonce)
        ciphertext = base64.b64decode(blob.ciphertext)
        expected_mac = base64.b64decode(blob.mac)
        enc_key, mac_key = self._derive_keys(salt)
        actual_mac = hmac.new(mac_key, nonce + ciphertext, hashlib.sha256).digest()
        if not hmac.compare_digest(expected_mac, actual_mac):
            raise ValueError("encrypted matter blob integrity check failed")
        stream = self._keystream(enc_key, nonce, len(ciphertext))
        return bytes(a ^ b for a, b in zip(ciphertext, stream, strict=True))

    def encrypt_json(self, payload: dict) -> dict[str, str]:
        plaintext = json.dumps(payload, sort_keys=True).encode("utf-8")
        return self.encrypt(plaintext).as_dict()

    def decrypt_json(self, payload: dict[str, str]) -> dict:
        plaintext = self.decrypt(EncryptedBlob.from_dict(payload))
        return json.loads(plaintext.decode("utf-8"))
