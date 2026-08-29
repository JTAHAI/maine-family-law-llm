"""Matter-scoped scheduler for compatible local background inference work.

The scheduler plans batches and durable kernel jobs; it deliberately does not
execute a model itself.  Each source-bound child remains independently
cancellable even when compatible children share one kernel job.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path

_ID = re.compile(r"[a-z][a-z0-9_-]{2,79}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_KINDS = frozenset({"extract", "classify", "embed"})


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _id(value: Any, label: str) -> str:
    candidate = str(value or "").strip().casefold()
    if not _ID.fullmatch(candidate):
        raise IntakeWorkbenchError(f"batch_scheduler_{label}_invalid")
    return candidate


class BatchInferenceScheduler:
    schema = "maine_family_law_llm.batch_inference_scheduler.v1"

    def __init__(self, root: str | Path, *, kernel: Any, matter_id: str, encryption_key: str | None = None):
        self.root = Path(root).resolve() / "40_RUNTIME" / "batch-scheduler"
        self.kernel = kernel
        self.matter_id = str(matter_id or "").strip()
        if not self.matter_id or len(self.matter_id) > 200:
            raise IntakeWorkbenchError("batch_scheduler_matter_id_invalid")
        self.encryptor = LocalEnvelopeEncryptor(
            encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me"
        )

    @property
    def path(self) -> Path:
        return self.root / "batches.json.enc"

    @property
    def lock(self) -> Path:
        return self.root / ".batches.lock"

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema": self.schema, "batches": {}, "events": [], "revision": 0}
        try:
            state = self.encryptor.decrypt_json(strict_json_load_path(self.path, max_bytes=4 * 1024 * 1024, require_object=True))
        except Exception as exc:
            raise IntakeWorkbenchError("batch_scheduler_unavailable", 409) from exc
        if state.get("schema") != self.schema:
            raise IntakeWorkbenchError("batch_scheduler_unavailable", 409)
        previous = ""
        for event in state.get("events", []):
            copy = dict(event)
            actual = str(copy.pop("event_hash", ""))
            if copy.get("previous_event_hash") != previous or actual != _digest(copy):
                raise IntakeWorkbenchError("batch_scheduler_history_invalid", 409)
            previous = actual
        return state

    def _write(self, state: dict[str, Any]) -> None:
        atomic_write_bytes(self.path, _canonical(self.encryptor.encrypt_json(state)), mode=0o600)

    @staticmethod
    def _event(state: dict[str, Any], action: str, batch_id: str, detail: dict[str, Any]) -> dict[str, Any]:
        events = state.setdefault("events", [])
        event = {"event_id": f"batch_evt_{hashlib.sha256((action + batch_id + _now()).encode()).hexdigest()[:24]}", "at": _now(), "action": action, "batch_id": batch_id, "detail": deepcopy(detail), "previous_event_hash": str(events[-1].get("event_hash") or "") if events else "", "review_required": True}
        event["event_hash"] = _digest(event)
        events.append(event)
        state["revision"] = int(state.get("revision") or 0) + 1
        return event

    @staticmethod
    def _public(batch: dict[str, Any]) -> dict[str, Any]:
        return deepcopy(batch)

    @staticmethod
    def _items(value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list) or not value or len(value) > 64:
            raise IntakeWorkbenchError("batch_scheduler_items_invalid")
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw in value:
            if not isinstance(raw, dict):
                raise IntakeWorkbenchError("batch_scheduler_item_invalid")
            item_id = _id(raw.get("item_id"), "item_id")
            if item_id in seen:
                raise IntakeWorkbenchError("batch_scheduler_item_duplicate")
            seen.add(item_id)
            kind = str(raw.get("job_kind") or "").strip().casefold()
            if kind not in _KINDS:
                raise IntakeWorkbenchError("batch_scheduler_job_kind_invalid")
            source = dict(raw.get("source_ref") or {})
            source_id = _id(source.get("source_id"), "source_id")
            source_hash = str(source.get("content_sha256") or "").strip().casefold()
            if not _HASH.fullmatch(source_hash):
                raise IntakeWorkbenchError("batch_scheduler_source_hash_invalid")
            profile = dict(raw.get("execution_profile") or {})
            # Profiles are identifiers/config flags only; text or provider URLs do not belong in the scheduler.
            clean_profile = {
                str(key)[:64]: str(value)[:160]
                for key, value in profile.items()
                if re.fullmatch(r"[a-z][a-z0-9_]{0,63}", str(key))
            }
            results.append({"item_id": item_id, "job_kind": kind, "source_ref": {"source_id": source_id, "content_sha256": source_hash}, "execution_profile": clean_profile, "status": "queued_review_required", "cancelled_at": "", "review_required": True})
        return results

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("user_confirmed") is not True:
            raise IntakeWorkbenchError("batch_scheduler_confirmation_required", 409)
        batch_id = _id(payload.get("batch_id"), "batch_id")
        items = self._items(payload.get("items"))
        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            signature = _digest({"job_kind": item["job_kind"], "execution_profile": item["execution_profile"]})[:16]
            grouped.setdefault(signature, []).append(item)
        with exclusive_file_lock(self.lock):
            state = self._load()
            if batch_id in state["batches"]:
                raise IntakeWorkbenchError("batch_scheduler_id_exists", 409)
            groups = []
            for signature, members in sorted(grouped.items()):
                group_id = f"grp_{signature}"
                durable = self.kernel.create_job(
                    "batch_inference",
                    {"batch_id": batch_id, "group_id": group_id, "job_kind": members[0]["job_kind"], "execution_profile": members[0]["execution_profile"], "items": [{"item_id": row["item_id"], "source_ref": row["source_ref"]} for row in members], "review_required": True, "execution_not_automatic": True},
                    matter_id=self.matter_id,
                    idempotency_key=f"{batch_id}:{group_id}",
                )
                groups.append({"group_id": group_id, "job_kind": members[0]["job_kind"], "execution_profile": members[0]["execution_profile"], "item_ids": [row["item_id"] for row in members], "runtime_job_id": durable["job_id"], "status": durable["status"], "review_required": True})
            batch = {"batch_id": batch_id, "matter_scope": "active_matter_only", "status": "queued_review_required", "created_at": _now(), "items": items, "groups": groups, "coalesced_group_count": len(groups), "execution_not_automatic": True, "review_required": True, "local_only": True, "network_used": False}
            state["batches"][batch_id] = batch
            event = self._event(state, "batch_scheduled", batch_id, {"item_count": len(items), "group_count": len(groups)})
            self._write(state)
        return {"batch": self._public(batch), "receipt": deepcopy(event)}

    def get(self, batch_id: str) -> dict[str, Any]:
        batch = self._load()["batches"].get(_id(batch_id, "batch_id"))
        if not batch:
            raise IntakeWorkbenchError("batch_scheduler_not_found", 404)
        return {"batch": self._public(batch)}

    def source(self, batch_id: str, item_id: str) -> dict[str, Any]:
        batch = self.get(batch_id)["batch"]
        item = next((row for row in batch["items"] if row["item_id"] == _id(item_id, "item_id")), None)
        if not item:
            raise IntakeWorkbenchError("batch_scheduler_item_not_found", 404)
        return {"source_ref": deepcopy(item["source_ref"]), "review_required": True}

    def cancel_item(self, batch_id: str, item_id: str) -> dict[str, Any]:
        safe_batch, safe_item = _id(batch_id, "batch_id"), _id(item_id, "item_id")
        with exclusive_file_lock(self.lock):
            state = self._load()
            batch = state["batches"].get(safe_batch)
            if not batch:
                raise IntakeWorkbenchError("batch_scheduler_not_found", 404)
            item = next((row for row in batch["items"] if row["item_id"] == safe_item), None)
            if not item:
                raise IntakeWorkbenchError("batch_scheduler_item_not_found", 404)
            if item["status"] != "cancelled_review_required":
                item.update({"status": "cancelled_review_required", "cancelled_at": _now()})
                for group in batch["groups"]:
                    if safe_item not in group["item_ids"]:
                        continue
                    live = [row for row in batch["items"] if row["item_id"] in group["item_ids"] and row["status"] != "cancelled_review_required"]
                    if not live:
                        try:
                            durable = self.kernel.request_cancel(group["runtime_job_id"])
                            group["status"] = durable["status"]
                        except KeyError:
                            group["status"] = "missing_review_required"
                if all(row["status"] == "cancelled_review_required" for row in batch["items"]):
                    batch["status"] = "cancelled_review_required"
                event = self._event(state, "batch_item_cancelled", safe_batch, {"item_id": safe_item})
                self._write(state)
            else:
                event = None
        return {"batch": self._public(batch), "receipt": deepcopy(event) if event else None, "review_required": True}
