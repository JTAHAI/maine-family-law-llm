"""Signed compact declarations, separate from PEFT and from executable admission.

Verifying a declaration does NOT verify its files, qualify a runtime, admit a
production model, or start a worker. This module has no signer or factory hook.
Existing provisioned trust/revocation/rollback handling is reused, not bypassed.
"""

from __future__ import annotations

import base64
import re
from typing import Annotated, Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import Field, StrictBool, StrictInt, model_validator

from legal.security.strict_json import strict_json_loads

from .admission import (
    AdmissionAuthority,
    AdmissionError,
    Closed,
    canonical,
    digest,
    now_utc,
    timestamp,
)

Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Identifier = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{2,79}$")]
LicenseIdentifier = Annotated[
    str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9.+_-]+$")
]
BYTE_LIMIT = 1_500_000_000


class CompactFile(Closed):
    path: str = Field(min_length=1, max_length=256)
    bytes: StrictInt = Field(ge=0, lt=BYTE_LIMIT)
    sha256: Hash
    role: Literal["weights", "tokenizer", "config", "notice", "runtime"]

    @model_validator(mode="after")
    def safe_relative_name(self):
        if self.role == "weights" and self.bytes == 0:
            raise ValueError("compact_empty_weights_invalid")
        if not re.fullmatch(r"[A-Za-z0-9_./+() -]+", self.path):
            raise ValueError("compact_inventory_path_invalid")
        for part in self.path.split("/"):
            if (
                part in {"", ".", ".."}
                or part != part.strip()
                or part.endswith(".")
                or part.split(".")[0].upper()
                in {
                    "CON",
                    "PRN",
                    "AUX",
                    "NUL",
                    *(f"COM{i}" for i in range(10)),
                    *(f"LPT{i}" for i in range(10)),
                }
            ):
                raise ValueError("compact_inventory_path_invalid")
        return self


class CompactInventory(Closed):
    schema_version: Literal["compact_file_inventory_v1"]
    kind: Literal["model", "runtime"]
    files: list[CompactFile] = Field(min_length=1, max_length=32_768)

    @model_validator(mode="after")
    def unique_bounded_inventory(self):
        names = [row.path.casefold() for row in self.files]
        if len(names) != len(set(names)) or sum(row.bytes for row in self.files) >= BYTE_LIMIT:
            raise ValueError("compact_inventory_duplicate_or_oversized")
        name_set = set(names)
        if any(
            "/".join(name.split("/")[:i]) in name_set
            for name in names
            for i in range(1, len(name.split("/")))
        ):
            raise ValueError("compact_inventory_file_directory_collision")
        weights = sum(row.role == "weights" for row in self.files)
        if self.kind == "model" and (weights != 1 or any(r.role == "runtime" for r in self.files)):
            raise ValueError("compact_model_inventory_invalid")
        if self.kind == "runtime" and (
            any(r.role not in {"runtime", "notice"} for r in self.files)
            or not any(r.role == "runtime" for r in self.files)
        ):
            raise ValueError("compact_runtime_inventory_invalid")
        return self


class FieldTask(Closed):
    kind: Literal["typed_source_field_review"]
    capability: Literal["evidence_review"]
    runtime_abi: Literal["compact_span_research_v1"]
    field_type: Literal["clock_time", "calendar_date", "money"]
    basis: Literal["source_field", "reported_event"]
    policy_sha256: Hash


class RankTask(Closed):
    kind: Literal["record_passage_ranking"]
    capability: Literal["evidence_review"]
    runtime_abi: Literal["compact_ranker_research_v1"]
    policy_sha256: Hash


class CompactRights(Closed):
    license_identifiers: list[LicenseIdentifier] = Field(min_length=1, max_length=32)
    rights_evidence_sha256: Hash
    notices_inventory_sha256: Hash
    redistribution_permitted: StrictBool


class CompactEvaluation(Closed):
    dataset_kind: Literal["synthetic", "unreviewed", "attorney_reviewed"]
    sample_count: StrictInt = Field(ge=1)
    report_sha256: Hash
    dataset_sha256: Hash
    # Missing human review must be representable without a fabricated hash.
    reviewer_approval_sha256: Hash | None

    @model_validator(mode="after")
    def reviewed_has_receipt(self):
        if self.dataset_kind == "attorney_reviewed" and not self.reviewer_approval_sha256:
            raise ValueError("compact_review_evidence_required")
        return self


class CompactRuntime(Closed):
    format: Literal["python_cpu_safetensors"]
    inventory_sha256: Hash
    qualification_report_sha256: Hash | None
    qualification_status: Literal["inventory_only", "qualified"]
    execution_device: Literal["cpu"]
    precision: Literal["fp32"]
    max_context_tokens: StrictInt = Field(ge=1, le=512)
    max_resident_bytes: StrictInt = Field(ge=1024, le=3 * 1024**3)

    @model_validator(mode="after")
    def qualified_has_receipt(self):
        if self.qualification_status == "qualified" and not self.qualification_report_sha256:
            raise ValueError("compact_runtime_qualification_receipt_required")
        return self


