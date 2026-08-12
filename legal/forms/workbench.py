"""Revision-bound Maine findings and form-assistance work products."""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import secrets
import shutil
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from legal.documents.workspace import get_document, workspace_paths
from legal.drafting.findings_engine import Rule52BestInterestFindingsEngine
from legal.forms.intelligence import FormCatalogBuilder

SCHEMA_VERSION = "maine_findings_forms_workbench_v1"
ALGORITHM_VERSION = "v5.11.0"
FOLDER = "findings_forms"
MAX_FORMS = 100
MAX_FIELDS = 500
MAX_FIELD_CHARS = 5_000
MAX_JSON_BYTES = 64 * 1024 * 1024
REVIEW_ARTIFACT_NAMES = {
    "maine-findings-forms-review.json",
    "maine-findings-forms-review.html",
    "maine-findings-forms-receipt.json",
}
COMPLETION_ARTIFACT_NAMES = {
    "form-working-copy.json",
    "form-working-copy.txt",
    "form-completion-receipt.json",
}
_ID_RE = re.compile(r"^[a-f0-9]{24}$")
_DOC_ID_RE = re.compile(r"^[a-f0-9]{32}$")
_LOCK = threading.RLock()


class MaineFindingsFormsError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class WorkbenchArtifact:
    name: str
    relative_path: str
    sha256: str
    size_bytes: int
    media_type: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "relative_path": self.relative_path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "media_type": self.media_type,
        }


@dataclass
class FindingsFormsResult:
    status: str
    build_id: str
    packet: dict[str, Any]
    artifacts: list[WorkbenchArtifact] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    reused_existing_build: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "build_id": self.build_id,
            "packet": self.packet,
            "artifacts": [item.as_dict() for item in self.artifacts],
            "blockers": sorted(set(self.blockers)),
            "warnings": sorted(set(self.warnings)),
            "reused_existing_build": self.reused_existing_build,
            "review_required": True,
        }


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha(payload: bytes | Any) -> str:
    return hashlib.sha256(payload if isinstance(payload, bytes) else _canonical(payload)).hexdigest()


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write(path: Path, data: bytes) -> None:
    if path.exists() and path.is_symlink():
        raise MaineFindingsFormsError("artifact_symlink_refused", "A workbench artifact symlink was refused.", status_code=409)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temp = path.parent / f".{path.name}.{secrets.token_hex(8)}.tmp"
    try:
        with temp.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.chmod(temp, 0o600)
        except OSError:
            pass
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _safe_field_values(values: dict[str, Any] | None) -> dict[str, dict[str, str]]:
    output: dict[str, dict[str, str]] = {}
    for raw_form_id, raw_fields in list((values or {}).items())[:MAX_FORMS]:
        form_id = str(raw_form_id or "").strip().upper()[:40]
        if not re.fullmatch(r"(?:FM|PA|CV|PB)-\d{3}[A-Z]?", form_id) or not isinstance(raw_fields, dict):
            continue
        safe: dict[str, str] = {}
        for raw_name, raw_value in list(raw_fields.items())[:MAX_FIELDS]:
            name = re.sub(r"[^a-z0-9_]+", "_", str(raw_name or "").strip().lower())[:80].strip("_")
            value = str(raw_value or "").replace("\x00", "").strip()[:MAX_FIELD_CHARS]
            if name and value:
                safe[name] = value
        output[form_id] = safe
    return output


def _synchronized(method):
    def wrapped(*args, **kwargs):
        with _LOCK:
            return method(*args, **kwargs)
    return wrapped


