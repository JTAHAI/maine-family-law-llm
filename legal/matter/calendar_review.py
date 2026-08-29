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
                "calculations": [],
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
        value.setdefault("events", [])
        value.setdefault("rules", [])
        value.setdefault("calculations", [])
        value.setdefault("history", [])
        value.setdefault("revision", 0)
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
        return {key: value[key] for key in ("schema", "events", "rules", "calculations", "history", "revision")} | {
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

    def calculate_dependency(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Record a new candidate without erasing the prior trigger calculation."""
        if payload.get("user_confirmed") is not True:
            raise IntakeWorkbenchError("deadline_dependency_confirmation_required", 409)
        dependency_id = _id(payload.get("dependency_id"), "dependency_id")
        receipt = self.calculate(payload)
        trigger_ref = dict(next(
            (row.get("source_ref") or {} for row in self._load()["events"] if row.get("event_id") == receipt["trigger_event"]),
            {},
        ))
        trigger_hash = str(trigger_ref.get("source_hash") or "").casefold()
        if not re.fullmatch(r"[a-f0-9]{64}", trigger_hash):
            raise IntakeWorkbenchError("deadline_dependency_trigger_hash_required", 409)

        def callback(value):
            prior_rows = [row for row in value["calculations"] if row.get("dependency_id") == dependency_id and row.get("active")]
            prior = prior_rows[-1] if prior_rows else None
            if prior and str(prior.get("trigger_event") or "") == receipt["trigger_event"] and str(prior.get("trigger_source_hash") or "") == trigger_hash:
                raise IntakeWorkbenchError("deadline_dependency_trigger_unchanged", 409)
            candidate_id = f"deadline_{uuid.uuid4().hex}"
            row = {
                **receipt,
                "candidate_id": candidate_id,
                "dependency_id": dependency_id,
                "trigger_source_hash": trigger_hash,
                "source_rule_hash": _hash(next((rule for rule in value["rules"] if rule.get("rule_id") == receipt["rule_id"]), {})),
                "supersedes_candidate_id": str(prior.get("candidate_id") or "") if prior else "",
                "active": True,
                "created_at": _now(),
                "review_required": True,
                "filing_ready": False,
            }
            if prior:
                prior["active"] = False
                prior["superseded_at"] = _now()
                prior["superseded_by_candidate_id"] = candidate_id
            value["calculations"].append(row)
            return row

        result = self._mutate("deadline_dependency_recalculated", [dependency_id, receipt["rule_id"], receipt["trigger_event"]], callback)
        return {**result, "status": "review_required", "notice": "A changed trigger created a new review-required candidate. Prior calculations remain preserved and are not silently replaced."}

    def dependency(self, dependency_id: str) -> dict[str, Any]:
        needle = _id(dependency_id, "dependency_id")
        rows = [dict(row) for row in self._load()["calculations"] if row.get("dependency_id") == needle]
        if not rows:
            raise IntakeWorkbenchError("deadline_dependency_not_found", 404)
        return {"dependency_id": needle, "calculations": rows, "active_candidate": next((row for row in reversed(rows) if row.get("active")), None), "review_required": True, "filing_ready": False, "local_only": True}

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

    def ics_export(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Build an explicit, review-required RFC5545-style local export preview.

        The returned text is never written to a calendar account or downloaded
        automatically. UID, sequence, cancellation, recurrence, alarm, and
        timezone fields are preserved in an encrypted export receipt.
        """
        export_id = _id(payload.get("export_id"), "calendar_export_id")
        timezone = _text(payload.get("time_zone") or "America/New_York", 80)
        if not re.fullmatch(r"[A-Za-z_]+/[A-Za-z_]+", timezone):
            raise IntakeWorkbenchError("calendar_export_timezone_invalid")
        sequence = payload.get("sequence", 0)
        if type(sequence) is not int or sequence < 0 or sequence > 9999:
            raise IntakeWorkbenchError("calendar_export_sequence_invalid")
        alarm_minutes = payload.get("alarm_minutes", 0)
        if type(alarm_minutes) is not int or alarm_minutes < 0 or alarm_minutes > 10080:
            raise IntakeWorkbenchError("calendar_export_alarm_invalid")
        recurrence = _text(payload.get("recurrence_rule"), 400)
        if recurrence and not re.fullmatch(r"(?:FREQ=(?:DAILY|WEEKLY|MONTHLY|YEARLY)(?:;[A-Z]+=[A-Z0-9,+-]+)*)", recurrence):
            raise IntakeWorkbenchError("calendar_export_recurrence_invalid")
        status = str(payload.get("status") or "CONFIRMED").strip().upper()
        if status not in {"CONFIRMED", "CANCELLED"}:
            raise IntakeWorkbenchError("calendar_export_status_invalid")
        requested_ids = payload.get("event_ids")
        if not isinstance(requested_ids, list) or not requested_ids:
            raise IntakeWorkbenchError("calendar_export_event_ids_invalid")
        event_ids = [_id(item, "calendar_export_event_id") for item in requested_ids]
        if len(set(event_ids)) != len(event_ids):
            raise IntakeWorkbenchError("calendar_export_event_ids_duplicate")

        def escape(value: Any) -> str:
            return str(value or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r", "").replace("\n", "\\n")

        def callback(value):
            rows = {row["event_id"]: row for row in value["events"]}
            if any(item not in rows for item in event_ids):
                raise IntakeWorkbenchError("calendar_export_event_not_found", 404)
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Maine Family Law LLM//Local Review//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH", f"X-WR-TIMEZONE:{timezone}"]
            manifest_events = []
            for event_id in event_ids:
                event = rows[event_id]; raw = str(event.get("date_time") or "")
                try: dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                except ValueError: raise IntakeWorkbenchError("calendar_export_event_datetime_invalid") from None
                uid = f"{event_id}@maine-family-law-llm.local"
                local = dt.strftime("%Y%m%dT%H%M%S")
                lines += ["BEGIN:VEVENT", f"UID:{uid}", f"SEQUENCE:{sequence}", f"DTSTAMP:{stamp}", f"DTSTART;TZID={timezone}:{local}", f"SUMMARY:{escape(event.get('document_or_notice') or event_id)}", f"DESCRIPTION:{escape('Review required. Source record: ' + str((event.get('source_ref') or {}).get('record_id') or 'unknown'))}", f"STATUS:{status}"]
                if recurrence: lines.append(f"RRULE:{recurrence}")
                if alarm_minutes and status != "CANCELLED": lines += ["BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:Review-required local calendar reminder", f"TRIGGER:-PT{alarm_minutes}M", "END:VALARM"]
                lines.append("END:VEVENT")
                manifest_events.append({"event_id": event_id, "uid": uid, "source_hash": str((event.get("source_ref") or {}).get("source_hash") or ""), "review_required": True})
            lines.append("END:VCALENDAR")
            content = "\r\n".join(lines) + "\r\n"
            receipt = {"export_id": export_id, "content_hash": hashlib.sha256(content.encode()).hexdigest(), "event_ids": event_ids, "events": manifest_events, "time_zone": timezone, "sequence": sequence, "status": status, "recurrence_rule": recurrence, "alarm_minutes": alarm_minutes, "created_at": _now(), "review_required": True, "calendar_account_write": False, "automatic_download": False}
            receipt["receipt_hash"] = _hash(receipt)
            value.setdefault("exports", []).append(receipt)
            return {"content": content, "receipt": receipt, "status": "review_required", "local_only": True, "calendar_account_write": False, "automatic_download": False}
        return self._mutate("calendar_ics_v2_export_created", [export_id, *event_ids], callback)
