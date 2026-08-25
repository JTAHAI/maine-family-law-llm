"""Encrypted matter-scoped implementation of the v8 Add-on Studio.

Every add-on produces deterministic review artifacts.  Native tools and signed
extensions fail closed when their approved local prerequisites are unavailable.
No handler files, sends, uploads, installs, downloads, or changes an external
account.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import html
import io
import json
import os
import re
import subprocess
import tempfile
import uuid
import zipfile
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from legal.addons.whisper_engine import (
    WhisperEngineError,
    discover_whisper_engine,
    transcribe_with_whisper,
)
from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock, read_bounded_regular_file
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path


SCHEMA_VERSION = "maine_family_law_llm.addon_studio.v2"
LEGACY_SCHEMA_VERSION = "maine_family_law_llm.addon_studio.v1"
WORKSPACE_FOLDER = "55_ADDON_STUDIO"
ADDON_IDS = (
    "native_whisper_transcription", "ocr_correction_studio", "communications_importer",
    "evidence_relationship_graph", "local_model_manager", "court_form_autofill",
    "advanced_table_extraction", "financial_document_intelligence", "semantic_order_comparison",
    "authority_update_center", "guided_research_builder", "evidence_annotation_studio",
    "local_automation_scheduler", "secure_reviewer_collaboration", "matter_template_library",
    "conflict_entity_resolver", "desktop_notification_center", "courtroom_bundle_exporter",
    "voice_drafting_commands", "extension_sdk_permission_center",
)
_ID = re.compile(r"[a-z][a-z0-9_-]{2,79}\Z")
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_MAX_STATE = 24 * 1024 * 1024
_MAX_TEXT = 200_000
_MAX_MEDIA = 512 * 1024 * 1024
_ALLOWED_RECIPE_TASKS = {"inbox_scan", "backup", "ocr_queue", "authority_check", "matter_health"}
_ALLOWED_EXTENSION_PERMISSIONS = {
    "matter.metadata.read", "matter.records.read", "matter.artifacts.write",
    "authority.read", "notifications.write",
}
_REVIEW_DECISIONS = {"accepted", "needs_changes", "rejected"}
_OFFICIAL_AUTHORITY_HOSTS = {
    "legislature.maine.gov",
    "www.mainelegislature.org",
    "courts.maine.gov",
    "www.courts.maine.gov",
}


class AddonStudioError(RuntimeError):
    def __init__(self, code: str, message: str | None = None, *, status_code: int = 400):
        super().__init__(message or code)
        self.code = code
        self.message = message or code.replace("_", " ")
        self.status_code = status_code


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _hash(value: Any) -> str:
    raw = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def _id(value: Any, field: str = "id") -> str:
    result = str(value or "").strip().casefold()
    if not _ID.fullmatch(result):
        raise AddonStudioError(f"{field}_invalid")
    return result


def _text(value: Any, *, limit: int = _MAX_TEXT, required: bool = False) -> str:
    result = str(value or "").strip()
    if len(result) > limit or (required and not result):
        raise AddonStudioError("text_invalid")
    return result


def _sha(value: Any, field: str = "sha256", *, required: bool = True) -> str:
    result = str(value or "").strip().casefold()
    if (required or result) and not _SHA.fullmatch(result):
        raise AddonStudioError(f"{field}_invalid")
    return result


def _rows(value: Any, *, limit: int = 500) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) > limit or any(not isinstance(row, dict) for row in value):
        raise AddonStudioError("rows_invalid")
    return [dict(row) for row in value]


def _source_ref(value: Any, *, require_hash: bool = False) -> dict[str, str]:
    row = dict(value or {})
    result = {
        "record_id": _id(row.get("record_id"), "record_id"),
        "locator": _text(row.get("locator"), limit=500, required=True),
    }
    source_hash = _sha(row.get("sha256") or row.get("source_hash"), required=require_hash)
    if source_hash:
        result["sha256"] = source_hash
    return result


class AddonStudioStore:
    def __init__(
        self,
        case_root: str | Path,
        *,
        encryption_key: str | None = None,
        tenant_id: str = "local",
    ):
        self.case_root = Path(case_root).resolve()
        self.root = self.case_root / WORKSPACE_FOLDER
        if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()):
            raise AddonStudioError("addon_workspace_unavailable", status_code=409)
        self.tenant_id = _id(tenant_id, "tenant_id")
        self.tenant_hash = _hash(self.tenant_id)[:24]
        self.scope = _hash({"case_root": str(self.case_root), "tenant": self.tenant_hash})[:24]
        self.encryptor = LocalEnvelopeEncryptor(
            encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me"
        )
        self.handlers: dict[str, Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]] = {
            addon_id: getattr(self, f"_{addon_id}") for addon_id in ADDON_IDS
        }

    @property
    def state_path(self) -> Path:
        return self.root / "addon-studio.json.enc"

    @property
    def lock_path(self) -> Path:
        return self.root / ".addon-studio.lock"

    def _initial(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA_VERSION,
            "scope": self.scope,
            "tenant_hash": self.tenant_hash,
            "matter_id": self.case_root.name,
            "revision": 0,
            "addons": {name: [] for name in ADDON_IDS},
            "reviews": [],
            "history": [],
        }

    def _load(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return self._initial()
        try:
            value = self.encryptor.decrypt_json(strict_json_load_path(self.state_path, max_bytes=_MAX_STATE, require_object=True))
        except Exception as exc:
            raise AddonStudioError("addon_state_unavailable", status_code=409) from exc
        if value.get("schema") == LEGACY_SCHEMA_VERSION:
            legacy_scope = _hash(str(self.case_root))[:24]
            if value.get("scope") != legacy_scope:
                raise AddonStudioError("cross_matter_access_denied", status_code=404)
            value.update(
                {
                    "schema": SCHEMA_VERSION,
                    "scope": self.scope,
                    "tenant_hash": self.tenant_hash,
                    "reviews": list(value.get("reviews") or []),
                }
            )
            self._save(value)
        if (
            value.get("schema") != SCHEMA_VERSION
            or value.get("scope") != self.scope
            or value.get("tenant_hash") != self.tenant_hash
        ):
            raise AddonStudioError("cross_matter_access_denied", status_code=404)
        return value

    def _save(self, value: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(self.state_path, json.dumps(self.encryptor.encrypt_json(value), sort_keys=True).encode(), mode=0o600)

    def _artifact(
        self,
        kind: str,
        item_id: str,
        content: bytes,
        suffix: str,
        *,
        encrypted: bool = True,
        media_type: str = "application/octet-stream",
    ) -> dict[str, Any]:
        safe_kind, safe_id = _id(kind, "artifact_kind"), _id(item_id, "artifact_id")
        folder = self.root / "artifacts" / safe_kind
        folder.mkdir(parents=True, exist_ok=True)
        content_hash = _hash(content)
        download_name = f"{safe_id}.{suffix}"
        if encrypted:
            content = json.dumps(self.encryptor.encrypt_json({"content": base64.b64encode(content).decode()}), sort_keys=True).encode()
            suffix = f"{suffix}.enc"
        target = folder / f"{safe_id}.{suffix}"
        if target.exists() and target.is_symlink():
            raise AddonStudioError("artifact_symlink_refused", status_code=409)
        atomic_write_bytes(target, content, mode=0o600)
        return {
            "artifact_id": safe_id,
            "kind": safe_kind,
            "relative_path": str(target.relative_to(self.case_root)).replace("\\", "/"),
            "sha256": _hash(content),
            "content_sha256": content_hash,
            "size": len(content),
            "encrypted": encrypted,
            "media_type": media_type,
            "download_name": download_name,
            "review_required": True,
        }

    def summary(self) -> dict[str, Any]:
        value = self._load()
        pending = sum(
            1
            for addon_rows in value["addons"].values()
            for row in addon_rows
            if not any(review.get("result_id") == row.get("result_id") for review in value.get("reviews", []))
        )
        return {"schema_version": SCHEMA_VERSION, "matter_id": value["matter_id"], "revision": value["revision"],
                "addon_ids": list(ADDON_IDS), "counts": {key: len(rows) for key, rows in value["addons"].items()},
                "status": "review_required", "local_only": True, "review_required": True,
                "pending_review_count": pending, "history_tail": value["history"][-20:]}

    def execute(
        self,
        addon_id: str,
        payload: dict[str, Any],
        *,
        actor_role: str = "reviewer",
        audit_event_id: str = "local",
    ) -> dict[str, Any]:
        safe_addon = str(addon_id or "").strip().casefold()
        if safe_addon not in self.handlers:
            raise AddonStudioError("addon_not_found", status_code=404)
        with exclusive_file_lock(self.lock_path):
            value = self._load()
            request_id = str(payload.get("request_id") or "").strip().casefold()
            if request_id:
                safe_request = _id(request_id, "request_id")
                prior = next(
                    (row for row in value["addons"][safe_addon] if row.get("request_id") == safe_request),
                    None,
                )
                if prior is not None:
                    replay = deepcopy(prior)
                    replay["idempotent_replay"] = True
                    return replay
            result = self.handlers[safe_addon](dict(payload or {}), value)
            result.update(
                {
                    "addon_id": safe_addon,
                    "local_only": True,
                    "review_required": True,
                    "review_state": "pending",
                    "request_id": _id(request_id, "request_id") if request_id else "",
                }
            )
            result["result_hash"] = _hash(result)
            value["addons"][safe_addon].append(deepcopy(result))
            previous = value["history"][-1]["hash"] if value["history"] else ""
            event = {"event_id": f"addon_{uuid.uuid4().hex}", "at": _now(), "addon_id": safe_addon,
                     "result_id": result.get("result_id", ""), "result_hash": result["result_hash"],
                     "previous_hash": previous, "review_required": True,
                     "actor_role": _id(actor_role, "actor_role"),
                     "audit_event_id": _text(audit_event_id, limit=100, required=True),
                     "tenant_hash": self.tenant_hash}
            event["hash"] = _hash(event)
            value["history"].append(event)
            value["revision"] += 1
            self._save(value)
            return result

    def item(self, addon_id: str, result_id: str) -> dict[str, Any]:
        safe_addon, safe_result = str(addon_id).casefold(), _id(result_id, "result_id")
        if safe_addon not in ADDON_IDS:
            raise AddonStudioError("addon_not_found", status_code=404)
        row = next((item for item in self._load()["addons"][safe_addon] if item.get("result_id") == safe_result), None)
        if row is None:
            raise AddonStudioError("addon_result_not_found", status_code=404)
        reviews = [
            deepcopy(review)
            for review in self._load().get("reviews", [])
            if review.get("result_id") == safe_result
        ]
        return {
            "addon_id": safe_addon,
            "item": deepcopy(row),
            "reviews": reviews,
            "review_state": reviews[-1]["decision"] if reviews else "pending",
            "review_required": True,
        }

    def review_result(
        self,
        addon_id: str,
        result_id: str,
        payload: dict[str, Any],
        *,
        actor_role: str = "reviewer",
        audit_event_id: str = "local",
    ) -> dict[str, Any]:
        safe_addon, safe_result = str(addon_id).casefold(), _id(result_id, "result_id")
        if safe_addon not in ADDON_IDS:
            raise AddonStudioError("addon_not_found", status_code=404)
        decision = _text(payload.get("decision"), limit=30).casefold()
        if decision not in _REVIEW_DECISIONS:
            raise AddonStudioError("review_decision_invalid")
        if payload.get("confirmed") is not True:
            raise AddonStudioError("review_confirmation_required", status_code=409)
        with exclusive_file_lock(self.lock_path):
            value = self._load()
            row = next(
                (item for item in value["addons"][safe_addon] if item.get("result_id") == safe_result),
                None,
            )
            if row is None:
                raise AddonStudioError("addon_result_not_found", status_code=404)
            expected = _sha(payload.get("result_hash"), "result_hash")
            if expected != row.get("result_hash") or _hash({k: v for k, v in row.items() if k != "result_hash"}) != expected:
                raise AddonStudioError("addon_result_hash_mismatch", status_code=409)
            previous = value["history"][-1]["hash"] if value["history"] else ""
            review = {
                "review_id": f"review_{uuid.uuid4().hex[:16]}",
                "addon_id": safe_addon,
                "result_id": safe_result,
                "result_hash": expected,
                "decision": decision,
                "note": _text(payload.get("note"), limit=4_000),
                "reviewed_at": _now(),
                "actor_role": _id(actor_role, "actor_role"),
                "audit_event_id": _text(audit_event_id, limit=100, required=True),
                "tenant_hash": self.tenant_hash,
                "previous_hash": previous,
            }
            review["hash"] = _hash(review)
            value["reviews"].append(review)
            history_event = {
                "event_id": review["review_id"],
                "at": review["reviewed_at"],
                "addon_id": safe_addon,
                "result_id": safe_result,
                "result_hash": expected,
                "previous_hash": previous,
                "review_required": True,
                "actor_role": review["actor_role"],
                "audit_event_id": review["audit_event_id"],
                "tenant_hash": self.tenant_hash,
            }
            history_event["hash"] = _hash(history_event)
            value["history"].append(history_event)
            value["revision"] += 1
            self._save(value)
        return {"review": review, "review_state": decision, "filing_ready": False, "review_required": True}

    def verify_integrity(self) -> dict[str, Any]:
        value = self._load()
        failures: list[str] = []
        previous = ""
        result_hashes = {
            row.get("result_id"): row.get("result_hash")
            for rows in value["addons"].values()
            for row in rows
        }
        for rows in value["addons"].values():
            for row in rows:
                expected = _hash({key: item for key, item in row.items() if key != "result_hash"})
                if row.get("result_hash") != expected:
                    failures.append(f"result_hash:{row.get('result_id', 'unknown')}")
        for event in value["history"]:
            event_without_hash = {key: item for key, item in event.items() if key != "hash"}
            if event.get("previous_hash") != previous or event.get("hash") != _hash(event_without_hash):
                failures.append(f"history_hash:{event.get('event_id', 'unknown')}")
            if event.get("result_hash") != result_hashes.get(event.get("result_id")):
                failures.append(f"history_result:{event.get('event_id', 'unknown')}")
            previous = str(event.get("hash") or "")
        return {
            "status": "pass" if not failures else "fail",
            "failure_count": len(failures),
            "failures": failures,
            "event_count": len(value["history"]),
            "result_count": len(result_hashes),
            "head_hash": previous,
            "review_required": True,
        }

    @staticmethod
    def _walk_artifacts(value: Any) -> list[dict[str, Any]]:
        artifacts: list[dict[str, Any]] = []
        if isinstance(value, dict):
            if value.get("artifact_id") and value.get("relative_path") and value.get("sha256"):
                artifacts.append(value)
            for child in value.values():
                artifacts.extend(AddonStudioStore._walk_artifacts(child))
        elif isinstance(value, list):
            for child in value:
                artifacts.extend(AddonStudioStore._walk_artifacts(child))
        return artifacts

    def artifact_content(self, addon_id: str, result_id: str, artifact_id: str) -> tuple[dict[str, Any], bytes]:
        inspected = self.item(addon_id, result_id)
        safe_artifact = _id(artifact_id, "artifact_id")
        artifact = next(
            (row for row in self._walk_artifacts(inspected["item"]) if row.get("artifact_id") == safe_artifact),
            None,
        )
        if artifact is None:
            raise AddonStudioError("addon_artifact_not_found", status_code=404)
        target = (self.case_root / str(artifact["relative_path"])).resolve()
        if self.case_root not in target.parents or not target.is_file() or target.is_symlink():
            raise AddonStudioError("addon_artifact_unavailable", status_code=409)
        stored = read_bounded_regular_file(target, max_bytes=_MAX_STATE)
        if _hash(stored) != artifact["sha256"]:
            raise AddonStudioError("addon_artifact_hash_mismatch", status_code=409)
        content = stored
        if artifact.get("encrypted"):
            try:
                envelope = json.loads(stored.decode("utf-8"))
                decrypted = self.encryptor.decrypt_json(envelope)
                content = base64.b64decode(str(decrypted["content"]), validate=True)
            except Exception as exc:
                raise AddonStudioError("addon_artifact_decryption_failed", status_code=409) from exc
        if artifact.get("content_sha256") and _hash(content) != artifact["content_sha256"]:
            raise AddonStudioError("addon_artifact_content_hash_mismatch", status_code=409)
        return deepcopy(artifact), content

    def _result(self, prefix: str, **fields: Any) -> dict[str, Any]:
        return {"result_id": f"{prefix}_{uuid.uuid4().hex[:16]}", "created_at": _now(), **fields}

    def _source_file(self, value: Any, *, max_bytes: int = _MAX_MEDIA) -> tuple[Path, bytes, str]:
        relative = Path(_text(value, limit=500, required=True))
        if relative.is_absolute() or ".." in relative.parts:
            raise AddonStudioError("source_path_invalid")
        source = (self.case_root / relative).resolve()
        if (
            self.case_root not in source.parents
            or not source.is_file()
            or source.is_symlink()
            or source.stat().st_size > max_bytes
        ):
            raise AddonStudioError("source_file_unavailable", status_code=409)
        content = read_bounded_regular_file(source, max_bytes=max_bytes)
        return source, content, _hash(content)

    def _model_file(self, value: Any) -> tuple[Path, int, str, bytes]:
        relative = Path(_text(value, limit=500, required=True))
        if relative.is_absolute() or ".." in relative.parts:
            raise AddonStudioError("model_path_invalid")
        source = (self.case_root / relative).resolve()
        if self.case_root not in source.parents or not source.is_file() or source.is_symlink():
            raise AddonStudioError("model_artifact_unavailable", status_code=409)
        size = source.stat().st_size
        if size < 8 or size > 16 * 1024 * 1024 * 1024:
            raise AddonStudioError("model_artifact_size_invalid", status_code=409)
        digest = hashlib.sha256()
        with source.open("rb") as handle:
            header = handle.read(16)
            digest.update(header)
            for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
                digest.update(chunk)
        return source, size, digest.hexdigest(), header

    def _native_whisper_transcription(self, payload: dict[str, Any], _state: dict[str, Any]) -> dict[str, Any]:
        relative = Path(_text(payload.get("media_relative_path"), limit=500, required=True))
        if relative.is_absolute() or ".." in relative.parts:
            raise AddonStudioError("media_path_invalid")
        source = (self.case_root / relative).resolve()
        if self.case_root not in source.parents or not source.is_file() or source.is_symlink() or source.stat().st_size > _MAX_MEDIA:
            raise AddonStudioError("media_source_unavailable", status_code=409)
        source_hash = _hash(read_bounded_regular_file(source, max_bytes=_MAX_MEDIA))
        if payload.get("source_hash") and _sha(payload.get("source_hash")) != source_hash:
            raise AddonStudioError("media_source_hash_mismatch", status_code=409)
        command_raw = os.environ.get("MFL_WHISPER_COMMAND_JSON", "")
        tool_root = Path(os.environ.get("MFL_WHISPER_TOOL_ROOT", "")).resolve() if os.environ.get("MFL_WHISPER_TOOL_ROOT") else None
        data: dict[str, Any]
        executable: Path
        model_hash = ""
        model_name = ""
        engine_version = "adapter"
        if command_raw and tool_root is not None:
            try:
                template = json.loads(command_raw)
                if not isinstance(template, list) or not template:
                    raise ValueError
                executable = Path(str(template[0])).resolve()
            except Exception as exc:
                raise AddonStudioError("whisper_command_invalid", status_code=409) from exc
            if not executable.is_file() or tool_root != executable.parent and tool_root not in executable.parents:
                raise AddonStudioError("whisper_executable_outside_approved_root", status_code=409)
            self.root.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="whisper-adapter-", dir=self.root) as temp:
                output = Path(temp) / "result.json"
                command = [str(part).replace("{input}", str(source)).replace("{output}", str(output)) for part in template]
                env = {**os.environ, "HTTP_PROXY": "", "HTTPS_PROXY": "", "ALL_PROXY": "", "NO_PROXY": "*", "HF_HUB_OFFLINE": "1"}
                try:
                    completed = subprocess.run(command, cwd=str(self.root), env=env, capture_output=True, text=True, timeout=300, check=False)
                except (OSError, subprocess.TimeoutExpired) as exc:
                    raise AddonStudioError("whisper_engine_failed", status_code=409) from exc
                if completed.returncode != 0 or not output.is_file():
                    raise AddonStudioError("whisper_engine_failed", status_code=409)
                data = strict_json_load_path(output, max_bytes=8 * 1024 * 1024, require_object=True)
        else:
            engine = discover_whisper_engine()
            if engine is None:
                return self._result("whisper", status="blocked", blockers=["approved_local_whisper_engine_unavailable"],
                                    source_hash=source_hash, no_automatic_download=True)
            executable = engine.executable
            try:
                data = transcribe_with_whisper(engine, source, work_root=self.root)
            except WhisperEngineError as exc:
                raise AddonStudioError(exc.code, status_code=409) from exc
            model_hash = str(data.get("model_sha256") or "")
            model_name = str(data.get("model_name") or "")
            engine_version = str(data.get("engine_version") or "")
        transcript = _text(data.get("text"), required=True)
        segments = _rows(data.get("segments") or [], limit=20_000)
        transcript_id = f"transcript_{uuid.uuid4().hex[:12]}"
        artifact = self._artifact("transcript", transcript_id, transcript.encode(), "txt", media_type="text/plain; charset=utf-8")
        segments_artifact = self._artifact(
            "transcript_segments",
            f"segments_{uuid.uuid4().hex[:12]}",
            json.dumps(segments, indent=2, sort_keys=True).encode(),
            "json",
            media_type="application/json",
        )
        return self._result("whisper", status="completed_review_required", source_hash=source_hash,
                            transcript_sha256=_hash(transcript.encode()), segment_count=len(segments), artifact=artifact,
                            segments_artifact=segments_artifact, language=_text(data.get("language") or "unknown", limit=20),
                            engine="whisper.cpp" if model_hash else "approved_adapter", engine_version=engine_version,
                            model_name=model_name, model_sha256=model_hash,
                            engine_executable_sha256=_hash(read_bounded_regular_file(executable, max_bytes=200 * 1024 * 1024)),
                            no_network=True, no_automatic_download=True)

    def _ocr_correction_studio(self, payload: dict[str, Any], _state: dict[str, Any]) -> dict[str, Any]:
        original, corrected = _text(payload.get("original_text"), required=True), _text(payload.get("corrected_text"), required=True)
        source_hash = _sha(payload.get("source_hash"))
        if _hash(original.encode()) != source_hash:
            raise AddonStudioError("ocr_source_hash_mismatch", status_code=409)
        artifact = self._artifact("ocr_correction", f"ocr_{uuid.uuid4().hex[:12]}", corrected.encode(), "txt")
        return self._result("ocr", page_id=_id(payload.get("page_id"), "page_id"), source_hash=source_hash,
                            corrected_hash=_hash(corrected.encode()), changed=original != corrected, artifact=artifact,
                            original_preserved=True, correction_history_append_only=True)

    def _communications_importer(self, payload: dict[str, Any], _state: dict[str, Any]) -> dict[str, Any]:
        supplied = payload.get("messages")
        source_receipt: dict[str, Any] = {"mode": "supplied_export_rows"}
        if payload.get("export_relative_path"):
            source, content, source_hash = self._source_file(payload["export_relative_path"], max_bytes=64 * 1024 * 1024)
            source_receipt = {
                "mode": "matter_export_file",
                "file_name": source.name,
                "sha256": source_hash,
                "size": len(content),
            }
            suffix = source.suffix.casefold()
            if suffix == ".json":
                parsed = json.loads(content.decode("utf-8-sig"))
                supplied = parsed.get("messages") if isinstance(parsed, dict) else parsed
            elif suffix == ".csv":
                supplied = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
            else:
                raise AddonStudioError("communications_export_format_unsupported")
        normalized = []
        for row in _rows(supplied, limit=10_000):
            normalized.append({"message_id": _id(row.get("message_id"), "message_id"), "source_format": _text(row.get("source_format"), limit=30),
                               "timestamp": _text(row.get("timestamp"), limit=50), "sender_token": _id(row.get("sender_token"), "sender_token"),
                               "recipient_tokens": [_id(v, "recipient_token") for v in row.get("recipient_tokens") or []],
                               "text": _text(row.get("text")), "attachment_ids": [_id(v, "attachment_id") for v in row.get("attachment_ids") or []]})
        artifact = self._artifact(
            "communications",
            f"communications_{uuid.uuid4().hex[:12]}",
            json.dumps({"messages": normalized, "source_receipt": source_receipt}, indent=2).encode(),
            "json",
            media_type="application/json",
        )
        return self._result("communications", imported_count=len(normalized), message_hash=_hash(normalized), messages=normalized,
                            source_formats=sorted({row["source_format"] for row in normalized}), originals_modified=False,
                            source_receipt=source_receipt, artifact=artifact)

    def _evidence_relationship_graph(self, payload: dict[str, Any], _state: dict[str, Any]) -> dict[str, Any]:
        nodes = [{"node_id": _id(r.get("node_id"), "node_id"), "kind": _text(r.get("kind"), limit=50), "label": _text(r.get("label"), limit=200)} for r in _rows(payload.get("nodes"))]
        ids = {row["node_id"] for row in nodes}
        edges = []
        for row in _rows(payload.get("edges")):
            source, target = _id(row.get("source"), "source"), _id(row.get("target"), "target")
            if source not in ids or target not in ids:
                raise AddonStudioError("graph_edge_orphaned")
            edges.append({"edge_id": _id(row.get("edge_id"), "edge_id"), "source": source, "target": target,
                          "relationship": _text(row.get("relationship"), limit=80), "source_ref": _source_ref(row.get("source_ref"))})
        graph_hash = _hash([nodes, edges])
        artifact = self._artifact("evidence_graph", f"graph_{uuid.uuid4().hex[:12]}", json.dumps({"nodes": nodes, "edges": edges, "graph_hash": graph_hash}, indent=2).encode(), "json", media_type="application/json")
        return self._result("graph", nodes=nodes, edges=edges, node_count=len(nodes), edge_count=len(edges), graph_hash=graph_hash, artifact=artifact)

    def _local_model_manager(self, payload: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        action, model_id = _text(payload.get("action") or "register", limit=30), _id(payload.get("model_id"), "model_id")
        existing = [row for row in state["addons"]["local_model_manager"] if row.get("model_id") == model_id]
        if action == "register":
            _source, model_size, actual_hash, model_header = self._model_file(payload.get("artifact_relative_path"))
            expected_hash = _sha(payload.get("artifact_sha256"), required=False)
            if expected_hash and actual_hash != expected_hash:
                raise AddonStudioError("model_artifact_hash_mismatch", status_code=409)
            model_format = _text(payload.get("format") or "gguf", limit=20).casefold()
            if model_format == "gguf" and not model_header.startswith(b"GGUF"):
                raise AddonStudioError("model_format_mismatch", status_code=409)
            return self._result("model", action=action, model_id=model_id, artifact_sha256=actual_hash,
                                artifact_relative_path=str(payload.get("artifact_relative_path")), artifact_size=model_size,
                                format=model_format, integrity_verified=True, automatic_download=False, selected=False)
        if not existing:
            raise AddonStudioError("model_not_registered", status_code=404)
        if action == "verify":
            registered = next(row for row in reversed(existing) if row.get("action") == "register")
            _source, model_size, actual_hash, _header = self._model_file(registered.get("artifact_relative_path"))
            return self._result("model", action=action, model_id=model_id, integrity_verified=actual_hash == registered.get("artifact_sha256"),
                                artifact_size=model_size, artifact_sha256=actual_hash, automatic_download=False)
        if action in {"select", "remove"}:
            if payload.get("confirmed") is not True:
                raise AddonStudioError("model_change_confirmation_required", status_code=409)
            return self._result("model", action=action, model_id=model_id, selected=action == "select", removed=action == "remove", user_confirmed=payload.get("confirmed") is True)
        raise AddonStudioError("model_action_invalid")

    def _court_form_autofill(self, payload: dict[str, Any], _state: dict[str, Any]) -> dict[str, Any]:
        freshness = _text(payload.get("freshness") or "unknown", limit=30)
        if freshness != "fresh":
            return self._result("form", status="blocked", blockers=["form_not_confirmed_current"], form_id=_id(payload.get("form_id"), "form_id"))
        required = [_id(v, "field_id") for v in payload.get("required_fields") or []]
        values = {str(k): _text(v, limit=10_000) for k, v in dict(payload.get("values") or {}).items()}
        missing = [field for field in required if not values.get(field)]
        if missing:
            return self._result("form", status="blocked", blockers=["required_fields_missing"], missing_fields=missing)
        form_id = _id(payload.get("form_id"), "form_id")
        artifact = self._artifact("form_working_copy", f"form_{uuid.uuid4().hex[:12]}", json.dumps({"form_id": form_id, "values": values}, indent=2).encode(), "json", media_type="application/json")
        return self._result("form", status="completed_review_required", form_id=form_id, original_preserved=True, artifact=artifact, filing_ready=False)

    def _advanced_table_extraction(self, payload: dict[str, Any], _state: dict[str, Any]) -> dict[str, Any]:
        cells = []
        for row in _rows(payload.get("cells"), limit=20_000):
            cells.append({"row": max(0, int(row.get("row") or 0)), "column": max(0, int(row.get("column") or 0)),
                          "value": _text(row.get("value"), limit=10_000), "source_locator": _text(row.get("source_locator"), limit=200)})
        stream = io.StringIO(newline="")
        writer = csv.writer(stream)
        for row_index in sorted({cell["row"] for cell in cells}):
            row_cells = [cell for cell in cells if cell["row"] == row_index]
            maximum = max((cell["column"] for cell in row_cells), default=-1)
            writer.writerow([next((cell["value"] for cell in row_cells if cell["column"] == column), "") for column in range(maximum + 1)])
        artifact = self._artifact("table", f"table_{uuid.uuid4().hex[:12]}", stream.getvalue().encode("utf-8-sig"), "csv", media_type="text/csv; charset=utf-8")
        return self._result("table", cell_count=len(cells), cells=cells, artifact=artifact, provenance_complete=all(cell["source_locator"] for cell in cells))

    def _financial_document_intelligence(self, payload: dict[str, Any], _state: dict[str, Any]) -> dict[str, Any]:
        allowed = {"income", "housing", "childcare", "medical", "debt", "transfer", "other"}
        transactions = []
        threshold = abs(float(payload.get("review_threshold") or 1000))
        for row in _rows(payload.get("transactions"), limit=20_000):
            category = _text(row.get("category") or "other", limit=30).casefold()
            if category not in allowed:
                category = "other"
            amount = round(float(row.get("amount") or 0), 2)
            transactions.append({"transaction_id": _id(row.get("transaction_id"), "transaction_id"), "date": _text(row.get("date"), limit=30),
                                 "amount": amount, "category": category, "source_ref": _source_ref(row.get("source_ref")),
                                 "review_flag": abs(amount) >= threshold})
        totals = {category: round(sum(row["amount"] for row in transactions if row["category"] == category), 2) for category in sorted(allowed)}
        artifact = self._artifact("financial_review", f"financial_{uuid.uuid4().hex[:12]}", json.dumps({"transactions": transactions, "category_totals": totals}, indent=2).encode(), "json", media_type="application/json")
        return self._result("financial", transactions=transactions, category_totals=totals, artifact=artifact,
                            review_flag_count=sum(row["review_flag"] for row in transactions), legal_conclusion=False)

    def _semantic_order_comparison(self, payload: dict[str, Any], _state: dict[str, Any]) -> dict[str, Any]:
        base = {_id(row.get("term_id"), "term_id"): row for row in _rows(payload.get("base_terms"))}
        changed = {_id(row.get("term_id"), "term_id"): row for row in _rows(payload.get("changed_terms"))}
        comparisons = []
        for term_id in sorted(set(base) | set(changed)):
            before = _text(base.get(term_id, {}).get("text"))
            after = _text(changed.get(term_id, {}).get("text"))
            status = "added" if not before else "removed" if not after else "unchanged" if " ".join(before.split()).casefold() == " ".join(after.split()).casefold() else "modified_review_required"
            comparisons.append({"term_id": term_id, "before": before, "after": after, "status": status,
                                "source_refs": [_source_ref(base.get(term_id, {}).get("source_ref", {})), _source_ref(changed.get(term_id, {}).get("source_ref", {}))]})
        artifact = self._artifact("order_comparison", f"order_compare_{uuid.uuid4().hex[:12]}", json.dumps(comparisons, indent=2).encode(), "json", media_type="application/json")
        return self._result("order_compare", comparisons=comparisons, artifact=artifact, changed_count=sum(row["status"] != "unchanged" for row in comparisons), operative_order_decided=False)

    def _authority_update_center(self, payload: dict[str, Any], _state: dict[str, Any]) -> dict[str, Any]:
        manifest = dict(payload.get("manifest") or {})
        build_id = _id(manifest.get("build_id"), "build_id")
        sources = _rows(manifest.get("sources") or [])
        blockers = []
        for row in sources:
            parsed = urlparse(str(row.get("official_url") or ""))
            if parsed.scheme != "https" or (parsed.hostname or "").casefold() not in _OFFICIAL_AUTHORITY_HOSTS or not _SHA.fullmatch(str(row.get("sha256") or "")):
                blockers.append("source_metadata_incomplete")
                break
        return self._result("authority", build_id=build_id, source_count=len(sources), status="accepted_candidate" if not blockers else "blocked",
                            blockers=blockers, network_used=False, activation_performed=False, rollback_available=True)

    def _guided_research_builder(self, payload: dict[str, Any], _state: dict[str, Any]) -> dict[str, Any]:
        question = _text(payload.get("question"), required=True)
        issues = [_text(v, limit=160) for v in payload.get("issues") or []]
        classes = [value for value in payload.get("source_classes") or ["statutes", "rules", "opinions"] if value in {"statutes", "rules", "opinions", "forms", "federal"}]
        queries = [{"issue": issue, "query": f"{issue} Maine {question}"[:500], "source_classes": classes, "jurisdiction": "Maine"} for issue in issues or ["unclassified issue"]]
        artifact = self._artifact("research_plan", f"research_{uuid.uuid4().hex[:12]}", json.dumps({"question": question, "issues": issues, "queries": queries}, indent=2).encode(), "json", media_type="application/json")
        return self._result("research_plan", question=question, issues=issues, queries=queries, artifact=artifact, current_law_claimed=False)

    def _evidence_annotation_studio(self, payload: dict[str, Any], _state: dict[str, Any]) -> dict[str, Any]:
        record_id, source_hash = _id(payload.get("record_id"), "record_id"), _sha(payload.get("source_hash"))
        annotations = []
        for row in _rows(payload.get("annotations")):
            exact = _text(row.get("exact_text"), limit=20_000)
            annotations.append({"annotation_id": _id(row.get("annotation_id"), "annotation_id"), "kind": _text(row.get("kind"), limit=50),
                                "locator": _text(row.get("locator"), limit=200), "exact_text_hash": _hash(exact), "note": _text(row.get("note"), limit=4_000)})
        artifact = self._artifact("annotations", f"annotations_{uuid.uuid4().hex[:12]}", json.dumps(annotations, indent=2).encode(), "json", media_type="application/json")
        return self._result("annotations", record_id=record_id, source_hash=source_hash, annotations=annotations, artifact=artifact, original_modified=False)

    def _local_automation_scheduler(self, payload: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        action = _text(payload.get("action") or "schedule", limit=20)
        schedule_id = _id(payload.get("schedule_id"), "schedule_id")
        if action == "run":
            schedules = [row for row in state["addons"]["local_automation_scheduler"]
                         if row.get("schedule_id") == schedule_id and row.get("task") in _ALLOWED_RECIPE_TASKS]
            if not schedules:
                raise AddonStudioError("automation_schedule_not_found", status_code=404)
            if payload.get("confirmed") is not True:
                raise AddonStudioError("automation_run_confirmation_required", status_code=409)
            task = schedules[-1]["task"]
            task_receipt: dict[str, Any] = {"task": task, "executed_locally": True}
            if task == "matter_health":
                task_receipt.update(
                    {
                        "addon_result_count": sum(len(rows) for rows in state["addons"].values()),
                        "pending_review_count": sum(
                            1
                            for rows in state["addons"].values()
                            for row in rows
                            if not any(review.get("result_id") == row.get("result_id") for review in state.get("reviews", []))
                        ),
                    }
                )
            else:
                task_receipt["status"] = "delegated_to_canonical_local_worker"
            return self._result(
                "automation_run",
                schedule_id=schedule_id,
                task=task,
                task_receipt=task_receipt,
                status="completed_review_required",
                completed_at=_now(),
                external_side_effects=False,
                runs_only_while_app_active=True,
            )
        if action != "schedule":
            raise AddonStudioError("automation_action_invalid")
        task = _text(payload.get("task"), limit=40)
        if task not in _ALLOWED_RECIPE_TASKS:
            raise AddonStudioError("automation_task_not_allowed")
        interval = max(1, min(24 * 30, int(payload.get("interval_hours") or 24)))
        return self._result("schedule", schedule_id=schedule_id, task=task,
                            interval_hours=interval, next_due_at=(datetime.now(UTC) + timedelta(hours=interval)).isoformat().replace("+00:00", "Z"),
                            enabled=payload.get("enabled") is True, runs_only_while_app_active=True, external_side_effects=False)

    def _secure_reviewer_collaboration(self, payload: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        refs = [_id(value, "artifact_ref") for value in payload.get("artifact_refs") or []]
        known = {
            artifact.get("artifact_id")
            for rows in state["addons"].values()
            for result in rows
            for artifact in self._walk_artifacts(result)
        }
        missing = sorted(set(refs) - known)
        if not refs or missing:
            raise AddonStudioError("reviewer_bundle_artifact_missing", status_code=409)
        bundle = {"schema": "secure_reviewer_bundle_v1", "recipient_label": _text(payload.get("recipient_label"), limit=160),
                  "artifact_refs": refs, "created_at": _now(), "review_required": True, "live_matter_access": False}
        artifact = self._artifact("reviewer_bundle", f"bundle_{uuid.uuid4().hex[:12]}", json.dumps(bundle, sort_keys=True).encode(), "json", encrypted=True, media_type="application/json")
        return self._result("collaboration", artifact=artifact, artifact_ref_count=len(refs), encrypted=True, send_performed=False, live_matter_shared=False)

    def _matter_template_library(self, payload: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        action = _text(payload.get("action") or "create", limit=20).casefold()
        template_id = _id(payload.get("template_id"), "template_id")
        if action == "create":
            fields = [_id(value, "field_id") for value in payload.get("fields") or []]
            if not fields:
                raise AddonStudioError("template_fields_required")
            schema = {"template_id": template_id, "fields": fields, "created_at": _now()}
            artifact = self._artifact("matter_template", f"template_{uuid.uuid4().hex[:12]}", json.dumps(schema, indent=2).encode(), "json", media_type="application/json")
            return self._result("template", action=action, template_id=template_id, fields=fields, values={}, artifact=artifact, matter_data_in_template=False)
        if action != "apply":
            raise AddonStudioError("template_action_invalid")
        template = next((row for row in reversed(state["addons"]["matter_template_library"]) if row.get("template_id") == template_id and row.get("action") == "create"), None)
        if template is None:
            raise AddonStudioError("matter_template_not_found", status_code=404)
        fields = list(template.get("fields") or [])
        values = {str(key): _text(value, limit=10_000) for key, value in dict(payload.get("values") or {}).items() if str(key) in fields}
        missing = [field for field in fields if not values.get(field)]
        if missing:
            return self._result("template_instance", action=action, template_id=template_id, status="blocked", blockers=["template_values_missing"], missing_fields=missing)
        artifact = self._artifact("matter_template_instance", f"template_instance_{uuid.uuid4().hex[:12]}", json.dumps({"template_id": template_id, "values": values}, indent=2).encode(), "json", media_type="application/json")
        return self._result("template_instance", action=action, template_id=template_id, fields=fields, values=values, artifact=artifact, matter_data_in_template=True)

    def _conflict_entity_resolver(self, payload: dict[str, Any], _state: dict[str, Any]) -> dict[str, Any]:
        mentions = [{"mention_id": _id(row.get("mention_id"), "mention_id"), "display": _text(row.get("display"), limit=200), "source_ref": _source_ref(row.get("source_ref"))} for row in _rows(payload.get("mentions"))]
        groups: dict[str, list[str]] = {}
        for row in mentions:
            key = re.sub(r"[^a-z0-9]", "", row["display"].casefold())
            groups.setdefault(key, []).append(row["mention_id"])
        candidates = [{"candidate_id": f"entity_{_hash(key)[:12]}", "mention_ids": ids, "status": "confirmed_merge" if payload.get("confirmed") is True else "review_required"} for key, ids in groups.items()]
        return self._result("entities", mentions=mentions, candidates=candidates, automatic_merge=False, confirmed=payload.get("confirmed") is True)

    def _desktop_notification_center(self, payload: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        action = _text(payload.get("action") or "create", limit=20)
        if action == "acknowledge":
            notification_id = _id(payload.get("notification_id"), "notification_id")
            known = {
                row.get("notification_id")
                for result in state["addons"]["desktop_notification_center"]
                for row in result.get("notifications", [])
            }
            if notification_id not in known:
                raise AddonStudioError("notification_not_found", status_code=404)
            return self._result("notification_acknowledgement", notification_id=notification_id, acknowledged=True)
        if action != "create":
            raise AddonStudioError("notification_action_invalid")
        notifications = []
        for row in _rows(payload.get("events")):
            event_id = _id(row.get("event_id"), "event_id")
            severity = _text(row.get("severity") or "info", limit=20)
            if severity not in {"info", "attention", "blocked"}:
                severity = "attention"
            notifications.append({"notification_id": f"notice_{event_id}", "event_id": event_id, "severity": severity,
                                  "title": _text(row.get("title"), limit=240), "corrective_action": _text(row.get("corrective_action"), limit=1_000), "acknowledged": False})
        return self._result("notifications", notifications=notifications, notification_count=len(notifications), os_notification_sent=False)

    def _courtroom_bundle_exporter(self, payload: dict[str, Any], _state: dict[str, Any]) -> dict[str, Any]:
        cards = _rows(payload.get("cards"), limit=500)
        safe_cards = []
        for row in cards:
            safe_cards.append({"card_id": _id(row.get("card_id"), "card_id"), "title": _text(row.get("title"), limit=240),
                               "display_text": _text(row.get("display_text"), limit=20_000), "source_ref": _source_ref(row.get("source_ref"))})
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps({"cards": safe_cards, "private_notes_included": False, "review_required": True}, indent=2))
            archive.writestr(
                "index.html",
                "<!doctype html><meta charset=utf-8><title>Courtroom review bundle</title>"
                "<h1>Review-required source cards</h1>"
                + "".join(
                    f"<h2>{html.escape(row['title'])}</h2><p>{html.escape(row['display_text'])}</p>"
                    for row in safe_cards
                ),
            )
        artifact = self._artifact("courtroom_bundle", f"courtroom_{uuid.uuid4().hex[:12]}", stream.getvalue(), "zip", media_type="application/zip")
        return self._result("courtroom_bundle", card_count=len(safe_cards), artifact=artifact, private_notes_included=False, offline=True)

    def _voice_drafting_commands(self, payload: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        transcript_result_id = str(payload.get("transcript_result_id") or "").strip().casefold()
        source_binding: dict[str, Any] = {"mode": "supplied_reviewed_text"}
        if transcript_result_id:
            safe_transcript_id = _id(transcript_result_id, "transcript_result_id")
            source_result = next((row for row in state["addons"]["native_whisper_transcription"] if row.get("result_id") == safe_transcript_id), None)
            if source_result is None:
                raise AddonStudioError("voice_transcript_result_not_found", status_code=404)
            artifact_meta, raw = self.artifact_content("native_whisper_transcription", safe_transcript_id, source_result["artifact"]["artifact_id"])
            transcript = _text(raw.decode("utf-8"), required=True)
            source_binding = {"mode": "native_transcript", "result_id": safe_transcript_id, "artifact_id": artifact_meta["artifact_id"], "sha256": source_result["transcript_sha256"]}
        else:
            transcript = _text(payload.get("transcript_text"), required=True)
        replacements = {" new paragraph ": "\n\n", " comma ": ", ", " period ": ". "}
        draft = f" {transcript} "
        for command, replacement in replacements.items():
            draft = re.sub(re.escape(command), replacement, draft, flags=re.IGNORECASE)
        draft = draft.strip()
        artifact = self._artifact("voice_draft", f"voice_{uuid.uuid4().hex[:12]}", draft.encode(), "txt", media_type="text/plain; charset=utf-8")
        return self._result("voice_draft", transcript_sha256=_hash(transcript.encode()), draft_sha256=_hash(draft.encode()), artifact=artifact,
                            source_binding=source_binding, commands_applied=sum(transcript.casefold().count(command.strip()) for command in replacements), filing_ready=False)

    def _extension_sdk_permission_center(self, payload: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        action = _text(payload.get("action") or "register", limit=20).casefold()
        if action == "status":
            registered = [row for row in state["addons"]["extension_sdk_permission_center"] if row.get("extension_id")]
            return self._result(
                "extension_permissions",
                status="permission_center_ready",
                allowed_permissions=sorted(_ALLOWED_EXTENSION_PERMISSIONS),
                installed_extension_count=len({row.get("extension_id") for row in registered}),
                arbitrary_network_access=False,
                extensions_default_enabled=False,
            )
        if action == "permission_review":
            extension_id = _id(payload.get("extension_id"), "extension_id")
            permissions = sorted({_text(value, limit=80) for value in payload.get("permissions") or []})
            if not permissions:
                raise AddonStudioError("extension_permissions_required")
            disallowed = sorted(set(permissions) - _ALLOWED_EXTENSION_PERMISSIONS)
            return self._result(
                "extension_permission_review",
                action=action,
                extension_id=extension_id,
                permissions=permissions,
                disallowed_permissions=disallowed,
                status="ready_for_signature" if not disallowed else "blocked",
                blockers=["extension_permission_not_allowed"] if disallowed else [],
                signature_verified=False,
                enabled=False,
                arbitrary_network_access=False,
            )
        if action in {"enable", "revoke"}:
            extension_id = _id(payload.get("extension_id"), "extension_id")
            registered = next((row for row in reversed(state["addons"]["extension_sdk_permission_center"]) if row.get("extension_id") == extension_id and row.get("signature_verified") is True), None)
            if registered is None:
                raise AddonStudioError("extension_not_registered", status_code=404)
            if payload.get("confirmed") is not True:
                raise AddonStudioError("extension_change_confirmation_required", status_code=409)
            return self._result("extension_state", action=action, extension_id=extension_id,
                                status="enabled" if action == "enable" else "revoked",
                                enabled=action == "enable", permissions=registered.get("permissions", []),
                                arbitrary_network_access=False, revocable=True)
        if action != "register":
            raise AddonStudioError("extension_action_invalid")
        manifest = dict(payload.get("manifest") or {})
        extension_id = _id(manifest.get("extension_id"), "extension_id")
        permissions = sorted({_text(value, limit=80) for value in manifest.get("permissions") or []})
        disallowed = sorted(set(permissions) - _ALLOWED_EXTENSION_PERMISSIONS)
        canonical = json.dumps({"extension_id": extension_id, "version": _text(manifest.get("version"), limit=30),
                                "artifact_sha256": _sha(manifest.get("artifact_sha256")), "permissions": permissions}, sort_keys=True, separators=(",", ":")).encode()
        verified = False
        try:
            public_key = base64.b64decode(_text(payload.get("public_key"), limit=500), validate=True)
            signature = base64.b64decode(_text(payload.get("signature"), limit=500), validate=True)
            Ed25519PublicKey.from_public_bytes(public_key).verify(signature, canonical)
            verified = True
        except Exception:
            verified = False
        status = "registered_disabled" if verified and not disallowed else "blocked"
        blockers = (["extension_signature_invalid"] if not verified else []) + (["extension_permission_not_allowed"] if disallowed else [])
        return self._result("extension", extension_id=extension_id, status=status, signature_verified=verified,
                            permissions=permissions, disallowed_permissions=disallowed, blockers=blockers, enabled=False,
                            arbitrary_network_access=False, revocable=True)
