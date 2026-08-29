"""Signed, external jurisdiction-pack manifests and encrypted matter selection.

Packs declare the hashes of authority, citation, form, procedure, terminology,
and safety-policy components.  The workbench verifies a pack's externally
provisioned Ed25519 signature before it can be selected for a matter.  A pack
never decides jurisdiction, imports authority into the application, or makes a
filing-ready claim.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from legal.evals.external_eval_root import ExternalEvalRootError, resolve_external_eval_root
from legal.security.durable_io import atomic_write_bytes
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,79}$")
_JURISDICTION = re.compile(r"^[A-Z]{2}(?:-[A-Z0-9]{2,12})+$")
_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]{1,48})?$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_COMPONENTS = {
    "authority_manifest_sha256",
    "citation_profile_sha256",
    "forms_catalog_sha256",
    "procedure_profile_sha256",
    "terminology_profile_sha256",
    "safety_policy_sha256",
    "index_snapshot_sha256",
}
_REQUIRED_CONTROLS = {
    "local_only": True,
    "review_required": True,
    "safety_policy_required": True,
    "jurisdiction_decision_prohibited": True,
}
_MAX_PACKS = 100


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else _canonical(value)).hexdigest()


def _safe_id(value: Any, code: str) -> str:
    text = str(value or "").strip()
    if not _ID.fullmatch(text):
        raise JurisdictionPackError(code)
    return text


def _load_object(path: Path, *, max_bytes: int = 512 * 1024) -> dict[str, Any] | None:
    try:
        return strict_json_load_path(path, max_bytes=max_bytes, require_object=True)
    except Exception:
        return None


def signable_payload(pack: dict[str, Any]) -> bytes:
    """Return the exact pack declaration covered by the detached signature."""

    return _canonical(
        {
            "schema_version": pack.get("schema_version"),
            "pack_id": pack.get("pack_id"),
            "jurisdiction": pack.get("jurisdiction"),
            "version": pack.get("version"),
            "components": pack.get("components"),
            "controls": pack.get("controls"),
            "reference_only": pack.get("reference_only", False),
        }
    )


class JurisdictionPackError(ValueError):
    pass


@dataclass(frozen=True)
class JurisdictionPackStatus:
    pack_id: str
    jurisdiction: str
    version: str
    status: str
    signature_verified: bool
    component_hashes: dict[str, str] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)
    review_required: bool = True
    jurisdiction_decision_prohibited: bool = True
    reference_only: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "pack_id": self.pack_id,
            "jurisdiction": self.jurisdiction,
            "version": self.version,
            "status": self.status,
            "signature_verified": self.signature_verified,
            "component_hashes": dict(self.component_hashes),
            "source_drill_down": [{"component": name, "sha256": value} for name, value in sorted(self.component_hashes.items())],
            "blockers": sorted(set(self.blockers)),
            "review_required": self.review_required,
            "jurisdiction_decision_prohibited": self.jurisdiction_decision_prohibited,
            "reference_only": self.reference_only,
        }


class JurisdictionPackCatalog:
    """Read only signed metadata from an external jurisdiction-pack root."""

    def __init__(self, root: str | Path, *, project_root: str | Path = ".") -> None:
        try:
            self.root = resolve_external_eval_root(root, project_root=project_root, create=False)
        except ExternalEvalRootError as exc:
            raise JurisdictionPackError(exc.code) from exc
        self.packs_root = self.root / "packs"
        self.trust_path = self.root / "jurisdiction_pack_trust.json"

    def list_verified(self) -> list[JurisdictionPackStatus]:
        if not self.packs_root.is_dir():
            return []
        rows: list[JurisdictionPackStatus] = []
        for path in sorted(self.packs_root.glob("*.json"))[:_MAX_PACKS]:
            payload = _load_object(path)
            rows.append(self.verify(payload or {}))
        return rows

    def get_verified(self, pack_id: str) -> JurisdictionPackStatus:
        safe_id = _safe_id(pack_id, "jurisdiction_pack_id_invalid")
        path = self.packs_root / f"{safe_id}.json"
        payload = _load_object(path)
        if payload is None:
            raise JurisdictionPackError("jurisdiction_pack_not_found")
        return self.verify(payload)

    def verify(self, pack: dict[str, Any]) -> JurisdictionPackStatus:
        blockers: list[str] = []
        pack_id = str(pack.get("pack_id") or "")
        jurisdiction = str(pack.get("jurisdiction") or "")
        version = str(pack.get("version") or "")
        reference_only = pack.get("reference_only", False)
        if pack.get("schema_version") != "jurisdiction_pack_v1":
            blockers.append("jurisdiction_pack_schema_unsupported")
        if not _ID.fullmatch(pack_id):
            blockers.append("jurisdiction_pack_id_invalid")
        if not _JURISDICTION.fullmatch(jurisdiction):
            blockers.append("jurisdiction_pack_jurisdiction_invalid")
        if not _VERSION.fullmatch(version):
            blockers.append("jurisdiction_pack_version_invalid")
        if type(reference_only) is not bool:
            blockers.append("jurisdiction_pack_reference_only_boolean_required")
        components = pack.get("components") if isinstance(pack.get("components"), dict) else {}
        if set(components) != _REQUIRED_COMPONENTS:
            blockers.append("jurisdiction_pack_components_incomplete")
        hashes: dict[str, str] = {}
        for name in _REQUIRED_COMPONENTS:
            value = str(components.get(name) or "").casefold()
            if not _HASH.fullmatch(value):
                blockers.append(f"jurisdiction_pack_component_hash_invalid:{name}")
            else:
                hashes[name] = value
        controls = pack.get("controls") if isinstance(pack.get("controls"), dict) else {}
        if set(controls) != set(_REQUIRED_CONTROLS):
            blockers.append("jurisdiction_pack_controls_incomplete")
        for name, required in _REQUIRED_CONTROLS.items():
            if controls.get(name) is not required:
                blockers.append(f"jurisdiction_pack_control_required:{name}")
        signature_verified, signature_blockers = self._verify_signature(pack)
        blockers.extend(signature_blockers)
        return JurisdictionPackStatus(
            pack_id=pack_id[:80],
            jurisdiction=jurisdiction[:32],
            version=version[:64],
            status=("reference_verified_not_selectable" if reference_only and not blockers else "verified" if not blockers else "blocked"),
            signature_verified=signature_verified,
            component_hashes=hashes,
            blockers=blockers,
            reference_only=bool(reference_only),
        )

    def _verify_signature(self, pack: dict[str, Any]) -> tuple[bool, list[str]]:
        trust = _load_object(self.trust_path, max_bytes=256 * 1024)
        blockers: list[str] = []
        if trust is None or trust.get("schema_version") != "jurisdiction_pack_trust_v1":
            blockers.append("jurisdiction_pack_trust_config_unavailable")
            trust = {}
        keys = trust.get("trusted_keys") if isinstance(trust.get("trusted_keys"), dict) else {}
        signature = pack.get("signature") if isinstance(pack.get("signature"), dict) else {}
        key_id = str(signature.get("key_id") or "")
        key = keys.get(key_id)
        if not isinstance(key, str) or not key:
            blockers.append("jurisdiction_pack_signing_key_untrusted")
        else:
            try:
                public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(key, validate=True))
                public_key.verify(base64.b64decode(str(signature.get("signature") or ""), validate=True), signable_payload(pack))
            except (ValueError, InvalidSignature):
                blockers.append("jurisdiction_pack_signature_invalid")
        return not blockers, blockers


class JurisdictionPackSelectionStore:
    """Encrypted, tenant-and-matter-scoped record of an explicit pack selection."""

    def __init__(self, root: str | Path | None = None, *, encryption_key: str | None = None) -> None:
        default = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "MaineFamilyLawLLM" / "jurisdiction-pack-selections"
        self.root = Path(root or os.environ.get("MFL_JURISDICTION_PACK_STATE_ROOT") or default).resolve()
        self.encryptor = LocalEnvelopeEncryptor(encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me")

    def _path(self, tenant_id: str, matter_id: str) -> Path:
        return self.root / f"{_digest({'tenant_id': tenant_id, 'matter_id': matter_id})[:48]}.json.enc"

    def _load(self, tenant_id: str, matter_id: str) -> dict[str, Any]:
        path = self._path(tenant_id, matter_id)
        if not path.is_file():
            return {"schema_version": "jurisdiction_pack_selection_state_v1", "tenant_id": tenant_id, "matter_id": matter_id, "selection": None, "audit": []}
        try:
            state = self.encryptor.decrypt_json(strict_json_load_path(path, max_bytes=1024 * 1024, require_object=True))
        except Exception as exc:
            raise JurisdictionPackError("jurisdiction_pack_selection_unavailable") from exc
        if state.get("tenant_id") != tenant_id or state.get("matter_id") != matter_id:
            raise JurisdictionPackError("jurisdiction_pack_selection_scope_mismatch")
        return state

    def select(self, *, tenant_id: str, matter_id: str, pack: JurisdictionPackStatus, actor_role: str) -> dict[str, Any]:
        tenant = _safe_id(tenant_id, "jurisdiction_pack_tenant_id_invalid")
        matter = _safe_id(matter_id, "jurisdiction_pack_matter_id_invalid")
        if actor_role not in {"reviewer", "attorney", "admin"}:
            raise JurisdictionPackError("jurisdiction_pack_reviewer_role_required")
        if pack.reference_only:
            raise JurisdictionPackError("jurisdiction_pack_reference_only_not_selectable")
        if pack.status != "verified" or not pack.signature_verified:
            raise JurisdictionPackError("jurisdiction_pack_verification_required")
        state = self._load(tenant, matter)
        receipt = {
            "selection_id": f"jps_{_digest({'tenant': tenant, 'matter': matter, 'pack': pack.pack_id, 'at': _now()})[:20]}",
            "pack_id": pack.pack_id,
            "jurisdiction": pack.jurisdiction,
            "version": pack.version,
            "component_manifest_hash": _digest(pack.component_hashes),
            "selected_at": _now(),
            "actor_role": actor_role,
            "review_required": True,
            "jurisdiction_decision_prohibited": True,
        }
        previous = str((state.get("audit") or [{}])[-1].get("event_hash") or "")
        event_basis = {"event": "jurisdiction_pack_selected", "selection_id": receipt["selection_id"], "at": receipt["selected_at"], "previous_hash": previous}
        state["selection"] = receipt
        state["audit"] = [*list(state.get("audit") or []), {**event_basis, "event_hash": _digest(event_basis)}][-_MAX_PACKS:]
        path = self._path(tenant, matter)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(path, _canonical(self.encryptor.encrypt_json(state)), mode=0o600)
        return self.status(tenant_id=tenant, matter_id=matter)

    def status(self, *, tenant_id: str, matter_id: str) -> dict[str, Any]:
        tenant = _safe_id(tenant_id, "jurisdiction_pack_tenant_id_invalid")
        matter = _safe_id(matter_id, "jurisdiction_pack_matter_id_invalid")
        state = self._load(tenant, matter)
        selection = state.get("selection")
        return {
            "status": "selected_review_required" if isinstance(selection, dict) else "not_selected",
            "selection": selection if isinstance(selection, dict) else None,
            "audit_event_count": len(state.get("audit") or []),
            "review_required": True,
            "jurisdiction_decision_prohibited": True,
            "filing_ready": False,
        }


class FictionalSecondStateReferencePack:
    """Build a signed non-production pack solely to exercise the pack boundary.

    The caller must supply its own private key.  This class never creates or
    persists a signing credential, provides legal content, or treats the
    fictional jurisdiction as a supported state.
    """

    @staticmethod
    def build(*, private_key: Ed25519PrivateKey, key_id: str, pack_id: str = "aurora_reference") -> dict[str, Any]:
        safe_key = _safe_id(key_id, "jurisdiction_pack_key_id_invalid")
        safe_pack = _safe_id(pack_id, "jurisdiction_pack_id_invalid")
        components = {name: _digest(f"fictional-reference:{safe_pack}:{name}") for name in sorted(_REQUIRED_COMPONENTS)}
        pack = {
            "schema_version": "jurisdiction_pack_v1",
            "pack_id": safe_pack,
            "jurisdiction": "XX-AURORA",
            "version": "0.0.1-reference",
            "components": components,
            "controls": dict(_REQUIRED_CONTROLS),
            "reference_only": True,
            "fictional_reference": True,
        }
        pack["signature"] = {
            "key_id": safe_key,
            "signature": base64.b64encode(private_key.sign(signable_payload(pack))).decode("ascii"),
        }
        return pack


__all__ = [
    "JurisdictionPackCatalog",
    "JurisdictionPackError",
    "FictionalSecondStateReferencePack",
    "JurisdictionPackSelectionStore",
    "JurisdictionPackStatus",
    "signable_payload",
]
