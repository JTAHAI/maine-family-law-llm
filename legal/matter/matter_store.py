from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict
from pathlib import Path

from legal.matter.models import Matter, MatterDocument
from legal.security.durable_io import atomic_write_bytes
from legal.security.local_encryption import LocalEnvelopeEncryptor


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
            legacy_metadata_path.unlink()
        metadata_path = matter_dir / "matter.json.enc"
        payload = asdict(matter)
        payload["storage_encryption_status"] = "encrypted_local_envelope"
        payload["encryption_metadata"] = self._envelope_metadata(payload_kind="matter", record_id=matter.matter_id)
        envelope = self.encryptor.encrypt_json(payload)
        atomic_write_bytes(metadata_path, json.dumps(envelope, indent=2, sort_keys=True).encode("utf-8"))
        return matter_dir

    def load_matter(self, matter_path: str | Path) -> dict:
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
            return self.encryptor.decrypt_json(payload)
        return payload

    def store_document(self, document: MatterDocument) -> Path:
        matter_dir = self.root / document.tenant_id / document.matter_id
        matter_dir.mkdir(parents=True, exist_ok=True)
        document_path = matter_dir / f"{document.document_id}.json.enc"
        payload = asdict(document)
        payload["storage_encryption_status"] = "encrypted_local_envelope"
        payload["encryption_metadata"] = self._envelope_metadata(payload_kind="document", record_id=document.document_id)
        envelope = self.encryptor.encrypt_json(payload)
        atomic_write_bytes(document_path, json.dumps(envelope, indent=2, sort_keys=True).encode("utf-8"))
        self._append_manifest(document, document_path)
        return document_path

    def load_document(self, document_path: str | Path) -> dict:
        envelope = json.loads(Path(document_path).read_text(encoding="utf-8"))
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
