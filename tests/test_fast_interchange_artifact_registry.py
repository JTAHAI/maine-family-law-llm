"""Cryptographic and loader-boundary tests with explicitly synthetic artifacts."""

from __future__ import annotations

import base64
import json
import os
import struct
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from test_fast_interchange_worker import _registry

from legal.fast_interchange.admission import AdmissionAuthority, AdmissionError, canonical, digest
from legal.fast_interchange.snapshot import (
    SnapshotError,
    VerifiedSnapshot,
    _read_model_json,
    validate_safetensors,
)
from legal.fast_interchange.worker import ArtifactFile, FastInterchangeError, HotSwapRegistry


@pytest.fixture
def admitted(tmp_path, monkeypatch):
    monkeypatch.setenv("MFL_VAULT_KEY_ROOT", str(tmp_path / "vault"))
    registry = _registry(tmp_path / "artifacts")
    releases = deepcopy(registry.release_document)
    for row in releases["releases"]:
        row["admission"] = "admitted_for_dev"
    registry = HotSwapRegistry.from_dicts(
        root=registry.root, releases=releases, artifacts=registry.artifact_document
    )
    now = datetime.now(UTC)
    past, future = (now - timedelta(days=1)).isoformat(), (now + timedelta(days=1)).isoformat()
    private_key = (
        Ed25519PrivateKey.generate()
    )  # Ephemeral test key; never exported or admitted publicly.
    trust = {
        "schema_version": "fast_interchange_admission_trust_v1",
        "revision": 1,
        "minimum_catalog_sequence": 1,
        "trusted_keys": {
            "fictional-test-key": {
                "public_key_base64": base64.b64encode(
                    private_key.public_key().public_bytes_raw()
                ).decode(),
                "not_before": past,
                "expires_at": future,
                "test_only": True,
            }
        },
        "revoked_key_ids": [],
        "revoked_release_ids": [],
        "approved_download_origins": [],
    }
    trust_path = tmp_path / "trust.json"
    trust_path.write_bytes(canonical(trust))
    authority = AdmissionAuthority(
        trust_path=trust_path, state_root=tmp_path / "state", allow_test_keys=True
    )
    grants = []
    for release in registry.releases.values():
        grants.append(
            {
                "release_id": release.release_id,
                "model_id": release.model_id,
                "capability": release.capability,
                "release_fingerprint": release.release_fingerprint,
                "scope": "development",
                "review_required": True,
                "promotion_authority": False,
                "licenses": {
                    "base": "SYNTHETIC-NOT-A-MODEL",
                    "tokenizer": "SYNTHETIC-NOT-A-MODEL",
                    "adapter": "SYNTHETIC-NOT-A-MODEL",
                    "rights_evidence_sha256": "d" * 64,
                    "redistribution_permitted": False,
                },
                "evaluation": {
                    "report_sha256": "e" * 64,
                    "dataset_kind": "synthetic",
                    "sample_count": 1,
                    "reviewer_approval_sha256": "f" * 64,
                },
                "compatibility": {
                    "runtime_abi": release.runtime_abi,
                    "torch_version": "test",
                    "transformers_version": "test",
                    "peft_version": "test",
                    "safetensors_version": "test",
                    "quantization": "fp32",
                    "max_context_tokens": 2048,
                    "max_new_tokens": 1024,
                    "max_resident_bytes": 1024 * 1024,
                    "prompt_template_sha256": release.prompt_template_sha256,
                },
            }
        )
    payload = {
        "schema_version": "fast_interchange_admission_catalog_v1",
        "catalog_id": "fictional-catalog",
        "sequence": 1,
        "published_at": past,
        "expires_at": future,
        "release_registry_sha256": digest(registry.release_document),
        "artifact_registry_sha256": digest(registry.artifact_document),
        "grants": grants,
    }

    def sign(value):
        return {
            "payload": deepcopy(value),
            "key_id": "fictional-test-key",
            "signature_base64": base64.b64encode(private_key.sign(canonical(value))).decode(),
        }

    envelope = sign(payload)
    return {
        "registry": replace(registry, admission_authority=authority, signed_catalog=envelope),
        "authority": authority,
        "trust": trust,
        "trust_path": trust_path,
        "payload": payload,
        "sign": sign,
        "envelope": envelope,
    }


def verify(fixture, envelope=None):
    registry = fixture["registry"]
    return fixture["authority"].verify(
        envelope or fixture["envelope"],
        releases=registry.release_document,
        artifacts=registry.artifact_document,
    )


