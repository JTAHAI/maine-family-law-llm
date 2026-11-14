"""Human-grounded evaluation ledger and release-readiness gates."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock, read_bounded_regular_file
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_loads

_HASH = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._-]{2,99}\Z")
APPROVALS = {"approved", "approved_with_notes"}
_MAX_LEDGER_BYTES = 16 * 1024 * 1024
_ENVELOPE_SCHEMA = "maine_family_law_llm.human_eval_encrypted.v1"


class HumanEvalError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


class HumanEvalLedger:
    """Store hashes and reviewer decisions, never private prompts or answers."""

    schema = "maine_family_law_llm.human_eval_ledger.v1"

    def __init__(self, root: str | Path, *, tenant: str = ""):
        self.root = Path(root).expanduser().resolve()
        self.tenant = tenant
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "human-eval-ledger.json"
        self.lock = self.root / ".human-eval-ledger.lock"

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema": self.schema, "cases": {}, "events": []}
        try:
            raw = read_bounded_regular_file(self.path, max_bytes=_MAX_LEDGER_BYTES)
            value = strict_json_loads(raw, max_bytes=_MAX_LEDGER_BYTES, require_object=True)
            authenticated_state = value.get("schema") == _ENVELOPE_SCHEMA
            if authenticated_state:
                bound = self._encryptor().decrypt_json(value["envelope"])
                if bound["tenant"] != self.tenant or bound["root"] != str(self.root):
                    raise ValueError
                value = bound["payload"]
            if not isinstance(value.get("cases"), dict) or not isinstance(value.get("events"), list):
                raise ValueError
            # Verify the original event chain before treating historic rows as
            # practice. The flag below only changes case views, not events.
            self._verify_events(value["events"])
            for case in value["cases"].values():
                if not isinstance(case.get("reviews"), list) or not isinstance(case.get("data_class"), str):
                    raise ValueError
                if not authenticated_state:
                    for review in case["reviews"]:
                        review["reviewer_authenticated"] = False
                    if case.get("adjudication"):
                        case["adjudication"]["reviewer_authenticated"] = False
        except (OSError, KeyError, ValueError, AttributeError, TypeError) as exc:
            raise HumanEvalError("human_eval_storage_unverified") from exc
        if value.get("schema") != self.schema:
            raise HumanEvalError("human_eval_schema_invalid")
        return value

    def _write(self, state: dict[str, Any]) -> None:
        envelope = _canonical({
            "schema": _ENVELOPE_SCHEMA,
            "envelope": self._encryptor().encrypt_json({
                "tenant": self.tenant, "root": str(self.root), "payload": state,
            }),
        })
        if len(envelope) > _MAX_LEDGER_BYTES:
            raise HumanEvalError("human_eval_storage_limit")
        atomic_write_bytes(self.path, envelope, mode=0o600)

    @staticmethod
    def _encryptor() -> LocalEnvelopeEncryptor:
        return LocalEnvelopeEncryptor(
            os.environ.get("MAINE_MATTER_STORE_KEY") or LocalEnvelopeEncryptor.development_default
        )

    def add_case(self, payload: dict[str, Any]) -> dict[str, Any]:
        case_id = _identifier(payload.get("case_id"), "case_id")
        task = _identifier(payload.get("task"), "task")
        artifact_sha256 = _hash_value(payload.get("artifact_sha256"), "artifact_sha256")
        data_class = str(payload.get("data_class") or "synthetic").strip().casefold()
        if data_class not in {"synthetic", "public_authority", "consented_real_matter"}:
            raise HumanEvalError("human_eval_data_class_invalid")
        with exclusive_file_lock(self.lock):
            state = self._read()
            if case_id in state["cases"]:
                raise HumanEvalError("human_eval_case_exists")
            record = {
                "case_id": case_id,
                "task": task,
                "artifact_sha256": artifact_sha256,
                "data_class": data_class,
                "consent_receipt_sha256": "",
                "created_at": _now(),
                "reviews": [],
                "adjudication": None,
                "promotion_status": "awaiting_independent_reviews",
            }
            if data_class == "consented_real_matter":
                record["consent_receipt_sha256"] = _hash_value(
                    payload.get("consent_receipt_sha256"),
                    "consent_receipt_sha256",
                )
            state["cases"][case_id] = record
            self._event(state, "case_added", case_id, {"task": task, "data_class": data_class})
            self._write(state)
        return self.public_case(record)

    def review(self, case_id: str, payload: dict[str, Any], *, authenticated: bool = False) -> dict[str, Any]:
        reviewer_id = _identifier(payload.get("reviewer_id"), "reviewer_id")
        role = str(payload.get("reviewer_role") or "").strip().casefold()
        if role not in {"attorney", "legal_aid_reviewer", "subject_matter_reviewer"}:
            raise HumanEvalError("human_eval_reviewer_role_invalid")
        disposition = str(payload.get("disposition") or "").strip().casefold()
        if disposition not in APPROVALS | {"rejected", "needs_correction"}:
            raise HumanEvalError("human_eval_disposition_invalid")
        ratings = dict(payload.get("ratings") or {})
        required = {"legal_accuracy", "grounding", "usefulness", "boundary_safety"}
        if set(ratings) != required or any(
            not isinstance(value, int) or isinstance(value, bool) or value < 1 or value > 5
            for value in ratings.values()
        ):
            raise HumanEvalError("human_eval_ratings_invalid")
        with exclusive_file_lock(self.lock):
            state = self._read()
            record = state["cases"].get(case_id)
            if record is None:
                raise HumanEvalError("human_eval_case_not_found")
            if any(review["reviewer_id"] == reviewer_id for review in record["reviews"]):
                raise HumanEvalError("human_eval_duplicate_reviewer")
            review = {
                "reviewer_id": reviewer_id,
                "reviewer_role": role,
                "reviewer_authenticated": authenticated is True,
                "disposition": disposition,
                "ratings": ratings,
                "finding_codes": sorted(
                    {_identifier(code, "finding_code") for code in payload.get("finding_codes", [])}
                ),
                "review_artifact_sha256": _hash_value(
                    payload.get("review_artifact_sha256"), "review_artifact_sha256"
                ),
                "reviewed_at": _now(),
            }
            record["reviews"].append(review)
            self._set_promotion_status(record)
            self._event(
                state,
                "case_reviewed",
                case_id,
                {"reviewer_id": reviewer_id, "disposition": disposition},
            )
            self._write(state)
        return self.public_case(record)

    def adjudicate(self, case_id: str, payload: dict[str, Any], *, authenticated: bool = False) -> dict[str, Any]:
        if payload.get("approved") is not True:
            raise HumanEvalError("human_eval_adjudication_approval_required")
        with exclusive_file_lock(self.lock):
            state = self._read()
            record = state["cases"].get(case_id)
            if record is None:
                raise HumanEvalError("human_eval_case_not_found")
            if record["promotion_status"] != "adjudication_required":
                raise HumanEvalError("human_eval_adjudication_not_required")
            reviewer_id = _identifier(payload.get("reviewer_id"), "reviewer_id")
            if any(review["reviewer_id"] == reviewer_id for review in record["reviews"]):
                raise HumanEvalError("human_eval_adjudicator_not_independent")
            record["adjudication"] = {
                "reviewer_id": reviewer_id,
                "reviewer_authenticated": authenticated is True,
                "disposition": str(payload.get("disposition") or "rejected").strip().casefold(),
                "receipt_sha256": _hash_value(payload.get("receipt_sha256"), "receipt_sha256"),
                "at": _now(),
            }
            record["promotion_status"] = (
                "promotion_eligible"
                if record["adjudication"]["disposition"] in APPROVALS
                else "rejected"
            )
            self._event(state, "case_adjudicated", case_id, record["adjudication"])
            self._write(state)
        return self.public_case(record)

    def readiness(
        self,
        *,
        minimum_total: int = 250,
        minimum_per_task: int = 25,
        required_tasks: list[str] | None = None,
    ) -> dict[str, Any]:
        state = self._read()
        cases = list(state["cases"].values())
        candidates = [case for case in cases if case["promotion_status"] == "promotion_eligible"]
        eligible = [
            case for case in candidates
            if case["data_class"] != "synthetic"
            and len(case.get("reviews", [])) >= 2
            and all(row.get("reviewer_authenticated") is True for row in case["reviews"])
            and (case["adjudication"] is None or case["adjudication"].get("reviewer_authenticated") is True)
        ]
        tasks = required_tasks or sorted({str(case["task"]) for case in cases})
        task_counts = {task: sum(1 for case in eligible if case["task"] == task) for task in tasks}
        blockers: list[str] = []
        if len(eligible) < minimum_total:
            blockers.append("human_eval_minimum_total_not_met")
        blockers.extend(
            f"human_eval_task_minimum_not_met:{task}"
            for task, count in task_counts.items()
            if count < minimum_per_task
        )
        if any(case["promotion_status"] == "adjudication_required" for case in cases):
            blockers.append("human_eval_conflicts_unadjudicated")
        consented = sum(1 for case in eligible if case["data_class"] == "consented_real_matter")
        return {
            "schema_version": "human_grounded_eval_readiness_v1",
            "status": "pass" if not blockers else "blocked",
            "case_count": len(cases),
            "promotion_eligible_count": len(eligible),
            "practice_or_unauthenticated_candidate_count": len(candidates) - len(eligible),
            "independent_release_approval_required": True,
            "consented_real_matter_count": consented,
            "task_counts": task_counts,
            "minimum_total": minimum_total,
            "minimum_per_task": minimum_per_task,
            "blockers": blockers,
            "private_content_stored": False,
            "human_review_required": True,
        }

    @staticmethod
    def _set_promotion_status(record: dict[str, Any]) -> None:
        reviews = list(record["reviews"])
        if len(reviews) < 2:
            record["promotion_status"] = "awaiting_independent_reviews"
            return
        approved = [review["disposition"] in APPROVALS for review in reviews]
        if any(approved) and not all(approved):
            record["promotion_status"] = "adjudication_required"
        elif all(approved):
            record["promotion_status"] = "promotion_eligible"
        else:
            record["promotion_status"] = "rejected"

    @staticmethod
    def public_case(record: dict[str, Any]) -> dict[str, Any]:
        return json.loads(json.dumps(record))

    def _event(
        self,
        state: dict[str, Any],
        action: str,
        case_id: str,
        detail: dict[str, Any],
    ) -> None:
        events = state["events"]
        event = {
            "event_id": f"eval-event-{len(events) + 1:06d}",
            "action": action,
            "case_id": case_id,
            "detail": detail,
            "at": _now(),
            "previous_event_hash": events[-1]["event_hash"] if events else "",
        }
        event["event_hash"] = _digest(event)
        events.append(event)

    @staticmethod
    def _verify_events(events: list[dict[str, Any]]) -> None:
        previous = ""
        for event in events:
            copy = dict(event)
            digest = str(copy.pop("event_hash", ""))
            if copy.get("previous_event_hash") != previous or _digest(copy) != digest:
                raise HumanEvalError("human_eval_history_invalid")
            previous = digest


def _identifier(value: Any, label: str) -> str:
    candidate = str(value or "").strip()
    if not _ID.fullmatch(candidate):
        raise HumanEvalError(f"human_eval_{label}_invalid")
    return candidate


def _hash_value(value: Any, label: str) -> str:
    candidate = str(value or "").strip().casefold()
    if not _HASH.fullmatch(candidate):
        raise HumanEvalError(f"human_eval_{label}_invalid")
    return candidate


__all__ = ["HumanEvalError", "HumanEvalLedger"]
