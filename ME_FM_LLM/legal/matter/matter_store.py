from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

from legal.matter.models import Matter, MatterDocument
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
        metadata_path = matter_dir / "matter.json"
        metadata_path.write_text(json.dumps(asdict(matter), indent=2, sort_keys=True), encoding="utf-8")
        return matter_dir

    def store_document(self, document: MatterDocument) -> Path:
        matter_dir = self.root / document.tenant_id / document.matter_id
        matter_dir.mkdir(parents=True, exist_ok=True)
        document_path = matter_dir / f"{document.document_id}.json.enc"
        payload = asdict(document)
        payload["storage_encryption_status"] = "encrypted_local_envelope"
        envelope = self.encryptor.encrypt_json(payload)
        document_path.write_text(json.dumps(envelope, indent=2, sort_keys=True), encoding="utf-8")
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
