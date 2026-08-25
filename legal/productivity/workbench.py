"""Encrypted, local-only productivity suite.

The suite deliberately stores metadata and review artifacts, not legal conclusions.
Every mutation is matter scoped, encrypted at rest, and chained into an append-only
history.  External sending, filing, calendar writes, and silent folder watching are
never performed by these services.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import uuid
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from legal.model_orchestration.hardware import profile_hardware
from legal.security.durable_io import (
    atomic_write_bytes,
    exclusive_file_lock,
    read_bounded_regular_file,
)
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path


SCHEMA_VERSION = "maine_family_law_llm.productivity_suite.v1"
WORKSPACE_FOLDER = "45_PRODUCTIVITY_STUDIO"
_ID = re.compile(r"[a-z][a-z0-9_-]{2,79}\Z")
_SHA256 = re.compile(r"[a-f0-9]{64}\Z")
_ALLOWED_RECIPE_STEPS = frozenset(
    {
        "inventory_records",
        "privacy_scan",
        "ocr_candidates",
        "build_timeline",
        "review_contradictions",
        "review_missing_records",
        "verify_sources",
        "prepare_draft",
        "review_blockers",
        "build_packet",
    }
)
_MAX_STATE_BYTES = 16 * 1024 * 1024
_MAX_BACKUP_FILE = 2 * 1024 * 1024
_MAX_BACKUP_TOTAL = 32 * 1024 * 1024


class ProductivitySuiteError(RuntimeError):
    def __init__(self, code: str, message: str | None = None, *, status_code: int = 400):
        super().__init__(message or code)
        self.code = code
        self.message = message or code.replace("_", " ")
        self.status_code = status_code


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _digest(value: Any) -> str:
    raw = value if isinstance(value, bytes) else json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _safe_id(value: Any, field: str) -> str:
    result = str(value or "").strip().casefold()
    if not _ID.fullmatch(result):
        raise ProductivitySuiteError(f"{field}_invalid")
    return result


def _text(value: Any, *, limit: int = 2_000) -> str:
    result = str(value or "").strip()
    if len(result) > limit:
        raise ProductivitySuiteError("text_limit_exceeded")
    return result


def _sha(value: Any, field: str = "source_hash", *, required: bool = True) -> str:
    result = str(value or "").strip().casefold()
    if (required or result) and not _SHA256.fullmatch(result):
        raise ProductivitySuiteError(f"{field}_invalid")
    return result


def _list(value: Any, *, limit: int = 300) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > limit:
        raise ProductivitySuiteError("list_invalid")
    return value


def _ics_escape(value: Any) -> str:
    return (
        _text(value, limit=500)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r", "")
        .replace("\n", "\\n")
    )


def _ics_datetime(value: Any) -> str:
    text = _text(value, limit=40)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return f"DTSTART;VALUE=DATE:{text.replace('-', '')}"
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProductivitySuiteError("calendar_date_invalid") from exc
    if parsed.tzinfo is None:
        return f"DTSTART:{parsed.strftime('%Y%m%dT%H%M%S')}"
    return f"DTSTART:{parsed.astimezone(UTC).strftime('%Y%m%dT%H%M%SZ')}"


class ProductivitySuiteStore:
    """One encrypted state boundary shared by ten tightly related capabilities."""

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).resolve()
        self.root = self.case_root / WORKSPACE_FOLDER
        if (
            not self.case_root.is_dir()
            or self.case_root.is_symlink()
            or (self.root.exists() and self.root.is_symlink())
        ):
            raise ProductivitySuiteError(
                "productivity_workspace_unavailable",
                "The active matter productivity workspace is unavailable.",
                status_code=409,
            )
        self.encryptor = LocalEnvelopeEncryptor(
            encryption_key
            or os.environ.get("MAINE_MATTER_STORE_KEY")
            or "local-development-key-change-me"
        )
        self.scope = hashlib.sha256(str(self.case_root).encode("utf-8")).hexdigest()[:24]

    @property
    def state_path(self) -> Path:
        return self.root / "productivity.json.enc"

    @property
    def lock_path(self) -> Path:
        return self.root / ".productivity.lock"

    @property
    def artifacts_root(self) -> Path:
        return self.root / "artifacts"

    def _initial(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA_VERSION,
            "scope": self.scope,
            "matter_id": self.case_root.name,
            "revision": 0,
            "inbox_configurations": [],
            "inbox_receipts": [],
            "recipes": [],
            "recipe_runs": [],
            "calendar_exports": [],
            "hardware_plans": [],
            "pinboard_items": [],
            "redaction_projects": [],
            "next_actions": [],
            "courtroom_sessions": [],
            "backup_schedules": [],
            "backups": [],
            "history": [],
        }

    def _load(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return self._initial()
        try:
            envelope = strict_json_load_path(
                self.state_path, max_bytes=_MAX_STATE_BYTES, require_object=True
            )
            value = self.encryptor.decrypt_json(envelope)
        except Exception as exc:
            raise ProductivitySuiteError(
                "productivity_state_unavailable",
                "The encrypted productivity state could not be opened.",
                status_code=409,
            ) from exc
        if value.get("schema") != SCHEMA_VERSION or value.get("scope") != self.scope:
            raise ProductivitySuiteError(
                "cross_matter_access_denied", "The requested matter scope does not match.", status_code=404
            )
        return value

    def _save(self, value: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(
            self.state_path,
            json.dumps(self.encryptor.encrypt_json(value), sort_keys=True).encode("utf-8"),
            mode=0o600,
        )

    def _mutate(self, action: str, ids: list[str], callback):  # type: ignore[no-untyped-def]
        with exclusive_file_lock(self.lock_path):
            value = self._load()
            result = callback(value)
            previous = value["history"][-1]["hash"] if value["history"] else ""
            event = {
                "event_id": f"productivity_{uuid.uuid4().hex}",
                "at": _now(),
                "action": action,
                "ids": ids,
                "previous_hash": previous,
                "review_required": True,
            }
            event["hash"] = _digest(event)
            value["history"].append(event)
            value["revision"] += 1
            self._save(value)
            return result

    def _artifact(self, kind: str, artifact_id: str, content: bytes, suffix: str) -> dict[str, Any]:
        safe_kind = _safe_id(kind, "artifact_kind")
        safe_id = _safe_id(artifact_id, "artifact_id")
        folder = self.artifacts_root / safe_kind
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{safe_id}.{suffix}"
        if path.exists() and path.is_symlink():
            raise ProductivitySuiteError("artifact_symlink_refused", status_code=409)
        atomic_write_bytes(path, content, mode=0o600)
        return {
            "artifact_id": safe_id,
            "kind": safe_kind,
            "relative_path": f"{WORKSPACE_FOLDER}/artifacts/{safe_kind}/{path.name}",
            "sha256": _digest(content),
            "size": len(content),
            "review_required": True,
        }

    def summary(self) -> dict[str, Any]:
        value = self._load()
        now = datetime.now(UTC)
        due_backup_schedules = []
        for schedule in value["backup_schedules"]:
            if not schedule.get("enabled"):
                continue
            try:
                due_at = datetime.fromisoformat(str(schedule.get("next_due_at") or "").replace("Z", "+00:00"))
            except ValueError:
                due_at = now
            if due_at <= now:
                due_backup_schedules.append(schedule["schedule_id"])
        counts = {
            "inbox_configurations": len(value["inbox_configurations"]),
            "inbox_receipts": len(value["inbox_receipts"]),
            "recipes": len(value["recipes"]),
            "recipe_runs": len(value["recipe_runs"]),
            "calendar_exports": len(value["calendar_exports"]),
            "hardware_plans": len(value["hardware_plans"]),
            "pinboard_items": len(value["pinboard_items"]),
            "redaction_projects": len(value["redaction_projects"]),
            "next_actions": len(value["next_actions"]),
            "courtroom_sessions": len(value["courtroom_sessions"]),
            "backup_schedules": len(value["backup_schedules"]),
            "backups": len(value["backups"]),
        }
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "review_required",
            "matter_id": value["matter_id"],
            "revision": value["revision"],
            "counts": counts,
            "capabilities": [
                "smart_matter_inbox",
                "saved_workflow_recipes",
                "local_media_transcription",
                "calendar_interoperability",
                "hardware_optimizer",
                "research_pinboard",
                "redaction_studio",
                "matter_next_actions",
                "courtroom_presentation",
                "encrypted_automatic_backup",
            ],
            "local_only": True,
            "due_backup_schedules": due_backup_schedules,
            "automatic_backup_mode": "while_app_is_active",
            "review_required": True,
            "history_tail": value["history"][-20:],
        }

    def configure_inbox(self, payload: dict[str, Any]) -> dict[str, Any]:
        inbox_id = _safe_id(payload.get("inbox_id"), "inbox_id")
        label = _text(payload.get("label") or inbox_id, limit=160)
        watch_token = _text(payload.get("watch_token"), limit=160)
        if not watch_token:
            raise ProductivitySuiteError("watch_token_required")

        def callback(value):
            row = {
                "inbox_id": inbox_id,
                "label": label,
                "watch_token": watch_token,
                "allowed_extensions": sorted(
                    {str(x).lower().lstrip(".") for x in _list(payload.get("allowed_extensions"), limit=40) if str(x).strip()}
                ),
                "automatic_import": False,
                "scan_requires_user_action": True,
                "created_at": _now(),
                "review_required": True,
            }
            value["inbox_configurations"] = [
                existing for existing in value["inbox_configurations"] if existing["inbox_id"] != inbox_id
            ] + [row]
            return deepcopy(row)

        return self._mutate("inbox_configured", [inbox_id], callback)

    def scan_inbox(self, inbox_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        safe_inbox_id = _safe_id(inbox_id, "inbox_id")
        candidates = _list(payload.get("candidates"), limit=500)

        def callback(value):
            config = next((x for x in value["inbox_configurations"] if x["inbox_id"] == safe_inbox_id), None)
            if config is None:
                raise ProductivitySuiteError("inbox_not_found", status_code=404)
            known_hashes = {
                item["sha256"]
                for receipt in value["inbox_receipts"]
                for item in receipt.get("candidates", [])
                if item.get("sha256")
            }
            rows = []
            for raw in candidates:
                if not isinstance(raw, dict):
                    raise ProductivitySuiteError("inbox_candidate_invalid")
                extension = str(raw.get("extension") or "").lower().lstrip(".")
                digest = _sha(raw.get("sha256"))
                rows.append(
                    {
                        "record_id": _safe_id(raw.get("record_id"), "record_id"),
                        "display_name": _text(raw.get("display_name"), limit=240),
                        "extension": extension,
                        "sha256": digest,
                        "size": max(0, int(raw.get("size") or 0)),
                        "classification": "exact_duplicate" if digest in known_hashes else "new_candidate",
                        "allowed": not config["allowed_extensions"] or extension in config["allowed_extensions"],
                        "source_receipt_required": True,
                    }
                )
            receipt = {
                "receipt_id": f"inbox_{uuid.uuid4().hex[:20]}",
                "inbox_id": safe_inbox_id,
                "scanned_at": _now(),
                "candidates": rows,
                "candidate_count": len(rows),
                "new_count": sum(x["classification"] == "new_candidate" for x in rows),
                "duplicate_count": sum(x["classification"] == "exact_duplicate" for x in rows),
                "import_performed": False,
                "review_required": True,
            }
            receipt["receipt_hash"] = _digest(receipt)
            value["inbox_receipts"].append(receipt)
            return deepcopy(receipt)

        return self._mutate("inbox_scanned", [safe_inbox_id], callback)

    def save_recipe(self, payload: dict[str, Any]) -> dict[str, Any]:
        recipe_id = _safe_id(payload.get("recipe_id"), "recipe_id")
        steps = [_safe_id(x, "recipe_step") for x in _list(payload.get("steps"), limit=20)]
        if not steps or any(step not in _ALLOWED_RECIPE_STEPS for step in steps):
            raise ProductivitySuiteError("recipe_steps_invalid")

        def callback(value):
            row = {
                "recipe_id": recipe_id,
                "label": _text(payload.get("label") or recipe_id, limit=160),
                "steps": steps,
                "requires_confirmation": True,
                "external_actions": False,
                "created_at": _now(),
                "review_required": True,
            }
            value["recipes"] = [
                existing for existing in value["recipes"] if existing["recipe_id"] != recipe_id
            ] + [row]
            return deepcopy(row)

        return self._mutate("recipe_saved", [recipe_id], callback)

    def run_recipe(self, recipe_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        safe_recipe_id = _safe_id(recipe_id, "recipe_id")
        if payload.get("confirmed") is not True:
            raise ProductivitySuiteError("recipe_confirmation_required", status_code=409)

        def callback(value):
            recipe = next((x for x in value["recipes"] if x["recipe_id"] == safe_recipe_id), None)
            if recipe is None:
                raise ProductivitySuiteError("recipe_not_found", status_code=404)
            run_id = f"run_{uuid.uuid4().hex[:20]}"
            results = [self._run_recipe_step(step, value) for step in recipe["steps"]]
            row = {
                "run_id": run_id,
                "recipe_id": safe_recipe_id,
                "started_at": _now(),
                "completed_at": _now(),
                "status": "completed_review_required",
                "results": results,
                "input_refs": _list(payload.get("input_refs"), limit=100),
                "cancelable": False,
                "review_required": True,
            }
            row["receipt_hash"] = _digest(row)
            value["recipe_runs"].append(row)
            return deepcopy(row)

        return self._mutate("recipe_run", [safe_recipe_id], callback)

    def _run_recipe_step(self, step: str, value: dict[str, Any]) -> dict[str, Any]:
        """Produce bounded, honest local output instead of a receipt-only success."""

        if step == "inventory_records":
            rows = []
            for path in sorted(self.case_root.rglob("*")):
                if not path.is_file() or path.is_symlink() or WORKSPACE_FOLDER in path.parts:
                    continue
                try:
                    raw = read_bounded_regular_file(path, max_bytes=_MAX_BACKUP_FILE)
                except Exception:
                    continue
                rows.append({"suffix": path.suffix.casefold(), "size": len(raw), "sha256": _digest(raw)})
            return {
                "step": step,
                "status": "completed_review_required",
                "record_count": len(rows),
                "total_bytes": sum(row["size"] for row in rows),
                "inventory_hash": _digest(rows),
                "output_scope": "matter_local_metadata",
            }
        if step == "privacy_scan":
            patterns = (re.compile(rb"\b[^\s@]+@[^\s@]+\.[^\s@]+\b"), re.compile(rb"\b\d{3}[-.) ]+\d{3}[-. ]+\d{4}\b"))
            candidates = 0
            scanned = 0
            for path in sorted(self.case_root.rglob("*")):
                if not path.is_file() or path.is_symlink() or path.suffix.casefold() not in {".txt", ".md", ".csv", ".json"}:
                    continue
                try:
                    raw = read_bounded_regular_file(path, max_bytes=_MAX_BACKUP_FILE)
                except Exception:
                    continue
                scanned += 1
                candidates += sum(len(pattern.findall(raw)) for pattern in patterns)
            return {
                "step": step,
                "status": "completed_review_required",
                "files_scanned": scanned,
                "candidate_count": candidates,
                "private_text_returned": False,
                "output_scope": "matter_local_metadata",
            }
        prerequisites = {
            "ocr_candidates": len(value["inbox_receipts"]),
            "build_timeline": len(value["calendar_exports"]),
            "review_contradictions": 0,
            "review_missing_records": len(value["inbox_receipts"]),
            "verify_sources": len(value["pinboard_items"]),
            "prepare_draft": 0,
            "review_blockers": len(value["next_actions"]),
            "build_packet": 0,
        }
        count = prerequisites.get(step, 0)
        return {
            "step": step,
            "status": "completed_review_required" if count else "needs_prerequisite_review",
            "candidate_count": count,
            "output_scope": "matter_local_metadata",
        }

    def export_calendar(self, payload: dict[str, Any]) -> dict[str, Any]:
        export_id = _safe_id(payload.get("export_id"), "export_id")
        events = _list(payload.get("events"), limit=500)
        if not events:
            raise ProductivitySuiteError("calendar_events_required")
        lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//TAHAI//Maine Family Law LLM//EN", "CALSCALE:GREGORIAN"]
        normalized = []
        for raw in events:
            if not isinstance(raw, dict):
                raise ProductivitySuiteError("calendar_event_invalid")
            event_id = _safe_id(raw.get("event_id"), "event_id")
            date_line = _ics_datetime(raw.get("date_time"))
            normalized.append(
                {
                    "event_id": event_id,
                    "date_time": _text(raw.get("date_time"), limit=40),
                    "summary": _text(raw.get("summary"), limit=300),
                    "source_ref": dict(raw.get("source_ref") or {}),
                }
            )
            lines.extend(
                [
                    "BEGIN:VEVENT",
                    f"UID:{event_id}@maine-family-law-llm.local",
                    f"DTSTAMP:{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}",
                    date_line,
                    f"SUMMARY:{_ics_escape(raw.get('summary'))}",
                    "DESCRIPTION:Candidate date exported for human review. Verify against the source and current rules.",
                    "END:VEVENT",
                ]
            )
        lines.append("END:VCALENDAR")
        content = ("\r\n".join(lines) + "\r\n").encode("utf-8")
        artifact = self._artifact("calendar", export_id, content, "ics")

        def callback(value):
            row = {
                "export_id": export_id,
                "created_at": _now(),
                "events": normalized,
                "artifact": artifact,
                "calendar_account_write": False,
                "review_required": True,
            }
            value["calendar_exports"].append(row)
            return deepcopy(row)

        return self._mutate("calendar_exported", [export_id], callback)

    def optimize_hardware(self, payload: dict[str, Any]) -> dict[str, Any]:
        task = _text(payload.get("task") or "general_chat", limit=80)
        profile = profile_hardware(self.case_root).as_dict()
        memory = int(profile.get("available_memory_bytes") or 0)
        requested_context = max(0, int(payload.get("requested_context_tokens") or 0))
        safe_context = int(profile.get("recommended_context_limit") or 4096)
        context = min(requested_context or safe_context, safe_context)
        tier = "compact" if memory and memory < 8 * 1024**3 else "balanced" if memory < 24 * 1024**3 else "large_local"
        plan_id = f"hardware_{uuid.uuid4().hex[:20]}"
        row = {
            "plan_id": plan_id,
            "task": task,
            "profile": profile,
            "recommended_model_tier": tier,
            "context_tokens": context,
            "concurrency": int(profile.get("recommended_concurrency") or 1),
            "fallback": "deterministic_local",
            "automatic_download": False,
            "created_at": _now(),
            "review_required": True,
        }

        def callback(value):
            value["hardware_plans"].append(row)
            return deepcopy(row)

        return self._mutate("hardware_optimized", [plan_id], callback)

    def add_pinboard_item(self, payload: dict[str, Any]) -> dict[str, Any]:
        item_id = _safe_id(payload.get("item_id"), "item_id")
        source = dict(payload.get("source_ref") or {})
        source_id = _safe_id(source.get("source_id") or source.get("record_id"), "source_id")
        exact_span = _text(source.get("exact_span"), limit=4_000)
        if not exact_span:
            raise ProductivitySuiteError("exact_source_span_required")

        def callback(value):
            if any(row["item_id"] == item_id for row in value["pinboard_items"]):
                raise ProductivitySuiteError("pinboard_item_conflict", status_code=409)
            row = {
                "item_id": item_id,
                "board": _text(payload.get("board") or "General", limit=120),
                "title": _text(payload.get("title") or item_id, limit=240),
                "note": _text(payload.get("note"), limit=4_000),
                "lane": _text(payload.get("lane") or "private_record", limit=80),
                "source_ref": {
                    "source_id": source_id,
                    "source_hash": _sha(source.get("source_hash"), required=False),
                    "exact_span": exact_span,
                    "locator": _text(source.get("locator"), limit=180),
                    "freshness": _text(source.get("freshness") or "unknown", limit=80),
                },
                "created_at": _now(),
                "review_required": True,
            }
            value["pinboard_items"].append(row)
            return deepcopy(row)

        return self._mutate("pinboard_item_added", [item_id, source_id], callback)

    def create_redaction_project(self, payload: dict[str, Any]) -> dict[str, Any]:
        project_id = _safe_id(payload.get("project_id"), "project_id")
        record_id = _safe_id(payload.get("record_id"), "record_id")
        source_hash = _sha(payload.get("source_hash"))
        candidates = []
        for raw in _list(payload.get("candidates"), limit=500):
            if not isinstance(raw, dict):
                raise ProductivitySuiteError("redaction_candidate_invalid")
            candidates.append(
                {
                    "candidate_id": _safe_id(raw.get("candidate_id"), "candidate_id"),
                    "category": _text(raw.get("category"), limit=80),
                    "exact_text_hash": _sha(raw.get("exact_text_hash")),
                    "locator": _text(raw.get("locator"), limit=180),
                    "decision": "pending_review",
                }
            )

        def callback(value):
            row = {
                "project_id": project_id,
                "record_id": record_id,
                "source_hash": source_hash,
                "candidates": candidates,
                "original_immutable": True,
                "derivative_created": False,
                "privacy_review_complete": False,
                "created_at": _now(),
                "review_required": True,
            }
            value["redaction_projects"].append(row)
            return deepcopy(row)

        return self._mutate("redaction_project_created", [project_id, record_id], callback)

    def finalize_redaction_project(self, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        safe_project_id = _safe_id(project_id, "project_id")
        if payload.get("confirmed") is not True:
            raise ProductivitySuiteError("redaction_confirmation_required", status_code=409)
        working_text = _text(payload.get("working_text"), limit=200_000)
        replacements = _list(payload.get("replacements"), limit=500)

        def callback(value):
            project = next((row for row in value["redaction_projects"] if row["project_id"] == safe_project_id), None)
            if project is None:
                raise ProductivitySuiteError("redaction_project_not_found", status_code=404)
            if _digest(working_text.encode("utf-8")) != project["source_hash"]:
                raise ProductivitySuiteError("redaction_source_hash_mismatch", status_code=409)
            derivative = working_text
            accepted_ids = []
            for raw in replacements:
                if not isinstance(raw, dict):
                    raise ProductivitySuiteError("redaction_replacement_invalid")
                candidate_id = _safe_id(raw.get("candidate_id"), "candidate_id")
                candidate = next((row for row in project["candidates"] if row["candidate_id"] == candidate_id), None)
                exact_text = _text(raw.get("exact_text"), limit=4_000)
                replacement = _text(raw.get("replacement") or "[REDACTED]", limit=200)
                if candidate is None or _digest(exact_text.encode("utf-8")) != candidate["exact_text_hash"]:
                    raise ProductivitySuiteError("redaction_candidate_hash_mismatch", status_code=409)
                if exact_text not in derivative:
                    raise ProductivitySuiteError("redaction_candidate_not_found", status_code=409)
                derivative = derivative.replace(exact_text, replacement)
                candidate["decision"] = "accepted_by_user"
                accepted_ids.append(candidate_id)
            if not accepted_ids:
                raise ProductivitySuiteError("redaction_replacement_required")
            artifact = self._artifact("redaction", safe_project_id, derivative.encode("utf-8"), "txt")
            project["derivative_created"] = True
            project["privacy_review_complete"] = True
            project["reviewed_at"] = _now()
            project["artifact"] = artifact
            return {
                "project_id": safe_project_id,
                "artifact": artifact,
                "accepted_candidate_ids": accepted_ids,
                "original_immutable": True,
                "privacy_review_complete": True,
                "filing_ready": False,
                "review_required": True,
            }

        return self._mutate("redaction_derivative_created", [safe_project_id], callback)

    def refresh_next_actions(self, payload: dict[str, Any]) -> dict[str, Any]:
        blockers = _list(payload.get("blockers"), limit=300)

        def callback(value):
            rows = []
            for index, raw in enumerate(blockers, start=1):
                if not isinstance(raw, dict):
                    raise ProductivitySuiteError("blocker_invalid")
                rows.append(
                    {
                        "action_id": _safe_id(raw.get("action_id") or f"action_{index:03d}", "action_id"),
                        "priority": max(0, min(3, int(raw.get("priority") or 2))),
                        "title": _text(raw.get("title"), limit=240),
                        "reason": _text(raw.get("reason"), limit=1_000),
                        "source_ref": dict(raw.get("source_ref") or {}),
                        "corrective_action": _text(raw.get("corrective_action"), limit=1_000),
                        "status": "open_review_required",
                    }
                )
            if not value["pinboard_items"]:
                rows.append({"action_id": "review_sources", "priority": 2, "title": "Pin at least one exact source", "reason": "No source is pinned for review.", "source_ref": {}, "corrective_action": "Open Research Pinboard and save an exact source span.", "status": "open_review_required"})
            rows.sort(key=lambda x: (x["priority"], x["action_id"]))
            value["next_actions"] = rows
            return {
                "status": "review_required" if rows else "clear",
                "actions": deepcopy(rows),
                "generated_at": _now(),
                "legal_priority_determination": False,
                "review_required": True,
            }

        return self._mutate("next_actions_refreshed", [], callback)

    def create_courtroom_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        session_id = _safe_id(payload.get("session_id"), "session_id")
        cards = []
        for raw in _list(payload.get("cards"), limit=200):
            if not isinstance(raw, dict):
                raise ProductivitySuiteError("presentation_card_invalid")
            source = dict(raw.get("source_ref") or {})
            cards.append(
                {
                    "card_id": _safe_id(raw.get("card_id"), "card_id"),
                    "title": _text(raw.get("title"), limit=240),
                    "display_text": _text(raw.get("display_text"), limit=4_000),
                    "source_ref": {
                        "source_id": _safe_id(source.get("source_id") or source.get("record_id"), "source_id"),
                        "source_hash": _sha(source.get("source_hash"), required=False),
                        "exact_span": _text(source.get("exact_span"), limit=4_000),
                    },
                    "private_notes_exposed": False,
                }
            )
        if not cards:
            raise ProductivitySuiteError("presentation_cards_required")

        def callback(value):
            row = {
                "session_id": session_id,
                "label": _text(payload.get("label") or session_id, limit=180),
                "cards": cards,
                "active_card_id": cards[0]["card_id"],
                "display_mode": "source_bound_full_screen",
                "keyboard_navigation": True,
                "private_notes_hidden": True,
                "created_at": _now(),
                "review_required": True,
            }
            value["courtroom_sessions"].append(row)
            return deepcopy(row)

        return self._mutate("courtroom_session_created", [session_id], callback)

    def save_backup_schedule(self, payload: dict[str, Any]) -> dict[str, Any]:
        schedule_id = _safe_id(payload.get("schedule_id"), "schedule_id")
        interval_hours = max(1, min(24 * 30, int(payload.get("interval_hours") or 24)))

        def callback(value):
            row = {
                "schedule_id": schedule_id,
                "interval_hours": interval_hours,
                "retention_count": max(1, min(30, int(payload.get("retention_count") or 7))),
                "enabled": payload.get("enabled") is True,
                "run_when_app_active": True,
                "background_service_installed": False,
                "last_run_at": "",
                "next_due_at": (datetime.now(UTC) + timedelta(hours=interval_hours)).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "created_at": _now(),
                "review_required": True,
            }
            value["backup_schedules"] = [x for x in value["backup_schedules"] if x["schedule_id"] != schedule_id] + [row]
            return deepcopy(row)

        return self._mutate("backup_schedule_saved", [schedule_id], callback)

    def _backup_root(self) -> Path:
        configured = str(os.environ.get("MFL_BACKUP_ROOT") or "").strip()
        root = Path(configured).expanduser().resolve() if configured else self.case_root.parent / ".mfl_encrypted_backups" / self.scope
        if root.exists() and root.is_symlink():
            raise ProductivitySuiteError("backup_root_symlink_refused", status_code=409)
        root.mkdir(parents=True, exist_ok=True)
        return root

    def run_backup(self, payload: dict[str, Any]) -> dict[str, Any]:
        schedule_id = _safe_id(payload.get("schedule_id"), "schedule_id")
        with exclusive_file_lock(self.lock_path):
            value = self._load()
            schedule = next((x for x in value["backup_schedules"] if x["schedule_id"] == schedule_id), None)
            if schedule is None:
                raise ProductivitySuiteError("backup_schedule_not_found", status_code=404)
            files = []
            total = 0
            for path in sorted(self.case_root.rglob("*")):
                if not path.is_file() or path.is_symlink() or self._backup_root() in path.parents:
                    continue
                try:
                    raw = read_bounded_regular_file(path, max_bytes=_MAX_BACKUP_FILE)
                except Exception:
                    continue
                if total + len(raw) > _MAX_BACKUP_TOTAL:
                    break
                relative = str(path.relative_to(self.case_root)).replace("\\", "/")
                files.append({"path": relative, "sha256": _digest(raw), "size": len(raw), "content": base64.b64encode(raw).decode("ascii")})
                total += len(raw)
            backup_id = f"backup_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
            package = {
                "schema_version": "encrypted_matter_backup_v1",
                "backup_id": backup_id,
                "matter_scope": self.scope,
                "created_at": _now(),
                "files": files,
                "file_count": len(files),
                "total_unencrypted_bytes": total,
            }
            envelope = self.encryptor.encrypt_json(package)
            target = self._backup_root() / f"{backup_id}.json.enc"
            atomic_write_bytes(target, json.dumps(envelope, sort_keys=True).encode("utf-8"), mode=0o600)
            persisted = strict_json_load_path(target, max_bytes=_MAX_BACKUP_TOTAL * 3, require_object=True)
            verified = self.encryptor.decrypt_json(persisted)
            if verified.get("backup_id") != backup_id or verified.get("matter_scope") != self.scope:
                raise ProductivitySuiteError("backup_verification_failed", status_code=409)
            receipt = {
                "backup_id": backup_id,
                "schedule_id": schedule_id,
                "file_count": len(files),
                "total_unencrypted_bytes": total,
                "encrypted_size": target.stat().st_size,
                "encrypted_sha256": _digest(target.read_bytes()),
                "verified": True,
                "created_at": _now(),
                "review_required": True,
            }
            receipt["receipt_hash"] = _digest(receipt)
            value["backups"].append(receipt)
            schedule["last_run_at"] = receipt["created_at"]
            schedule["next_due_at"] = (datetime.now(UTC) + timedelta(hours=schedule["interval_hours"])).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            previous = value["history"][-1]["hash"] if value["history"] else ""
            event = {"event_id": f"productivity_{uuid.uuid4().hex}", "at": _now(), "action": "encrypted_backup_created", "ids": [backup_id, schedule_id], "previous_hash": previous, "review_required": True}
            event["hash"] = _digest(event)
            value["history"].append(event)
            value["revision"] += 1
            self._save(value)
            retention = int(schedule["retention_count"])
            existing = sorted(self._backup_root().glob("backup_*.json.enc"), key=lambda p: p.stat().st_mtime, reverse=True)
            for old in existing[retention:]:
                old.unlink(missing_ok=True)
            return receipt

    def verify_backup(self, backup_id: str) -> dict[str, Any]:
        safe_backup_id = _safe_id(backup_id, "backup_id")
        path = self._backup_root() / f"{safe_backup_id}.json.enc"
        if not path.is_file() or path.is_symlink():
            raise ProductivitySuiteError("backup_not_found", status_code=404)
        try:
            envelope = strict_json_load_path(path, max_bytes=_MAX_BACKUP_TOTAL * 3, require_object=True)
            package = self.encryptor.decrypt_json(envelope)
        except Exception as exc:
            raise ProductivitySuiteError("backup_integrity_failed", status_code=409) from exc
        valid = package.get("matter_scope") == self.scope and all(
            _digest(base64.b64decode(row["content"])) == row["sha256"] for row in package.get("files", [])
        )
        return {
            "backup_id": safe_backup_id,
            "status": "pass" if valid else "blocked",
            "file_count": int(package.get("file_count") or 0),
            "encrypted_sha256": _digest(path.read_bytes()),
            "restore_mode": "separate_recovery_directory_only",
            "review_required": True,
        }

    def restore_backup(self, backup_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Restore into a new recovery directory without touching live matter files."""

        safe_backup_id = _safe_id(backup_id, "backup_id")
        if payload.get("confirmed") is not True:
            raise ProductivitySuiteError("backup_restore_confirmation_required", status_code=409)
        path = self._backup_root() / f"{safe_backup_id}.json.enc"
        if not path.is_file() or path.is_symlink():
            raise ProductivitySuiteError("backup_not_found", status_code=404)
        try:
            envelope = strict_json_load_path(path, max_bytes=_MAX_BACKUP_TOTAL * 3, require_object=True)
            package = self.encryptor.decrypt_json(envelope)
        except Exception as exc:
            raise ProductivitySuiteError("backup_integrity_failed", status_code=409) from exc
        if package.get("matter_scope") != self.scope:
            raise ProductivitySuiteError("cross_matter_access_denied", status_code=404)
        recovery_root = self._backup_root() / "recovery" / safe_backup_id
        if recovery_root.exists():
            raise ProductivitySuiteError("backup_recovery_already_exists", status_code=409)
        recovery_root.mkdir(parents=True, exist_ok=False)
        restored: list[dict[str, Any]] = []
        total = 0
        for row in package.get("files", []):
            relative = Path(str(row.get("path") or ""))
            if relative.is_absolute() or ".." in relative.parts or not relative.parts:
                raise ProductivitySuiteError("backup_path_invalid", status_code=409)
            raw = base64.b64decode(str(row.get("content") or ""), validate=True)
            if _digest(raw) != row.get("sha256"):
                raise ProductivitySuiteError("backup_integrity_failed", status_code=409)
            target = (recovery_root / relative).resolve()
            if recovery_root.resolve() not in target.parents:
                raise ProductivitySuiteError("backup_path_invalid", status_code=409)
            target.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_bytes(target, raw, mode=0o600)
            restored.append({"path": relative.as_posix(), "sha256": _digest(raw), "size": len(raw)})
            total += len(raw)
        receipt = {
            "backup_id": safe_backup_id,
            "status": "restored_to_separate_recovery_directory",
            "file_count": len(restored),
            "total_bytes": total,
            "recovery_token": _digest(str(recovery_root))[:24],
            "live_matter_overwritten": False,
            "review_required": True,
        }
        receipt["receipt_hash"] = _digest(receipt)
        return self._mutate("encrypted_backup_restored", [safe_backup_id], lambda _value: receipt)

    def source_item(self, item_id: str) -> dict[str, Any]:
        safe_item_id = _safe_id(item_id, "item_id")
        value = self._load()
        for collection in ("pinboard_items", "redaction_projects", "courtroom_sessions", "calendar_exports"):
            for row in value[collection]:
                identifiers = {str(row.get(key) or "") for key in ("item_id", "project_id", "session_id", "export_id")}
                if safe_item_id in identifiers:
                    return {"collection": collection, "item": deepcopy(row), "review_required": True}
        raise ProductivitySuiteError("source_item_not_found", status_code=404)