def test_unsigned_self_declared_production_is_not_admission(admitted):
    registry = admitted["registry"]
    unsigned = replace(registry, admission_authority=None, signed_catalog=None)
    for model in unsigned.releases.values():
        with pytest.raises(FastInterchangeError, match="signed_admission_required"):
            unsigned.select(model.model_id, allow_test_only=False)


def test_real_signature_binds_both_registries_and_writes_encrypted_high_water(admitted):
    signed, grants = verify(admitted)
    assert signed.payload.sequence == 1 and len(grants) == 2
    path = admitted["authority"].state_path
    raw = path.read_bytes()
    assert b"fictional-catalog" not in raw
    before = path.stat().st_mtime_ns
    verify(admitted)
    assert (
        path.stat().st_mtime_ns == before
    )  # Reverification does not rewrite unchanged high water.
    for release in admitted["registry"].releases.values():
        assert admitted["registry"].select(release.model_id, allow_test_only=False) == release


@pytest.mark.parametrize(
    "fault",
    [
        "signature",
        "unknown_key",
        "extra",
        "expired",
        "future",
        "registry",
        "revoked_key",
        "revoked_release",
        "test_key",
        "production",
        "extra_grant",
        "capability",
        "license_missing",
        "zero_samples",
        "non_boolean",
    ],
)
def test_admission_fails_closed(admitted, fault):
    envelope, payload, trust = (
        deepcopy(admitted["envelope"]),
        deepcopy(admitted["payload"]),
        admitted["trust"],
    )
    if fault == "signature":
        envelope["signature_base64"] = base64.b64encode(bytes(64)).decode()
    elif fault == "unknown_key":
        envelope["key_id"] = "unknown-key"
    elif fault == "extra":
        envelope["grant_everything"] = True
    elif fault == "revoked_key":
        trust["revoked_key_ids"] = [envelope["key_id"]]
    elif fault == "revoked_release":
        trust["revoked_release_ids"] = [payload["grants"][0]["release_id"]]
    elif fault == "test_key":
        admitted["authority"].allow_test_keys = False
    else:
        if fault == "expired":
            payload["expires_at"] = "2000-01-01T00:00:00Z"
        if fault == "future":
            payload["published_at"] = "2100-01-01T00:00:00Z"
        if fault == "registry":
            payload["artifact_registry_sha256"] = "0" * 64
        if fault == "production":
            payload["grants"][0]["scope"] = "production"
        if fault == "extra_grant":
            payload["grants"][0]["run_tools"] = True
        if fault == "capability":
            payload["grants"][0]["capability"] = "judge_case"
        if fault == "license_missing":
            payload["grants"][0]["licenses"].pop("base")
        if fault == "zero_samples":
            payload["grants"][0]["evaluation"]["sample_count"] = 0
        if fault == "non_boolean":
            payload["grants"][0]["licenses"]["redistribution_permitted"] = 1
        envelope = admitted["sign"](payload)
    admitted["trust_path"].write_bytes(canonical(trust))
    with pytest.raises(AdmissionError):
        verify(admitted, envelope)


def test_rollback_conflict_revocation_and_trust_revision_are_rechecked(admitted):
    verify(admitted)
    payload = deepcopy(admitted["payload"])
    payload["sequence"] = 2
    verify(admitted, admitted["sign"](payload))
    with pytest.raises(AdmissionError, match="catalog_rollback"):
        verify(admitted)
    payload["expires_at"] = "2090-01-01T00:00:00Z"
    with pytest.raises(AdmissionError, match="sequence_conflict"):
        verify(admitted, admitted["sign"](payload))
    admitted["trust"]["revision"] = 3
    admitted["trust_path"].write_bytes(canonical(admitted["trust"]))
    payload["sequence"] = 3
    verify(admitted, admitted["sign"](payload))
    admitted["trust"]["revision"] = 2
    admitted["trust_path"].write_bytes(canonical(admitted["trust"]))
    with pytest.raises(AdmissionError, match="trust_rollback"):
        verify(admitted, admitted["sign"](payload))


def test_in_memory_descriptor_cannot_drift_from_signed_documents(admitted):
    registry = admitted["registry"]
    release = next(iter(registry.releases.values()))
    registry.releases[release.release_id] = replace(release, prompt_template_sha256="0" * 64)
    with pytest.raises(FastInterchangeError, match="admission_release_mismatch"):
        registry.select(release.model_id, allow_test_only=False)


