import base64
import hashlib
import hmac
import os
from concurrent.futures import ThreadPoolExecutor

import pytest

from legal.security.local_encryption import (
    EncryptedBlob,
    LocalEnvelopeEncryptor,
    default_matter_passphrase,
    vault_security_status,
)


def test_aes_gcm_envelope_round_trip_and_tamper_detection():
    encryptor = LocalEnvelopeEncryptor("synthetic-test-passphrase")
    blob = encryptor.encrypt(b"private matter data")
    assert blob.algorithm == "aes-256-gcm"
    assert blob.mac == ""
    assert encryptor.decrypt(blob) == b"private matter data"
    raw = bytearray(base64.b64decode(blob.ciphertext))
    raw[0] ^= 1
    tampered = EncryptedBlob(**{**blob.__dict__, "ciphertext": base64.b64encode(raw).decode()})
    with pytest.raises(ValueError, match="integrity"):
        encryptor.decrypt(tampered)


def test_os_bound_default_key_is_stable_and_not_the_development_literal(monkeypatch, tmp_path):
    monkeypatch.setenv("MFL_VAULT_KEY_ROOT", str(tmp_path))
    first = default_matter_passphrase()
    second = default_matter_passphrase()
    assert first == second
    assert first != LocalEnvelopeEncryptor.development_default
    assert vault_security_status()["master_key_present"] is True
    assert len(list(tmp_path.iterdir())) == 1


def test_os_bound_default_key_is_stable_during_concurrent_first_use(monkeypatch, tmp_path):
    monkeypatch.setenv("MFL_VAULT_KEY_ROOT", str(tmp_path))
    with ThreadPoolExecutor(max_workers=8) as executor:
        keys = list(executor.map(lambda _index: default_matter_passphrase(), range(32)))
    assert len(set(keys)) == 1
    assert len(list(tmp_path.iterdir())) == 1


def test_default_encryptor_can_read_legacy_development_envelope(monkeypatch, tmp_path):
    monkeypatch.setenv("MFL_VAULT_KEY_ROOT", str(tmp_path))
    passphrase = LocalEnvelopeEncryptor.development_default.encode()
    salt = os.urandom(16)
    nonce = os.urandom(16)
    material = hashlib.pbkdf2_hmac("sha256", passphrase, salt, 200_000, dklen=64)
    enc_key, mac_key = material[:32], material[32:]
    plaintext = b"legacy private matter data"
    stream = LocalEnvelopeEncryptor._keystream(enc_key, nonce, len(plaintext))
    ciphertext = bytes(a ^ b for a, b in zip(plaintext, stream, strict=True))
    blob = EncryptedBlob(
        algorithm=LocalEnvelopeEncryptor.legacy_algorithm,
        kdf=LocalEnvelopeEncryptor.kdf,
        salt=base64.b64encode(salt).decode(),
        nonce=base64.b64encode(nonce).decode(),
        ciphertext=base64.b64encode(ciphertext).decode(),
        mac=base64.b64encode(
            hmac.new(mac_key, nonce + ciphertext, hashlib.sha256).digest()
        ).decode(),
    )
    assert (
        LocalEnvelopeEncryptor(LocalEnvelopeEncryptor.development_default).decrypt(blob)
        == plaintext
    )
