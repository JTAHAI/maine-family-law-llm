"""Local, review-required service, notice, deadline, and hearing calendar data."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path

_ID = re.compile(r"[a-z][a-z0-9_-]{2,79}\Z")
_EVENTS = frozenset(
    {
        "filing",
        "service_attempt",
        "completed_service_candidate",
        "waiver_acceptance",
        "mail_service",
        "electronic_service",
        "personal_service",
        "publication",
        "notice",
        "hearing",
        "mediation",
        "response_due",
        "objection_due",
        "appeal_related_date",
        "document_due",
        "court_ordered_date",
        "user_reminder",
        "unknown",
    }
)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _id(value: Any, name: str) -> str:
    result = str(value or "").strip().casefold()
    if not _ID.fullmatch(result):
        raise IntakeWorkbenchError(f"{name}_invalid")
    return result


def _text(value: Any, limit: int = 4_000) -> str:
    result = str(value or "").strip()
    if len(result) > limit:
        raise IntakeWorkbenchError("text_limit_exceeded")
    return result


class CalendarReviewStore:
    schema = "maine_family_law_llm.calendar_review.v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).resolve()
        self.root = self.case_root / "22_CALENDAR_REVIEW"
        if (
            not self.case_root.is_dir()
            or self.case_root.is_symlink()
            or (self.root.exists() and self.root.is_symlink())
        ):
            raise IntakeWorkbenchError("calendar_store_unavailable", 409)
        self.encryptor = LocalEnvelopeEncryptor(
            encryption_key
            or os.environ.get("MAINE_MATTER_STORE_KEY")
            or "local-development-key-change-me"
        )
        self.scope = hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24]

    @property
    def path(self) -> Path:
        return self.root / "calendar.json.enc"

    @property
    def lock(self) -> Path:
        return self.root / ".calendar.lock"

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "schema": self.schema,
                "scope": self.scope,
                "events": [],
                "rules": [],
                "history": [],
                "revision": 0,
            }
        try:
            value = self.encryptor.decrypt_json(
                strict_json_load_path(self.path, max_bytes=4 * 1024 * 1024, require_object=True)
            )
        except Exception as exc:
            raise IntakeWorkbenchError("calendar_store_unavailable", 409) from exc
        if value.get("schema") != self.schema or value.get("scope") != self.scope:
            raise IntakeWorkbenchError("cross_matter_access_denied", 404)
        return value

    def _save(self, value: dict[str, Any]) -> None:
        atomic_write_bytes(
            self.path,
            json.dumps(self.encryptor.encrypt_json(value), sort_keys=True).encode(),
            mode=0o600,
        )

    def _mutate(self, action, ids, callback):  # type: ignore[no-untyped-def]
        with exclusive_file_lock(self.lock):
            value = self._load()
            result = callback(value)
            prior = value["history"][-1]["hash"] if value["history"] else ""
            event = {
                "event_id": f"calendar_event_{uuid.uuid4().hex}",
                "at": _now(),
                "action": action,
                "ids": ids,
                "previous_hash": prior,
                "review_required": True,
            }
            event["hash"] = _hash(event)
            value["history"].append(event)
            value["revision"] += 1
            self._save(value)
            return result

    def public(self, value: dict[str, Any]) -> dict[str, Any]:
        return {key: value[key] for key in ("schema", "events", "rules", "history", "revision")} | {
            "status": "review_required",
            "review_required": True,
            "local_only": True,
            "calendar_account_write": False,
        }

    def inventory(self) -> dict[str, Any]:
        return self.public(self._load())

    def add_events(self, payload: dict[str, Any]) -> dict[str, Any]:
        entries = payload.get("events")
        if not isinstance(entries, list) or not entries or len(entries) > 300:
            raise IntakeWorkbenchError("events_invalid")

        def callback(value):
            seen = {row["event_id"] for row in value["events"]}
            added = []
            for item in entries:
                if not isinstance(item, dict):
                    raise IntakeWorkbenchError("event_invalid")
                event_id = _id(item.get("event_id"), "event_id")
                kind = str(item.get("kind") or "unknown")
                if event_id in seen or kind not in _EVENTS:
                    raise IntakeWorkbenchError("event_id_or_kind_invalid")
                source = item.get("source_ref") or {}
                record_id = _id(source.get("record_id"), "record_id") if source else ""
                added.append(
                    {
                        "event_id": event_id,
                        "kind": kind,
                        "date_time": _text(item.get("date_time"), 64),
                        "time_zone": _text(item.get("time_zone") or "unknown", 64),
                        "document_or_notice": _text(item.get("document_or_notice"), 512),
                        "person_or_role": _text(item.get("person_or_role"), 256),
                        "method": _text(item.get("method"), 128),
                        "proof_status": str(item.get("proof_status") or "unknown"),
                        "disputed": bool(item.get("disputed")),
                        "source_ref": {
                            "record_id": record_id,
                            "source_hash": _text(source.get("source_hash"), 128),
                            "page": source.get("page"),
                        },
                        "reviewer_status": "review_required",
                    }
                )
                seen.add(event_id)
            value["events"].extend(added)
            return self.public(value)

        return self._mutate(
            "events_added",
            [_id(x.get("event_id"), "event_id") for x in entries if isinstance(x, dict)],
            callback,
        )

    def add_rules(self, payload: dict[str, Any]) -> dict[str, Any]:
        rules = payload.get("rules")
        if not isinstance(rules, list) or not rules:
            raise IntakeWorkbenchError("rules_invalid")

        def callback(value):
            for item in rules:
                if not isinstance(item, dict):
                    raise IntakeWorkbenchError("rule_invalid")
                source = item.get("source_ref") or {}
                authority = str(item.get("freshness") or "unknown")
                value["rules"].append(
                    {
                        "rule_id": _id(item.get("rule_id"), "rule_id"),
                        "citation": _text(item.get("citation"), 256),
                        "source_ref": {
                            "record_id": _id(source.get("record_id"), "record_id"),
                            "source_hash": _text(source.get("source_hash"), 128),
                            "page": source.get("page"),
                        },
                        "freshness": authority,
                        "triggering_event": _text(item.get("triggering_event"), 128),
                        "unit": str(item.get("unit") or "days"),
                        "count": int(item.get("count") or 0),
                        "inclusion_rule": str(item.get("inclusion_rule") or "unknown"),
                        "weekend_holiday_handling": str(
                            item.get("weekend_holiday_handling") or "unknown"
                        ),
                        "exceptions": _text(item.get("exceptions"), 2_000),
                        "jurisdiction": _text(item.get("jurisdiction"), 128),
                        "effective_date": _text(item.get("effective_date"), 64),
                        "review_required": True,
                    }
                )
            return self.public(value)

        return self._mutate(
            "rules_added",
            [_id(x.get("rule_id"), "rule_id") for x in rules if isinstance(x, dict)],
            callback,
        )

    def calculate(self, payload: dict[str, Any]) -> dict[str, Any]:
        value = self._load()
        rule = next(
            (x for x in value["rules"] if x["rule_id"] == _id(payload.get("rule_id"), "rule_id")),
            None,
        )
        trigger = next(
            (
                x
                for x in value["events"]
                if x["event_id"] == _id(payload.get("trigger_event_id"), "trigger_event_id")
            ),
            None,
        )
        if not rule or not trigger:
            raise IntakeWorkbenchError("rule_or_trigger_not_found", 404)
        try:
            start = date.fromisoformat(trigger["date_time"][:10])
            candidate = start + timedelta(days=int(rule["count"]))
        except ValueError:
            candidate = None
        stale = rule["freshness"] not in {"fresh", "current"}
        holidays = payload.get("holidays") if isinstance(payload.get("holidays"), list) else []
        receipt = {
            "trigger_event": trigger["event_id"],
            "rule_id": rule["rule_id"],
            "formula": f"{trigger['date_time'][:10]} + {rule['count']} {rule['unit']}",
            "holidays_used": holidays,
            "time_zone": trigger["time_zone"],
            "assumptions": ["Calendar data is user-supplied or requires official review."],
            "candidate_result": candidate.isoformat() if candidate else "unknown",
            "uncertainty": "stale_or_unknown_authority" if stale else "review_required",
            "reviewer_confirmed": False,
            "review_required": True,
        }
        receipt["hash"] = _hash(receipt)
        return receipt

    def receipt(self) -> dict[str, Any]:
        value = self._load()
        result = {
            "revision": value["revision"],
            "events_hash": _hash(value["events"]),
            "rules_hash": _hash(value["rules"]),
            "review_required": True,
            "local_only": True,
            "issued_at": _now(),
        }
        result["receipt_hash"] = _hash(result)
        return result
