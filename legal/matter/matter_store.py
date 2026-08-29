from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict
from pathlib import Path

from legal.matter.models import Matter, MatterDocument
from legal.security.durable_io import atomic_write_bytes
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.matter_key_hierarchy import MatterKeyHierarchy, MatterKeyHierarchyError
from legal.security.matter_unlock import MatterUnlockBroker, MatterUnlockError


class MatterStoreError(ValueError):
    pass


class MatterStore:
    """External encrypted matter-store adapter.

    It refuses repo-local runtime stores and persists document payloads as encrypted
    envelopes. The source repository should only contain code/tests, never private
    matter documents or plaintext derived work product.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        project_root: str | Path | None = None,
        encryption_key: str | None = None,
    ):
        self.root = Path(root).resolve()
        self.project_root = Path(project_root).resolve() if project_root else None
        self._validate_external_root()
        key = encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me"
        self.encryptor = LocalEnvelopeEncryptor(key)
        # New matter/document envelopes use an independently wrapped data key.
        # ``encryptor`` stays available only for safe legacy-read migration and
        # existing callers that have not yet moved their sidecars.
        self.key_hierarchy = MatterKeyHierarchy(self.root, root_secret=self.encryptor.passphrase)
        self.unlock_broker = MatterUnlockBroker(self.root, root_secret=self.encryptor.passphrase)

    @property
    def encryption_key_id(self) -> str:
        return hashlib.sha256(self.encryptor.passphrase).hexdigest()[:16]

    def _envelope_metadata(self, *, payload_kind: str, record_id: str) -> dict[str, str]:
        return {
            "encryption_algorithm": self.encryptor.algorithm,
            "encryption_kdf": self.encryptor.kdf,
            "encryption_key_id": self.encryption_key_id,
            "encryption_version": "1",
            "payload_kind": payload_kind,
            "record_id": record_id,
        }

    def _matter_key_envelope_metadata(
        self, *, tenant_id: str, matter_id: str, payload_kind: str, record_id: str
    ) -> dict[str, str]:
        status = self.key_hierarchy.ensure(tenant_id, matter_id)
        return {
            "encryption_algorithm": "aes-256-gcm",
            "encryption_kdf": "dpapi_root_wrapped_matter_data_key",
            "encryption_key_id": str(status.get("active_key_id") or ""),
            "encryption_version": "2",
            "payload_kind": payload_kind,
            "record_id": record_id,
        }

    @staticmethod
    def _is_matter_key_envelope(payload: object) -> bool:
        return isinstance(payload, dict) and payload.get("schema_version") == "matter_key_hierarchy_v1"

    def _scope_for_path(self, path: Path) -> tuple[str, str]:
        """Derive the tenant/matter scope from a canonical external-store path."""

        directory = path if path.is_dir() else path.parent
        try:
            relative = directory.resolve().relative_to(self.root)
        except ValueError as exc:
            raise MatterStoreError("matter_key_scope_outside_store") from exc
        if len(relative.parts) < 2:
            raise MatterStoreError("matter_key_scope_unavailable")
        return relative.parts[-2], relative.parts[-1]

    def _hierarchy_for_path(
        self, *, path: Path, tenant_id: str, matter_id: str
    ) -> MatterKeyHierarchy:
        """Locate the canonical hierarchy when a caller opened one matter directly.

        Security dashboards sometimes construct a store around an individual
        matter directory rather than its tenant store root.  Only reuse a
        hierarchy after finding its exact scope file; never create probe files
        in ancestor directories.
        """

        candidates = [self.root, *path.resolve().parents]
        seen: set[Path] = set()
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            state_path = candidate / ".mfl-key-hierarchy" / tenant_id / f"{matter_id}.json"
            if state_path.is_file():
                return MatterKeyHierarchy(candidate, root_secret=self.encryptor.passphrase)
        return self.key_hierarchy

    def _unlock_broker_for_path(
        self, *, path: Path, tenant_id: str, matter_id: str
    ) -> MatterUnlockBroker:
        """Locate a direct-open matter's encrypted unlock policy without writes."""

        candidates = [self.root, *path.resolve().parents]
        seen: set[Path] = set()
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            policy_path = candidate / ".mfl-matter-unlock" / tenant_id / f"{matter_id}.json.enc"
            if policy_path.is_file():
                return MatterUnlockBroker(candidate, root_secret=self.encryptor.passphrase)
        return self.unlock_broker

    def encrypt_matter_payload(
        self, *, tenant_id: str, matter_id: str, purpose: str, payload: dict
    ) -> dict[str, str]:
        try:
            self.unlock_broker.assert_unlocked(tenant_id, matter_id)
            return self.key_hierarchy.encrypt_json(tenant_id, matter_id, purpose, payload)
        except (MatterKeyHierarchyError, MatterUnlockError) as exc:
            raise MatterStoreError(str(exc)) from exc

    def decrypt_matter_payload(
        self,
        *,
        tenant_id: str,
        matter_id: str,
        purpose: str,
        envelope: dict,
        hierarchy: MatterKeyHierarchy | None = None,
        unlock_broker: MatterUnlockBroker | None = None,
    ) -> dict:
        try:
            (unlock_broker or self.unlock_broker).assert_unlocked(tenant_id, matter_id)
            return (hierarchy or self.key_hierarchy).decrypt_json(tenant_id, matter_id, purpose, envelope)
        except (MatterKeyHierarchyError, MatterUnlockError) as exc:
            raise MatterStoreError(str(exc)) from exc

    def matter_key_status(
        self, *, path: str | Path, tenant_id: str, matter_id: str
    ) -> dict:
        """Return non-secret hierarchy status for one already-scoped matter."""

        try:
            hierarchy = self._hierarchy_for_path(
                path=Path(path), tenant_id=tenant_id, matter_id=matter_id
            )
            return hierarchy.status(tenant_id, matter_id)
        except MatterKeyHierarchyError as exc:
            raise MatterStoreError(str(exc)) from exc

    def manage_matter_key(
        self,
        *,
        path: str | Path,
        tenant_id: str,
        matter_id: str,
        operation: str,
        recovery_secret: str | None = None,
        approved: bool = False,
        confirmation: str = "",
    ) -> dict:
        """Perform one explicit, auditable hierarchy operation.

        Only callers that have already proved role, tenant, matter, session,
        and CSRF scope should reach this adapter.  It never returns key or
        recovery material.
        """

        try:
            hierarchy = self._hierarchy_for_path(
                path=Path(path), tenant_id=tenant_id, matter_id=matter_id
            )
            if operation == "enroll_recovery":
                return hierarchy.enroll_recovery(tenant_id, matter_id, str(recovery_secret or ""))
            if operation == "rotate":
                return hierarchy.rotate(tenant_id, matter_id, recovery_secret=recovery_secret)
            if operation == "recover_root_wrapping":
                return hierarchy.recover_root_wrapping(tenant_id, matter_id, str(recovery_secret or ""))
            if operation == "revoke":
                return hierarchy.revoke(tenant_id, matter_id)
            if operation == "cryptographic_delete":
                return hierarchy.cryptographic_delete(
                    tenant_id,
                    matter_id,
                    approved=approved,
                    confirmation=confirmation,
                )
            raise MatterStoreError("matter_key_operation_unavailable")
        except MatterKeyHierarchyError as exc:
            raise MatterStoreError(str(exc)) from exc

    def matter_unlock_status(self, *, path: str | Path, tenant_id: str, matter_id: str) -> dict:
        try:
            broker = self._unlock_broker_for_path(
                path=Path(path), tenant_id=tenant_id, matter_id=matter_id
            )
            return broker.status(tenant_id, matter_id)
        except MatterUnlockError as exc:
            raise MatterStoreError(str(exc)) from exc

    def configure_matter_unlock(
        self,
        *,
        path: str | Path,
        tenant_id: str,
        matter_id: str,
        enabled: bool,
        fallback_policy: str,
        approved: bool,
    ) -> dict:
        try:
            broker = self._unlock_broker_for_path(
                path=Path(path), tenant_id=tenant_id, matter_id=matter_id
            )
            return broker.configure(
                tenant_id,
                matter_id,
                enabled=enabled,
                fallback_policy=fallback_policy,
                approved=approved,
            )
        except MatterUnlockError as exc:
            raise MatterStoreError(str(exc)) from exc

    def verify_matter_unlock(
        self,
        *,
        path: str | Path,
        tenant_id: str,
        matter_id: str,
        approved: bool,
    ) -> dict:
        try:
            broker = self._unlock_broker_for_path(
                path=Path(path), tenant_id=tenant_id, matter_id=matter_id
            )
            return broker.verify(tenant_id, matter_id, approved=approved)
        except MatterUnlockError as exc:
            raise MatterStoreError(str(exc)) from exc

    def lock_matter_unlock(self, *, path: str | Path, tenant_id: str, matter_id: str) -> dict:
        try:
            broker = self._unlock_broker_for_path(
                path=Path(path), tenant_id=tenant_id, matter_id=matter_id
            )
            return broker.lock(tenant_id, matter_id)
        except MatterUnlockError as exc:
            raise MatterStoreError(str(exc)) from exc

    def _validate_external_root(self) -> None:
        blocked_names = {
            "official_authority_store",
            "parsed_authority_store",
            "matter_store",
            "eval_store",
            "embedding_store",
            "audit_store",
            "model_registry",
        }
        if self.root.name in blocked_names and self.project_root and self.root.is_relative_to(self.project_root):
            raise MatterStoreError("canonical runtime stores must not live inside the source repository")
        if self.project_root and self.root.is_relative_to(self.project_root):
            raise MatterStoreError("matter store must be outside the source repository")

    def create_matter(self, matter: Matter) -> Path:
        matter_dir = self.root / matter.tenant_id / matter.matter_id
        matter_dir.mkdir(parents=True, exist_ok=True)
        legacy_metadata_path = matter_dir / "matter.json"
        if legacy_metadata_path.exists():
            # Never erase a legacy matter while creating a new encrypted
            # envelope.  Migration is an explicit, separately audited action.
            raise MatterStoreError("legacy_matter_metadata_exists")
        metadata_path = matter_dir / "matter.json.enc"
        payload = asdict(matter)
        payload["storage_encryption_status"] = "encrypted_local_envelope"
        payload["encryption_metadata"] = self._matter_key_envelope_metadata(
            tenant_id=matter.tenant_id,
            matter_id=matter.matter_id,
            payload_kind="matter",
            record_id=matter.matter_id,
        )
        envelope = self.encrypt_matter_payload(
            tenant_id=matter.tenant_id,
            matter_id=matter.matter_id,
            purpose="matter_metadata",
            payload=payload,
        )
        atomic_write_bytes(metadata_path, json.dumps(envelope, indent=2, sort_keys=True).encode("utf-8"))
        return matter_dir

    def load_matter(
        self,
        matter_path: str | Path,
        *,
        tenant_id: str | None = None,
        matter_id: str | None = None,
    ) -> dict:
        path = Path(matter_path)
        if path.is_dir():
            encrypted = path / "matter.json.enc"
            legacy = path / "matter.json"
            if encrypted.exists():
                path = encrypted
            elif legacy.exists():
                path = legacy
        payload = json.loads(path.read_text(encoding="utf-8"))
        if str(path).endswith(".enc"):
            if self._is_matter_key_envelope(payload):
                if not tenant_id or not matter_id:
                    tenant_id, matter_id = self._scope_for_path(path)
                return self.decrypt_matter_payload(
                    tenant_id=tenant_id,
                    matter_id=matter_id,
                    purpose="matter_metadata",
                    envelope=payload,
                    hierarchy=self._hierarchy_for_path(
                        path=path, tenant_id=tenant_id, matter_id=matter_id
                    ),
                    unlock_broker=self._unlock_broker_for_path(
                        path=path, tenant_id=tenant_id, matter_id=matter_id
                    ),
                )
            if not tenant_id or not matter_id:
                tenant_id, matter_id = self._scope_for_path(path)
            try:
                self._unlock_broker_for_path(
                    path=path, tenant_id=tenant_id, matter_id=matter_id
                ).assert_unlocked(tenant_id, matter_id)
            except MatterUnlockError as exc:
                raise MatterStoreError(str(exc)) from exc
            return self.encryptor.decrypt_json(payload)
        return payload

    def store_document(self, document: MatterDocument) -> Path:
        matter_dir = self.root / document.tenant_id / document.matter_id
        matter_dir.mkdir(parents=True, exist_ok=True)
        document_path = matter_dir / f"{document.document_id}.json.enc"
        payload = asdict(document)
        payload["storage_encryption_status"] = "encrypted_local_envelope"
        payload["encryption_metadata"] = self._matter_key_envelope_metadata(
            tenant_id=document.tenant_id,
            matter_id=document.matter_id,
            payload_kind="document",
            record_id=document.document_id,
        )
        envelope = self.encrypt_matter_payload(
            tenant_id=document.tenant_id,
            matter_id=document.matter_id,
            purpose="matter_document",
            payload=payload,
        )
        atomic_write_bytes(document_path, json.dumps(envelope, indent=2, sort_keys=True).encode("utf-8"))
        self._append_manifest(document, document_path)
        return document_path

    def load_document(self, document_path: str | Path) -> dict:
        path = Path(document_path)
        envelope = json.loads(path.read_text(encoding="utf-8"))
        if self._is_matter_key_envelope(envelope):
            tenant_id, matter_id = self._scope_for_path(path)
            return self.decrypt_matter_payload(
                tenant_id=tenant_id,
                matter_id=matter_id,
                purpose="matter_document",
                envelope=envelope,
                hierarchy=self._hierarchy_for_path(
                    path=path, tenant_id=tenant_id, matter_id=matter_id
                ),
                unlock_broker=self._unlock_broker_for_path(
                    path=path, tenant_id=tenant_id, matter_id=matter_id
                ),
            )
        tenant_id, matter_id = self._scope_for_path(path)
        try:
            self._unlock_broker_for_path(
                path=path, tenant_id=tenant_id, matter_id=matter_id
            ).assert_unlocked(tenant_id, matter_id)
        except MatterUnlockError as exc:
            raise MatterStoreError(str(exc)) from exc
        return self.encryptor.decrypt_json(envelope)

    def _append_manifest(self, document: MatterDocument, document_path: Path) -> None:
        manifest_path = document_path.parent / "documents_manifest.jsonl"
        row = {
            "document_id": document.document_id,
            "matter_id": document.matter_id,
            "tenant_id": document.tenant_id,
            "filename": document.filename,
            "sha256": document.sha256,
            "data_class": document.data_class,
            "retention_policy_id": document.retention_policy_id,
            "private_data_allowed_for_training": False,
            "encrypted_path": document_path.name,
            "storage_encryption_status": "encrypted_local_envelope",
            "parser_status": document.parser_status,
        }
        with manifest_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
