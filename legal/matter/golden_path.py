"""Evidence-driven golden-path journey for a local family-law matter."""

from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor

from .intake_workbench import IntakeWorkbenchError, MatterIntakeStore

STAGES = (
    "matter_intake",
    "procedural_posture",
    "record_inventory",
    "issue_tree",
    "grounded_research",
    "human_review",
)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class MatterJourneyStore:
    """Persist human checkpoints while deriving all machine stages from evidence."""

    schema = "maine_family_law_llm.matter_journey.v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).expanduser().resolve()
        self.root = self.case_root / "21_MATTER_JOURNEY"
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "journeys.json.enc"
        self.lock = self.root / ".journeys.lock"
        self.encryptor = LocalEnvelopeEncryptor(
            encryption_key
            or os.environ.get("MAINE_MATTER_STORE_KEY")
            or "local-development-key-change-me"
        )
        self.intake = MatterIntakeStore(self.case_root, encryption_key=encryption_key)

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema": self.schema, "journeys": {}}
        envelope = json.loads(self.path.read_text(encoding="utf-8"))
        state = self.encryptor.decrypt_json(envelope)
        if state.get("schema") != self.schema or not isinstance(state.get("journeys"), dict):
            raise IntakeWorkbenchError("matter_journey_state_invalid", 409)
        return state

    def _write(self, state: dict[str, Any]) -> None:
        envelope = self.encryptor.encrypt_json(state)
        atomic_write_bytes(
            self.path,
            json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8"),
            mode=0o600,
        )

    def record_checkpoint(self, matter_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        stage = str(payload.get("stage") or "").strip().casefold()
        if stage not in {"grounded_research", "human_review"}:
            raise IntakeWorkbenchError("matter_journey_checkpoint_stage_invalid")
        if not bool(payload.get("approved")):
            raise IntakeWorkbenchError("matter_journey_explicit_approval_required")
        source_receipt_sha256 = str(payload.get("source_receipt_sha256") or "").strip().casefold()
        if stage == "grounded_research" and not _valid_hash(source_receipt_sha256):
            raise IntakeWorkbenchError("grounded_research_source_receipt_required")
        review_receipt_sha256 = str(payload.get("review_receipt_sha256") or "").strip().casefold()
        if stage == "human_review" and not _valid_hash(review_receipt_sha256):
            raise IntakeWorkbenchError("human_review_receipt_required")
        self.intake.get(matter_id)
        with exclusive_file_lock(self.lock):
            state = self._read()
            journey = state["journeys"].setdefault(matter_id, {"events": []})
            previous = str(journey["events"][-1]["event_hash"]) if journey["events"] else ""
            event = {
                "event_id": f"journey-{len(journey['events']) + 1:04d}",
                "stage": stage,
                "at": _now(),
                "source_receipt_sha256": source_receipt_sha256,
                "review_receipt_sha256": review_receipt_sha256,
                "reviewer_role": str(payload.get("reviewer_role") or "reviewer")[:80],
                "previous_event_hash": previous,
            }
            event["event_hash"] = _hash(event)
            journey["events"].append(event)
            self._write(state)
        return deepcopy(event)

    def status(
        self,
        matter_id: str,
        *,
        corpus_metrics: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        intake = self.intake.get(matter_id)
        state = self._read()
        events = list((state.get("journeys", {}).get(matter_id) or {}).get("events") or [])
        _verify_events(events)
        completed_checkpoints = {str(event.get("stage")) for event in events}
        metrics = dict(corpus_metrics or {})
        document_count = int(
            metrics.get("document_count")
            or metrics.get("indexed_documents")
            or metrics.get("record_count")
            or 0
        )
        posture = dict(intake.get("procedural_posture") or {})
        issue_tree = list(intake.get("issue_tree") or [])
        intake_actions = {
            str(event.get("action") or "") for event in list(intake.get("history") or [])
        }
        stage_rows = [
            _stage("matter_intake", True, "Matter intake is saved."),
            _stage(
                "procedural_posture",
                bool(posture.get("state")) and "posture_updated" in intake_actions,
                "Record the current posture and its source status.",
            ),
            _stage(
                "record_inventory",
                document_count > 0,
                "Import or index at least one matter record.",
            ),
            _stage("issue_tree", bool(issue_tree), "Build at least one review-required issue."),
            _stage(
                "grounded_research",
                "grounded_research" in completed_checkpoints,
                "Complete source-backed research and retain its receipt.",
            ),
            _stage(
                "human_review",
                "human_review" in completed_checkpoints,
                "Complete human review and retain its receipt.",
            ),
        ]
        completed = sum(1 for row in stage_rows if row["complete"])
        next_stage = next((row for row in stage_rows if not row["complete"]), None)
        if next_stage is not None:
            next_stage["status"] = "next"
        return {
            "schema_version": "matter_golden_path_status_v1",
            "matter_id": matter_id,
            "status": "review_complete" if completed == len(stage_rows) else "in_progress",
            "completed_stage_count": completed,
            "total_stage_count": len(stage_rows),
            "progress": round(completed / len(stage_rows), 4),
            "stages": stage_rows,
            "next_action": deepcopy(next_stage),
            "corpus_document_count": document_count,
            "checkpoint_receipt_count": len(events),
            "journey_receipt_sha256": _hash(events),
            "review_required": completed != len(stage_rows),
            "local_only": True,
        }


def _stage(stage: str, complete: bool, guidance: str) -> dict[str, Any]:
    return {
        "stage": stage,
        "complete": complete,
        "status": "complete" if complete else "next" if stage == "matter_intake" else "pending",
        "guidance": guidance,
    }


def _valid_hash(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _verify_events(events: list[dict[str, Any]]) -> None:
    previous = ""
    for event in events:
        copy = dict(event)
        digest = str(copy.pop("event_hash", ""))
        if copy.get("previous_event_hash") != previous or _hash(copy) != digest:
            raise IntakeWorkbenchError("matter_journey_history_invalid", 409)
        previous = digest


__all__ = ["MatterJourneyStore", "STAGES"]
