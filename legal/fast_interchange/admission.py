"""Independent, offline model admission. No private keys or automatic promotion.

The operator provisions public trust separately from downloaded catalogs.
Signatures bind both registries, capability, licenses, evaluation, and runtime
limits. Test keys and synthetic evaluation cannot admit production models.
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, ValidationError

from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path

from .fleet import FAST_INTERCHANGE_CAPABILITIES


class AdmissionError(ValueError):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def now_utc() -> datetime:
    return datetime.now(UTC)


def timestamp(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.utcoffset() is None:
            raise ValueError
        return result.astimezone(UTC)
    except (ValueError, TypeError) as exc:
        raise AdmissionError("fast_interchange_admission_time_invalid") from exc


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class PublicKey(Closed):
    public_key_base64: str = Field(min_length=40, max_length=64)
    not_before: str
    expires_at: str
    test_only: StrictBool


class TrustConfig(Closed):
    schema_version: Literal["fast_interchange_admission_trust_v1"]
    revision: StrictInt = Field(ge=1)
    minimum_catalog_sequence: StrictInt = Field(ge=1)
    trusted_keys: dict[str, PublicKey]
    revoked_key_ids: list[str]
    revoked_release_ids: list[str]
    approved_download_origins: list[str]


class Licenses(Closed):
    base: str = Field(min_length=1, max_length=160)
    tokenizer: str = Field(min_length=1, max_length=160)
    adapter: str = Field(min_length=1, max_length=160)
    rights_evidence_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    redistribution_permitted: StrictBool


class Evaluation(Closed):
    report_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    dataset_kind: Literal["synthetic", "unreviewed", "attorney_reviewed"]
    sample_count: StrictInt = Field(ge=1)
    reviewer_approval_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class Compatibility(Closed):
    runtime_abi: Literal["fast_interchange_hotswap_v1"]
    torch_version: str = Field(min_length=1, max_length=40)
    transformers_version: str = Field(min_length=1, max_length=40)
    peft_version: str = Field(min_length=1, max_length=40)
    safetensors_version: str = Field(min_length=1, max_length=40)
    quantization: Literal["fp32", "fp16", "bf16"]
    max_context_tokens: StrictInt = Field(ge=1, le=2048)
    max_new_tokens: StrictInt = Field(ge=1, le=1024)
    max_resident_bytes: StrictInt = Field(ge=1024, le=16 * 1024**3)
    prompt_template_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class AdmissionGrant(Closed):
    release_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{2,79}$")
    model_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{2,79}$")
    capability: str
    release_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    scope: Literal["development", "production"]
    licenses: Licenses
    evaluation: Evaluation
    compatibility: Compatibility
    review_required: Literal[True]
    promotion_authority: Literal[False]


class CatalogPayload(Closed):
    schema_version: Literal["fast_interchange_admission_catalog_v1"]
    catalog_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{2,79}$")
    sequence: StrictInt = Field(ge=1)
    published_at: str
    expires_at: str
    release_registry_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    artifact_registry_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    grants: list[AdmissionGrant] = Field(min_length=1, max_length=64)


class SignedCatalog(Closed):
    payload: CatalogPayload
    key_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{2,79}$")
    signature_base64: str = Field(min_length=80, max_length=100)


class AdmissionAuthority:
    def __init__(
        self,
        *,
        trust_path: Path,
        state_root: Path,
        allow_test_keys: bool = False,
        record_high_water: bool = True,
    ):
        self.trust_path = Path(trust_path)
        self.state_path = Path(state_root) / "admission-high-water.json.enc"
        self.lock_path = Path(state_root) / ".admission.lock"
        self.allow_test_keys = allow_test_keys
        self.record_high_water = record_high_water
        self.encryptor = LocalEnvelopeEncryptor("local-development-key-change-me")

    def inspection_only(self) -> AdmissionAuthority:
        """Check current trust and rollback bounds without admitting an update.

        Import inspection must not obsolete the active catalog before the user
        approves activation. Worker/host construction always records admission.
        """
        return AdmissionAuthority(
            trust_path=self.trust_path,
            state_root=self.state_path.parent,
            allow_test_keys=self.allow_test_keys,
            record_high_water=False,
        )

    def _trust(self) -> TrustConfig:
        try:
            return TrustConfig.model_validate(
                strict_json_load_path(self.trust_path, max_bytes=256 * 1024, require_object=True)
            )
        except (OSError, ValueError) as exc:
            raise AdmissionError("fast_interchange_trust_unavailable") from exc

    def verify(
        self, envelope: dict[str, Any], *, releases: dict[str, Any], artifacts: dict[str, Any]
    ) -> tuple[SignedCatalog, dict[str, AdmissionGrant]]:
        try:
            signed = SignedCatalog.model_validate(envelope)
            trust = self._trust()
            key = trust.trusted_keys.get(signed.key_id)
            instant = now_utc()
            if not key or signed.key_id in trust.revoked_key_ids:
                raise AdmissionError("fast_interchange_signing_key_untrusted")
            if key.test_only and not self.allow_test_keys:
                raise AdmissionError("fast_interchange_test_signer_forbidden")
            if not timestamp(key.not_before) <= instant < timestamp(key.expires_at):
                raise AdmissionError("fast_interchange_signing_key_expired")
            payload = signed.payload
            if not timestamp(payload.published_at) <= instant < timestamp(payload.expires_at):
                raise AdmissionError("fast_interchange_catalog_expired_or_future")
            Ed25519PublicKey.from_public_bytes(
                base64.b64decode(key.public_key_base64, validate=True)
            ).verify(
                base64.b64decode(signed.signature_base64, validate=True),
                canonical(envelope["payload"]),
            )
            if payload.release_registry_sha256 != digest(
                releases
            ) or payload.artifact_registry_sha256 != digest(artifacts):
                raise AdmissionError("fast_interchange_catalog_registry_mismatch")
            grants = {item.release_id: item for item in payload.grants}
            if len(grants) != len(payload.grants):
                raise AdmissionError("fast_interchange_duplicate_admission")
            for grant in grants.values():
                if grant.capability not in FAST_INTERCHANGE_CAPABILITIES:
                    raise AdmissionError("fast_interchange_admission_capability_invalid")
                if grant.release_id in trust.revoked_release_ids:
                    raise AdmissionError("fast_interchange_release_revoked")
                if grant.scope == "production" and (
                    key.test_only or grant.evaluation.dataset_kind != "attorney_reviewed"
                ):
                    raise AdmissionError("fast_interchange_production_evidence_missing")
            self._high_water(trust, payload, digest(envelope["payload"]))
            return signed, grants
        except AdmissionError:
            raise
        except (InvalidSignature, ValueError, TypeError, KeyError, ValidationError) as exc:
            raise AdmissionError("fast_interchange_admission_invalid") from exc

    def _high_water(self, trust: TrustConfig, payload: CatalogPayload, catalog_hash: str) -> None:
        try:
            with exclusive_file_lock(self.lock_path):
                state: dict[str, Any] = {
                    "schema": "fi_admission_high_water_v1",
                    "trust_revision": 0,
                    "catalogs": {},
                }
                if self.state_path.exists():
                    state = self.encryptor.decrypt_json(
                        strict_json_load_path(
                            self.state_path, max_bytes=1024 * 1024, require_object=True
                        )
                    )
                if (
                    state.get("schema") != "fi_admission_high_water_v1"
                    or trust.revision < state["trust_revision"]
                ):
                    raise AdmissionError("fast_interchange_trust_rollback")
                prior = state["catalogs"].get(payload.catalog_id, {"sequence": 0, "sha256": ""})
                if payload.sequence < max(trust.minimum_catalog_sequence, prior["sequence"]):
                    raise AdmissionError("fast_interchange_catalog_rollback")
                if payload.sequence == prior["sequence"] and catalog_hash != prior["sha256"]:
                    raise AdmissionError("fast_interchange_catalog_sequence_conflict")
                if len(state["catalogs"]) >= 64 and payload.catalog_id not in state["catalogs"]:
                    raise AdmissionError("fast_interchange_catalog_capacity")
                if not self.record_high_water:
                    return
                if trust.revision == state["trust_revision"] and prior == {
                    "sequence": payload.sequence,
                    "sha256": catalog_hash,
                }:
                    return
                state["trust_revision"] = trust.revision
                state["catalogs"][payload.catalog_id] = {
                    "sequence": payload.sequence,
                    "sha256": catalog_hash,
                }
                atomic_write_bytes(
                    self.state_path, canonical(self.encryptor.encrypt_json(state)), mode=0o600
                )
        except AdmissionError:
            raise
        except Exception as exc:
            raise AdmissionError("fast_interchange_admission_state_unavailable") from exc


__all__ = [
    "AdmissionAuthority",
    "AdmissionError",
    "AdmissionGrant",
    "SignedCatalog",
    "canonical",
    "digest",
]