@pytest.mark.parametrize(
    "path",
    [
        "../weights",
        "base/x:secret",
        "C:/file",
        "//server/share",
        "base/CON.json",
        "base/space. ",
        "base//x",
        "base/./x",
        "base/../x",
    ],
)
def test_artifact_paths_fail_closed(path):
    with pytest.raises(FastInterchangeError):
        ArtifactFile.from_dict({"path": path, "sha256": "a" * 64, "bytes": 1})


def test_unlisted_loader_file_is_rejected_before_loading(tmp_path):
    registry = _registry(tmp_path)
    (tmp_path / "base" / "custom_code.py").write_text("raise AssertionError('not executable')")
    with pytest.raises(FastInterchangeError, match="unlisted_loader_file"):
        next(iter(registry.bindings.values())).verify(tmp_path)


def test_loaded_snapshot_is_immutable_even_if_installed_original_changes(tmp_path):
    registry = _registry(tmp_path)
    binding = next(iter(registry.bindings.values()))
    snapshot = VerifiedSnapshot()
    try:
        root = snapshot.prepare(tmp_path, binding, strict_models=False, maximum_bytes=100000)
        original, copied = tmp_path / "base/model.bin", root / "base/model.bin"
        original.write_bytes(b"changed original")
        assert copied.read_bytes() == b"base"
        if os.name == "nt":
            with pytest.raises(OSError):
                copied.write_bytes(b"tamper")
            with pytest.raises(OSError):
                copied.unlink()
    finally:
        snapshot.close()
    assert not root.exists()


def test_standard_large_tokenizer_vocabulary_remains_strictly_bounded(tmp_path):
    tokenizer = tmp_path / "tokenizer.json"
    # More than the default strict JSON item limit, but below the dedicated
    # tokenizer budget used by ordinary Qwen-class vocabularies.
    tokenizer.write_text(
        json.dumps({"model": {"vocab": {f"token_{index}": index for index in range(210_000)}}}),
        encoding="utf-8",
    )
    value = _read_model_json(tokenizer)
    assert len(value["model"]["vocab"]) == 210_000


@pytest.mark.parametrize("fault", ["huge_header", "shape", "overlap", "extra", "trailing"])
def test_safetensors_bounds_are_checked_without_executing_model(tmp_path, fault):
    path = tmp_path / "tiny.safetensors"
    header = {"tensor": {"dtype": "F32", "shape": [1], "data_offsets": [0, 4]}}
    if fault == "shape":
        header["tensor"]["shape"] = [2**30]
    if fault == "overlap":
        header["second"] = deepcopy(header["tensor"])
    if fault == "extra":
        header["tensor"]["python"] = "not allowed"
    raw = canonical(header)
    path.write_bytes(
        struct.pack("<Q", 2**32 if fault == "huge_header" else len(raw))
        + raw
        + bytes(8 if fault == "trailing" else 4)
    )
    with pytest.raises((SnapshotError, ValueError)):
        validate_safetensors(path, maximum_bytes=1024)


def test_duplicate_registry_json_is_rejected(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"schema":"first","schema":"second"}')
    with pytest.raises(FastInterchangeError, match="registry_unavailable|registry_invalid"):
        HotSwapRegistry.load(root=tmp_path, release_registry=path, artifact_registry=path)


@pytest.mark.parametrize(
    "fault",
    ["architecture", "large_vocab", "allocation", "dynamic_config", "rank", "replicated_rank"],
)
def test_config_driven_allocations_fail_before_model_loading(fault):
    from legal.fast_interchange.snapshot import validate_model_budget

    config = {
        "model_type": "qwen2",
        "hidden_size": 64,
        "intermediate_size": 128,
        "num_hidden_layers": 2,
        "vocab_size": 1000,
        "num_attention_heads": 4,
    }
    adapter = {"peft_type": "LORA", "task_type": "CAUSAL_LM", "r": 4}
    budget = 16 * 1024**2
    validate_model_budget(config, adapter, maximum_bytes=budget)
    if fault == "architecture":
        config["model_type"] = "custom_python_architecture"
    if fault == "large_vocab":
        config["vocab_size"] = 2**32
    if fault == "allocation":
        budget = 1024
    if fault == "dynamic_config":
        config["configuration_files"] = ["outside.json"]
    if fault == "rank":
        adapter["r"] = 2**32
    if fault == "replicated_rank":
        adapter["rank_pattern"] = {"q_proj": 2**32}
    with pytest.raises(SnapshotError):
        validate_model_budget(config, adapter, maximum_bytes=budget)