class MaineFindingsFormsStore:
    def __init__(self, case_root: Path):
        paths = workspace_paths(case_root)
        self.root = paths.root / FOLDER
        self.builds = self.root / "builds"
        self.active_path = self.root / "ACTIVE_BUILD.json"
        for folder in (self.root, self.builds):
            if folder.exists() and folder.is_symlink():
                raise MaineFindingsFormsError("workbench_symlink_refused", "A findings/forms workspace symlink was refused.", status_code=409)
            folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.case_root = paths.case_root

    def catalog(self, authority_forms: Iterable[dict[str, Any]]) -> dict[str, Any]:
        records = [dict(row) for row in authority_forms if isinstance(row, dict)][:MAX_FORMS]
        current_versions = {
            str(row.get("form_id") or "").strip().upper(): str(row.get("version_date") or "")
            for row in records
            if str(row.get("freshness_status") or "").lower() in {"current", "fresh", "verified_current"}
            and row.get("form_id") and row.get("version_date")
        }
        report = FormCatalogBuilder().build_catalog(records, current_versions=current_versions)
        data = report.to_dict()
        data["review_required"] = True
        data["source"] = "verified_active_authority_generation"
        return data

    @_synchronized
    def build_review(
        self,
        document_id: str,
        *,
        authority_forms: Iterable[dict[str, Any]],
        selected_form_ids: Iterable[str] | None = None,
        posture: str = "final_order",
        evidence_records: Iterable[dict[str, Any]] | None = None,
        approved: bool = False,
    ) -> FindingsFormsResult:
        if approved is not True:
            raise MaineFindingsFormsError("explicit_approval_required", "Explicit approval is required.", status_code=409)
        document = get_document(self.case_root, document_id)
        document_id = str(document.get("document_id") or "").lower()
        if not _DOC_ID_RE.fullmatch(document_id):
            raise MaineFindingsFormsError("invalid_document_id", "The document ID is invalid.", status_code=404)
        revision_id = str(document.get("current_revision_id") or "")
        content = str(document.get("content") or "")
        forms = self.catalog(authority_forms)
        selected_ids = []
        known = {str(row.get("form_id") or ""): row for row in forms.get("entries") or []}
        for raw in selected_form_ids or []:
            form_id = str(raw or "").strip().upper()
            if form_id in known and form_id not in selected_ids:
                selected_ids.append(form_id)
        selected = [known[form_id] for form_id in selected_ids]
        findings = Rule52BestInterestFindingsEngine().review_order(
            content,
            posture=str(posture or "final_order"),
            evidence_records=evidence_records,
        ).to_dict()
        form_plan = self._form_plan(selected, content=content)
        blockers = list(findings.get("blockers") or []) + list(form_plan.get("blockers") or [])
        warnings = []
        if not forms.get("entries"):
            blockers.append("verified_form_catalog_unavailable")
        packet = {
            "schema_version": SCHEMA_VERSION,
            "algorithm_version": ALGORITHM_VERSION,
            "document_id": document_id,
            "revision_id": revision_id,
            "document_title": str(document.get("title") or "")[:240],
            "document_type": str(document.get("document_type") or "draft")[:80],
            "document_content_sha256": str(document.get("content_sha256") or _sha(content.encode("utf-8"))),
            "posture": str(posture or "final_order")[:80],
            "findings_review": findings,
            "form_catalog": forms,
            "form_plan": form_plan,
            "blockers": sorted(set(blockers)),
            "warnings": warnings,
            "generated_at": _utc_now(),
            "review_required": True,
            "legal_conclusion": "not_determined",
        }
        fingerprint = _sha({key: value for key, value in packet.items() if key != "generated_at"})
        build_id = fingerprint[:24]
        packet["build_id"] = build_id
        packet["packet_sha256"] = _sha(packet)
        build_dir = self.builds / build_id
        reused = False
        if build_dir.exists():
            verification = self.verify(build_id)
            if verification["status"] != "pass":
                raise MaineFindingsFormsError("immutable_build_collision", "An existing workbench build failed verification.", status_code=409)
            packet = self._read_json(build_dir / "maine-findings-forms-review.json")
            blockers = list(packet.get("blockers") or [])
            warnings = list(packet.get("warnings") or [])
            reused = True
        else:
            staging = self.builds / f".{build_id}.{uuid.uuid4().hex}.staging"
            staging.mkdir(mode=0o700)
            try:
                json_bytes = json.dumps(packet, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8")
                html_bytes = self._review_html(packet).encode("utf-8")
                receipt = {
                    "schema_version": "maine_findings_forms_receipt_v1",
                    "build_id": build_id,
                    "packet_sha256": packet["packet_sha256"],
                    "document_id": document_id,
                    "revision_id": revision_id,
                    "document_content_sha256": packet["document_content_sha256"],
                    "selected_form_ids": selected_ids,
                    "findings_blockers": findings.get("blockers") or [],
                    "form_blockers": form_plan.get("blockers") or [],
                    "algorithm_version": ALGORITHM_VERSION,
                    "generated_at": packet["generated_at"],
                    "review_required": True,
                }
                receipt["receipt_sha256"] = _sha(receipt)
                files = {
                    "maine-findings-forms-review.json": json_bytes,
                    "maine-findings-forms-review.html": html_bytes,
                    "maine-findings-forms-receipt.json": json.dumps(receipt, indent=2, sort_keys=True).encode("utf-8"),
                }
                manifest_rows = []
                for filename, data in files.items():
                    _atomic_write(staging / filename, data)
                    manifest_rows.append({"name": filename, "sha256": _sha(data), "size_bytes": len(data)})
                manifest = {"schema_version": SCHEMA_VERSION, "build_id": build_id, "files": manifest_rows, "packet_sha256": packet["packet_sha256"]}
                _atomic_write(staging / "manifest.json", json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8"))
                os.replace(staging, build_dir)
            finally:
                shutil.rmtree(staging, ignore_errors=True)
        pointer = {"build_id": build_id, "document_id": document_id, "revision_id": revision_id, "packet_sha256": packet["packet_sha256"]}
        _atomic_write(self.active_path, json.dumps(pointer, indent=2, sort_keys=True).encode("utf-8"))
        _atomic_write(self.root / f"ACTIVE_{document_id}.json", json.dumps(pointer, indent=2, sort_keys=True).encode("utf-8"))
        status = "checked" if not blockers else "review_required"
        return FindingsFormsResult(status, build_id, packet, self._artifacts(build_dir), blockers, warnings, reused)

    @_synchronized
    def complete_forms(
        self,
        build_id: str,
        *,
        form_values: dict[str, Any],
        confirmed: bool = False,
    ) -> dict[str, Any]:
        if confirmed is not True:
            raise MaineFindingsFormsError("explicit_confirmation_required", "Explicit confirmation is required.", status_code=409)
        review = self.load(build_id)
        packet = review["packet"]
        document = get_document(self.case_root, packet["document_id"])
        if str(document.get("current_revision_id") or "") != str(packet.get("revision_id") or ""):
            raise MaineFindingsFormsError("review_build_stale", "The document changed after the findings/forms review was created.", status_code=409)
        values = _safe_field_values(form_values)
        selected = packet.get("form_plan", {}).get("selected_forms") or []
        selected_ids = {str(row.get("form_id") or "") for row in selected}
        unknown = sorted(set(values) - selected_ids)
        if unknown:
            raise MaineFindingsFormsError("unknown_form_values", "Values were supplied for a form outside the selected plan.", status_code=409)
        completion_rows = []
        blockers = list(packet.get("blockers") or [])
        consistency: dict[str, set[str]] = {}
        for form in selected:
            form_id = str(form.get("form_id") or "")
            fields = values.get(form_id, {})
            required = [str(item) for item in form.get("required_fields") or []]
            missing = [name for name in required if not fields.get(name)]
            blockers.extend(f"required_form_field_missing:{form_id}:{name}" for name in missing)
            for name, value in fields.items():
                consistency.setdefault(name, set()).add(value.casefold())
            completion_rows.append({
                "form_id": form_id,
                "source_id": form.get("source_id"),
                "title": form.get("title"),
                "version_date": form.get("version_date"),
                "freshness_status": form.get("freshness_status"),
                "fields": fields,
                "required_fields": required,
                "missing_required_fields": missing,
                "review_required": True,
            })
        conflicts = [{"field": name, "value_count": len(values)} for name, values in consistency.items() if len(values) > 1]
        blockers.extend(f"cross_form_value_conflict:{row['field']}" for row in conflicts)
        completion = {
            "schema_version": "maine_form_working_copy_v1",
            "review_build_id": build_id,
            "document_id": packet["document_id"],
            "revision_id": packet["revision_id"],
            "document_content_sha256": packet["document_content_sha256"],
            "forms": completion_rows,
            "cross_form_conflicts": conflicts,
            "blockers": sorted(set(blockers)),
            "generated_at": _utc_now(),
            "review_required": True,
            "filing_ready": False,
            "notice": "This is structured working-copy data, not a completed official court PDF or a filing-ready document.",
        }
        completion_id = _sha({key: value for key, value in completion.items() if key != "generated_at"})[:24]
        completion["completion_id"] = completion_id
        completion["completion_sha256"] = _sha(completion)
        output_dir = self.builds / build_id / "completions" / completion_id
        if output_dir.exists():
            verification = self.verify_completion(build_id, completion_id)
            if verification["status"] != "pass":
                raise MaineFindingsFormsError(
                    "immutable_completion_collision",
                    "An existing form completion failed verification.",
                    status_code=409,
                )
            completion = self._read_json(output_dir / "form-working-copy.json")
        else:
            staging = output_dir.parent / f".{completion_id}.{uuid.uuid4().hex}.staging"
            staging.mkdir(mode=0o700, parents=True)
            try:
                working = json.dumps(completion, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8")
                receipt = {
                    "schema_version": "maine_form_completion_receipt_v1",
                    "completion_id": completion_id,
                    "completion_sha256": completion["completion_sha256"],
                    "review_build_id": build_id,
                    "document_id": packet["document_id"],
                    "revision_id": packet["revision_id"],
                    "selected_form_ids": sorted(selected_ids),
                    "blockers": completion["blockers"],
                    "generated_at": completion["generated_at"],
                    "review_required": True,
                }
                receipt["receipt_sha256"] = _sha(receipt)
                text_bytes = self._completion_text(completion).encode("utf-8")
                receipt_bytes = json.dumps(receipt, indent=2, sort_keys=True).encode("utf-8")
                files = {
                    "form-working-copy.json": working,
                    "form-working-copy.txt": text_bytes,
                    "form-completion-receipt.json": receipt_bytes,
                }
                manifest_rows = []
                for filename, data in files.items():
                    _atomic_write(staging / filename, data)
                    manifest_rows.append({"name": filename, "sha256": _sha(data), "size_bytes": len(data)})
                completion_manifest = {
                    "schema_version": "maine_form_completion_manifest_v1",
                    "build_id": build_id,
                    "completion_id": completion_id,
                    "completion_sha256": completion["completion_sha256"],
                    "files": manifest_rows,
                }
                _atomic_write(staging / "manifest.json", json.dumps(completion_manifest, indent=2, sort_keys=True).encode("utf-8"))
                os.replace(staging, output_dir)
            finally:
                shutil.rmtree(staging, ignore_errors=True)
        return {
            "status": "completed_blocked" if completion["blockers"] else "completed_review_required",
            "build_id": build_id,
            "completion_id": completion_id,
            "completion": completion,
            "artifacts": self._completion_artifacts(output_dir),
            "review_required": True,
            "filing_ready": False,
        }

    def active(self, *, document_id: str | None = None) -> dict[str, Any]:
        pointer_path = self.active_path
        if document_id:
            candidate = str(document_id or "").lower()
            if not _DOC_ID_RE.fullmatch(candidate):
                raise MaineFindingsFormsError("invalid_document_id", "The document ID is invalid.", status_code=404)
            pointer_path = self.root / f"ACTIVE_{candidate}.json"
        if not pointer_path.is_file() or pointer_path.is_symlink():
            raise MaineFindingsFormsError("active_build_unavailable", "No active findings/forms review is available.", status_code=404)
        pointer = self._read_json(pointer_path)
        if document_id and str(pointer.get("document_id") or "") != str(document_id):
            raise MaineFindingsFormsError("active_build_document_mismatch", "The active review belongs to another document.", status_code=404)
        return self.load(str(pointer.get("build_id") or ""))

    def load(self, build_id: str) -> dict[str, Any]:
        verification = self.verify(build_id)
        if verification["status"] != "pass":
            raise MaineFindingsFormsError("build_unverified", "The findings/forms build failed verification.", status_code=409)
        packet = self._read_json(self.builds / build_id / "maine-findings-forms-review.json")
        return {"status": "pass", "build_id": build_id, "packet": packet, "artifacts": [item.as_dict() for item in self._artifacts(self.builds / build_id)], "review_required": True}

    def verify(self, build_id: str) -> dict[str, Any]:
        if not _ID_RE.fullmatch(str(build_id or "")):
            raise MaineFindingsFormsError("invalid_build_id", "The findings/forms build ID is invalid.", status_code=404)
        build_dir = self.builds / build_id
        if not build_dir.is_dir() or build_dir.is_symlink():
            raise MaineFindingsFormsError("build_not_found", "The findings/forms build was not found.", status_code=404)
        manifest = self._read_json(build_dir / "manifest.json")
        blockers: list[str] = []
        if str(manifest.get("schema_version") or "") != SCHEMA_VERSION:
            blockers.append("manifest_schema_mismatch")
        if str(manifest.get("build_id") or "") != build_id:
            blockers.append("manifest_build_id_mismatch")
        rows = manifest.get("files") or []
        names = [Path(str(row.get("name") or "")).name for row in rows if isinstance(row, dict)]
        if len(names) != len(set(names)):
            blockers.append("manifest_duplicate_artifact")
        if set(names) != REVIEW_ARTIFACT_NAMES:
            blockers.append("manifest_artifact_set_mismatch")
        for row in rows:
            if not isinstance(row, dict):
                blockers.append("manifest_artifact_row_invalid")
                continue
            name = Path(str(row.get("name") or "")).name
            path = build_dir / name
            if not path.is_file() or path.is_symlink():
                blockers.append(f"artifact_missing:{name}")
                continue
            if path.stat().st_size != int(row.get("size_bytes") or -1):
                blockers.append(f"artifact_size_mismatch:{name}")
            if _sha_file(path) != str(row.get("sha256") or ""):
                blockers.append(f"artifact_hash_mismatch:{name}")
        packet = self._read_json(build_dir / "maine-findings-forms-review.json")
        stored_hash = str(packet.get("packet_sha256") or "")
        payload = dict(packet)
        payload.pop("packet_sha256", None)
        if _sha(payload) != stored_hash:
            blockers.append("packet_hash_mismatch")
        if str(manifest.get("packet_sha256") or "") != stored_hash:
            blockers.append("manifest_packet_hash_mismatch")
        return {"status": "pass" if not blockers else "fail", "valid": not blockers, "build_id": build_id, "blockers": blockers, "review_required": True}

    def verify_completion(self, build_id: str, completion_id: str) -> dict[str, Any]:
        parent = self.verify(build_id)
        if not _ID_RE.fullmatch(str(completion_id or "")):
            raise MaineFindingsFormsError("invalid_completion_id", "The completion ID is invalid.", status_code=404)
        root = self.builds / build_id / "completions" / completion_id
        if not root.is_dir() or root.is_symlink():
            raise MaineFindingsFormsError("completion_not_found", "The form completion was not found.", status_code=404)
        manifest = self._read_json(root / "manifest.json")
        blockers: list[str] = [f"parent_review:{item}" for item in parent.get("blockers") or []]
        if str(manifest.get("schema_version") or "") != "maine_form_completion_manifest_v1":
            blockers.append("completion_manifest_schema_mismatch")
        if str(manifest.get("build_id") or "") != build_id:
            blockers.append("completion_manifest_build_id_mismatch")
        if str(manifest.get("completion_id") or "") != completion_id:
            blockers.append("completion_manifest_id_mismatch")
        rows = manifest.get("files") or []
        names = [Path(str(row.get("name") or "")).name for row in rows if isinstance(row, dict)]
        if len(names) != len(set(names)):
            blockers.append("completion_manifest_duplicate_artifact")
        if set(names) != COMPLETION_ARTIFACT_NAMES:
            blockers.append("completion_manifest_artifact_set_mismatch")
        for row in rows:
            if not isinstance(row, dict):
                blockers.append("completion_manifest_artifact_row_invalid")
                continue
            name = Path(str(row.get("name") or "")).name
            path = root / name
            if not path.is_file() or path.is_symlink():
                blockers.append(f"completion_artifact_missing:{name}")
                continue
            if path.stat().st_size != int(row.get("size_bytes") or -1):
                blockers.append(f"completion_artifact_size_mismatch:{name}")
            if _sha_file(path) != str(row.get("sha256") or ""):
                blockers.append(f"completion_artifact_hash_mismatch:{name}")
        completion = self._read_json(root / "form-working-copy.json")
        stored_hash = str(completion.get("completion_sha256") or "")
        payload = dict(completion)
        payload.pop("completion_sha256", None)
        if _sha(payload) != stored_hash:
            blockers.append("completion_hash_mismatch")
        if str(manifest.get("completion_sha256") or "") != stored_hash:
            blockers.append("completion_manifest_hash_mismatch")
        return {"status": "pass" if not blockers else "fail", "valid": not blockers, "build_id": build_id, "completion_id": completion_id, "blockers": blockers, "review_required": True}

    def resolve_artifact(self, build_id: str, filename: str, *, completion_id: str = "") -> tuple[Path, str]:
        allowed = {
            "maine-findings-forms-review.json": "application/json",
            "maine-findings-forms-review.html": "text/html",
            "maine-findings-forms-receipt.json": "application/json",
            "form-working-copy.json": "application/json",
            "form-working-copy.txt": "text/plain",
            "form-completion-receipt.json": "application/json",
        }
        safe_name = Path(str(filename or "")).name
        if safe_name not in allowed:
            raise MaineFindingsFormsError("artifact_not_allowed", "The requested artifact is not allowed.", status_code=404)
        self.verify(build_id)
        base = self.builds / build_id
        if completion_id:
            if not _ID_RE.fullmatch(completion_id):
                raise MaineFindingsFormsError("invalid_completion_id", "The completion ID is invalid.", status_code=404)
            base = base / "completions" / completion_id
            completion_verification = self.verify_completion(build_id, completion_id)
            if completion_verification["status"] != "pass":
                raise MaineFindingsFormsError("completion_unverified", "The form completion failed verification.", status_code=409)
        path = base / safe_name
        if not path.is_file() or path.is_symlink():
            raise MaineFindingsFormsError("artifact_unavailable", "The requested artifact is unavailable.", status_code=404)
        return path, allowed[safe_name]

    def _form_plan(self, selected: list[dict[str, Any]], *, content: str) -> dict[str, Any]:
        blockers = []
        if not selected:
            blockers.append("required_form_selection_not_confirmed")
        for row in selected:
            form_id = str(row.get("form_id") or "")
            freshness = str(row.get("freshness_status") or "unknown")
            if freshness not in {"current", "fresh", "verified_current"}:
                blockers.append(f"form_not_verified_current:{form_id}")
        shared: dict[str, list[str]] = {}
        for row in selected:
            for field_name in row.get("required_fields") or []:
                shared.setdefault(str(field_name), []).append(str(row.get("form_id") or ""))
        return {
            "selected_forms": selected,
            "selected_form_ids": [row.get("form_id") for row in selected],
            "shared_fields": {field: ids for field, ids in shared.items() if len(ids) > 1},
            "blockers": sorted(set(blockers)),
            "review_required": True,
            "notice": "Selection is based only on admitted active authority metadata and must be reviewed for the actual filing context.",
        }

    def _artifacts(self, build_dir: Path) -> list[WorkbenchArtifact]:
        media = {
            "maine-findings-forms-review.json": "application/json",
            "maine-findings-forms-review.html": "text/html",
            "maine-findings-forms-receipt.json": "application/json",
        }
        return [WorkbenchArtifact(name, name, _sha_file(build_dir / name), (build_dir / name).stat().st_size, media[name]) for name in media if (build_dir / name).is_file()]

    def _completion_artifacts(self, output_dir: Path) -> list[dict[str, Any]]:
        media = {"form-working-copy.json": "application/json", "form-working-copy.txt": "text/plain", "form-completion-receipt.json": "application/json"}
        return [{"name": name, "sha256": _sha_file(output_dir / name), "size_bytes": (output_dir / name).stat().st_size, "media_type": media[name]} for name in media if (output_dir / name).is_file()]

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_JSON_BYTES:
            raise MaineFindingsFormsError("artifact_invalid", "A findings/forms artifact is invalid.", status_code=409)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise MaineFindingsFormsError("artifact_invalid", "A findings/forms artifact is invalid.", status_code=409)
        return payload

    @staticmethod
    def _review_html(packet: dict[str, Any]) -> str:
        findings = packet.get("findings_review") or {}
        forms = packet.get("form_plan") or {}
        rows = "".join(f"<tr><td>{html.escape(str(row.get('label') or ''))}</td><td>{html.escape(str(row.get('status') or ''))}</td><td>{len(row.get('supporting_record_spans') or [])}</td></tr>" for row in findings.get("factor_matrix") or [])
        selected = "".join(f"<li>{html.escape(str(row.get('form_id') or ''))}: {html.escape(str(row.get('title') or ''))}</li>" for row in forms.get("selected_forms") or [])
        blockers = "".join(f"<li>{html.escape(str(item))}</li>" for item in packet.get("blockers") or [])
        return f"<!doctype html><html><head><meta charset='utf-8'><title>Maine findings and forms review</title></head><body><h1>{html.escape(packet.get('document_title') or 'Document')}</h1><p>Review required. No legal conclusion or filing readiness is determined.</p><h2>Best-interest findings matrix</h2><table><thead><tr><th>Factor</th><th>Status</th><th>Candidate record spans</th></tr></thead><tbody>{rows}</tbody></table><h2>Selected forms</h2><ul>{selected}</ul><h2>Blockers</h2><ul>{blockers}</ul><p><code>{html.escape(packet.get('packet_sha256') or '')}</code></p></body></html>"

    @staticmethod
    def _completion_text(completion: dict[str, Any]) -> str:
        lines = ["MAINE COURT FORM WORKING COPY", "Review required. This is not an official completed court PDF.", ""]
        for form in completion.get("forms") or []:
            lines.extend([f"[{form.get('form_id')}] {form.get('title')}", f"Version: {form.get('version_date') or 'unknown'} · Freshness: {form.get('freshness_status') or 'unknown'}"])
            for name, value in sorted((form.get("fields") or {}).items()):
                lines.append(f"{name}: {value}")
            if form.get("missing_required_fields"):
                lines.append("Missing required fields: " + ", ".join(form["missing_required_fields"]))
            lines.append("")
        if completion.get("blockers"):
            lines.append("BLOCKERS")
            lines.extend(f"- {item}" for item in completion["blockers"])
        return "\n".join(lines) + "\n"
