"""Encrypted, source-bound statement comparison without credibility judgments."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from copy import deepcopy
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path

_ID = re.compile(r"[a-z][a-z0-9_-]{2,79}\Z")
_KINDS = frozenset(
    {
        "affidavit",
        "pleading",
        "interview",
        "testimony",
        "message",
        "report",
        "prior_statement",
        "unknown",
    }
)


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _id(value: Any, name: str) -> str:
    result = str(value or "").strip().casefold()
    if not _ID.fullmatch(result):
        raise IntakeWorkbenchError(f"{name}_invalid")
    return result


def _text(value: Any, limit: int = 20_000) -> str:
    result = str(value or "").strip()
    if len(result) > limit:
        raise IntakeWorkbenchError("text_limit_exceeded")
    return result


class WitnessStatementStore:
    schema = "maine_family_law_llm.witness_statements.v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root, self.root = (
            Path(case_root).resolve(),
            Path(case_root).resolve() / "26_WITNESS_STATEMENTS",
        )
        if (
            not self.case_root.is_dir()
            or self.case_root.is_symlink()
            or (self.root.exists() and self.root.is_symlink())
        ):
            raise IntakeWorkbenchError("statement_store_unavailable", 409)
        self.encryptor = LocalEnvelopeEncryptor(
            encryption_key
            or os.environ.get("MAINE_MATTER_STORE_KEY")
            or "local-development-key-change-me"
        )
        self.scope = hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24]

    @property
    def path(self) -> Path:
        return self.root / "statements.json.enc"

    @property
    def lock(self) -> Path:
        return self.root / ".statements.lock"

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "schema": self.schema,
                "scope": self.scope,
                "people": [],
                "statements": [],
                "history": [],
                "revision": 0,
            }
        try:
            value = self.encryptor.decrypt_json(
                strict_json_load_path(self.path, max_bytes=8 * 1024 * 1024, require_object=True)
            )
        except Exception as exc:
            raise IntakeWorkbenchError("statement_store_unavailable", 409) from exc
        if value.get("schema") != self.schema or value.get("scope") != self.scope:
            raise IntakeWorkbenchError("cross_matter_access_denied", 404)
        return value

    def _save(self, value: dict[str, Any]) -> None:
        atomic_write_bytes(
            self.path,
            json.dumps(self.encryptor.encrypt_json(value), sort_keys=True).encode(),
            mode=0o600,
        )

    def _mutate(self, action: str, ids: list[str], fn):  # type: ignore[no-untyped-def]
        with exclusive_file_lock(self.lock):
            value, result = self._load(), None
            result = fn(value)
            prior = value["history"][-1]["event_hash"] if value["history"] else ""
            event = {
                "event_id": f"statement_event_{uuid.uuid4().hex}",
                "at": _now(),
                "action": action,
                "ids": ids,
                "previous_event_hash": prior,
                "review_required": True,
            }
            event["event_hash"] = _hash(event)
            value["history"].append(event)
            value["revision"] += 1
            self._save(value)
            return result

    @staticmethod
    def _public(value: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(value)
        result.pop("scope", None)
        result.update(
            {
                "status": "review_required",
                "review_required": True,
                "local_only": True,
                "credibility_score": "not_available",
                "deception_inference": "not_available",
                "identity_inference": "not_available",
            }
        )
        return result

    def inventory(self) -> dict[str, Any]:
        return self._public(self._load())

    def add_people(self, payload: dict[str, Any]) -> dict[str, Any]:
        rows = payload.get("people")
        if not isinstance(rows, list) or not rows:
            raise IntakeWorkbenchError("people_invalid")

        def fn(value: dict[str, Any]) -> dict[str, Any]:
            known = {row["person_id"] for row in value["people"]}
            for row in rows:
                person_id = _id(row.get("person_id"), "person_id")
                if person_id in known:
                    raise IntakeWorkbenchError("duplicate_person_id", 409)
                value["people"].append(
                    {
                        "person_id": person_id,
                        "role": _text(row.get("role"), 128),
                        "user_confirmed": bool(row.get("user_confirmed")),
                        "review_required": True,
                    }
                )
                known.add(person_id)
            return self._public(value)

        return self._mutate(
            "people_added",
            [_id(row.get("person_id"), "person_id") for row in rows if isinstance(row, dict)],
            fn,
        )

    def add_statements(self, payload: dict[str, Any]) -> dict[str, Any]:
        rows = payload.get("statements")
        if not isinstance(rows, list) or not rows:
            raise IntakeWorkbenchError("statements_invalid")

        def fn(value: dict[str, Any]) -> dict[str, Any]:
            known, people = (
                {row["statement_id"] for row in value["statements"]},
                {row["person_id"] for row in value["people"]},
            )
            for row in rows:
                if not isinstance(row, dict):
                    raise IntakeWorkbenchError("statement_invalid")
                statement_id, speaker = (
                    _id(row.get("statement_id"), "statement_id"),
                    _id(row.get("speaker_id"), "speaker_id"),
                )
                source, kind = (
                    row.get("source_ref") or {},
                    str(row.get("statement_type") or "unknown"),
                )
                if statement_id in known or speaker not in people or kind not in _KINDS:
                    raise IntakeWorkbenchError("statement_model_invalid")
                exact = _text(row.get("exact_text"))
                if not exact:
                    raise IntakeWorkbenchError("exact_text_required")
                value["statements"].append(
                    {
                        "statement_id": statement_id,
                        "speaker_id": speaker,
                        "role": _text(row.get("role"), 128),
                        "source_ref": {
                            "record_id": _id(source.get("record_id"), "record_id"),
                            "source_hash": _text(source.get("source_hash"), 128),
                            "page_block_or_time": _text(source.get("page_block_or_time"), 128),
                        },
                        "statement_date": _text(row.get("statement_date"), 64),
                        "event_date": _text(row.get("event_date"), 64),
                        "exact_text": exact,
                        "statement_type": kind,
                        "oath_verification_candidate": bool(row.get("oath_verification_candidate")),
                        "context_before": _text(row.get("context_before")),
                        "context_after": _text(row.get("context_after")),
                        "question": _text(row.get("question")),
                        "answer": _text(row.get("answer")),
                        "topic_tags": [_text(tag, 128) for tag in row.get("topic_tags", [])],
                        "claim_links": [
                            _id(item, "claim_id") for item in row.get("claim_links", [])
                        ],
                        "ocr_or_translation_warning": bool(row.get("ocr_or_translation_warning")),
                        "reviewer_status": "review_required",
                    }
                )
                known.add(statement_id)
            return self._public(value)

        return self._mutate(
            "statements_added",
            [_id(row.get("statement_id"), "statement_id") for row in rows if isinstance(row, dict)],
            fn,
        )

    def compare(self, left_id: str, right_id: str) -> dict[str, Any]:
        value = self._load()
        left = next(
            (
                row
                for row in value["statements"]
                if row["statement_id"] == _id(left_id, "statement_id")
            ),
            None,
        )
        right = next(
            (
                row
                for row in value["statements"]
                if row["statement_id"] == _id(right_id, "statement_id")
            ),
            None,
        )
        if left is None or right is None:
            raise IntakeWorkbenchError("statement_not_found", 404)
        ratio = SequenceMatcher(
            None, left["exact_text"].casefold(), right["exact_text"].casefold()
        ).ratio()
        if left["exact_text"] == right["exact_text"]:
            status = "consistent"
        elif (
            left["event_date"] and right["event_date"] and left["event_date"] != right["event_date"]
        ):
            status = "date_conflict"
        elif not left["context_before"] or not right["context_before"]:
            status = "missing_prior_context"
        elif ratio > 0.6:
            status = "qualified"
        else:
            status = "materially_different_candidate"
        return {
            "status": "review_required",
            "comparison_status": status,
            "similarity": round(ratio, 4),
            "left": left,
            "right": right,
            "credibility": "not_determined",
            "deception": "not_determined",
            "limitations": ["Exact wording is preserved; comparison is not a character judgment."],
        }

    def outline(self, payload: dict[str, Any]) -> dict[str, Any]:
        statement_ids = [_id(item, "statement_id") for item in payload.get("statement_ids", [])]
        if not statement_ids:
            raise IntakeWorkbenchError("outline_statements_required")
        rows = [row for row in self._load()["statements"] if row["statement_id"] in statement_ids]
        if len(rows) != len(set(statement_ids)):
            raise IntakeWorkbenchError("statement_not_found", 404)
        return {
            "status": "review_required",
            "attorney_reviewer_work_product": True,
            "outline": [
                {
                    "statement_id": row["statement_id"],
                    "foundation_question": (
                        "Please identify the source record and surrounding context."
                    ),
                    "chronology_question": "What date or event does this statement address?",
                    "clarification_question": (
                        "What information remains unknown or needs correction?"
                    ),
                    "exhibit_identification_question": (
                        "Can the referenced exhibit be identified from its source?"
                    ),
                }
                for row in rows
            ],
            "prohibited": [
                "fabricating facts",
                "hiding contradictions",
                "altering quotes",
                "evading questions",
            ],
        }

    def receipt(self) -> dict[str, Any]:
        value = self._load()
        receipt = {
            "revision": value["revision"],
            "people_hash": _hash(value["people"]),
            "statements_hash": _hash(value["statements"]),
            "history_hash": _hash(value["history"]),
            "review_required": True,
            "issued_at": _now(),
        }
        receipt["receipt_hash"] = _hash(receipt)
        return receipt