class CompactGrant(Closed):
    release_id: Identifier
    model_id: Identifier
    scope: Literal["development", "production"]
    task: Annotated[FieldTask | RankTask, Field(discriminator="kind")]
    model_inventory_sha256: Hash
    runtime: CompactRuntime
    rights: CompactRights
    evaluation: CompactEvaluation
    review_required: Literal[True]
    promotion_authority: Literal[False]

    @model_validator(mode="before")
    @classmethod
    def exact_safety_flags(cls, value):
        if (
            not isinstance(value, dict)
            or value.get("review_required") is not True
            or value.get("promotion_authority") is not False
        ):
            raise ValueError("compact_safety_flags_invalid")
        return value


class CompactCatalog(Closed):
    schema_version: Literal["compact_admission_declaration_v1"]
    catalog_id: str = Field(pattern=r"^compact-[a-z0-9_-]{1,70}$")
    sequence: StrictInt = Field(ge=1)
    published_at: str
    expires_at: str
    grants: list[CompactGrant] = Field(min_length=1, max_length=16)


class SignedCompactCatalog(Closed):
    payload: CompactCatalog
    key_id: Identifier
    signature_base64: str = Field(min_length=80, max_length=100)


def bounded_document(value, *, max_bytes):
    return strict_json_loads(
        value if isinstance(value, (bytes, str)) else canonical(value),
        max_bytes=max_bytes,
        max_depth=12,
        max_items=200_000,
        require_object=True,
    )


class CompactDeclarationVerifier:
    def __init__(self, authority: AdmissionAuthority):
        self.authority = authority

    def verify(self, envelope, *, model_inventory, runtime_inventory, expected_policies):
        """Validate declarations only. Expected policy hashes come from host code.

        Policy keys are ``typed_source_field_review:<field>:<basis>`` or
        ``record_passage_ranking``. A hash allowed for one field/basis does not
        authorize another. Never populate this map from imported/UI data.

        No caller may equate this result with executable/production admission.
        Model/runtime bytes and native closure require separate locked checks.
        """
        try:
            envelope = bounded_document(envelope, max_bytes=256_000)
            model_inventory = bounded_document(model_inventory, max_bytes=8_000_000)
            runtime_inventory = bounded_document(runtime_inventory, max_bytes=8_000_000)
            signed = SignedCompactCatalog.model_validate(envelope)
            model = CompactInventory.model_validate(model_inventory)
            runtime = CompactInventory.model_validate(runtime_inventory)
            if model.kind != "model" or runtime.kind != "runtime":
                raise AdmissionError("compact_inventory_kind_mismatch")
            selected_bytes = sum(r.bytes for r in (*model.files, *runtime.files))
            if selected_bytes >= BYTE_LIMIT:
                raise AdmissionError("compact_dependency_size_limit")
            trust = self.authority._trust()
            key = trust.trusted_keys.get(signed.key_id)
            if key is None or signed.key_id in trust.revoked_key_ids:
                raise AdmissionError("fast_interchange_signing_key_untrusted")
            if key.test_only and not self.authority.allow_test_keys:
                raise AdmissionError("fast_interchange_test_signer_forbidden")
            instant = now_utc()
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
            release_ids, model_ids = set(), set()
            for grant in payload.grants:
                if grant.release_id in release_ids or grant.model_id in model_ids:
                    raise AdmissionError("compact_duplicate_grant")
                release_ids.add(grant.release_id)
                model_ids.add(grant.model_id)
                if grant.release_id in trust.revoked_release_ids:
                    raise AdmissionError("fast_interchange_release_revoked")
                if grant.model_inventory_sha256 != digest(
                    model_inventory
                ) or grant.runtime.inventory_sha256 != digest(runtime_inventory):
                    raise AdmissionError("compact_inventory_binding_mismatch")
                policy_key = grant.task.kind
                if isinstance(grant.task, FieldTask):
                    policy_key += f":{grant.task.field_type}:{grant.task.basis}"
                if expected_policies.get(policy_key) != grant.task.policy_sha256:
                    raise AdmissionError("compact_policy_binding_mismatch")
                if not grant.rights.redistribution_permitted:
                    raise AdmissionError("compact_redistribution_not_permitted")
                if grant.scope == "production":
                    # A signed declaration is not actual model/native/installed
                    # qualification. No current compact runtime has that path.
                    raise AdmissionError("compact_production_qualification_not_implemented")
            # All checks precede state advancement; inspection_only retains the
            # original no-advancement semantics and catalog/trust rollback checks.
            self.authority._high_water(trust, payload, digest(envelope["payload"]))
            return dict(
                schema_version="compact_verified_declaration_v1",
                catalog_sha256=digest(envelope["payload"]),
                selected_bytes=selected_bytes,
                declaration_signature_verified=True,
                artifact_bytes_verified=False,
                runtime_qualified=False,
                production_admitted=False,
                runnable=False,
                review_required=True,
                grants=[g.model_dump() for g in payload.grants],
            )
        except AdmissionError:
            raise
        except (
            InvalidSignature,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            RecursionError,
        ) as exc:
            raise AdmissionError("compact_declaration_invalid") from exc
