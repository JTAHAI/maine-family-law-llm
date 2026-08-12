"""Encrypted, review-only discovery and disclosure tracker."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path

_ID = re.compile(r"[a-z][a-z0-9_-]{2,79}\Z")
_KINDS = frozenset(
    {
        "initial_disclosure",
        "interrogatory",
        "request_for_production",
        "request_for_admission",
        "subpoena_record",
        "informal_request",
        "supplemental_response",
        "deficiency_notice",
        "protective_order_record",
        "unknown",
    }
)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _hash(v: Any) -> str:
    return hashlib.sha256(json.dumps(v, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _id(v: Any, n: str) -> str:
    x = str(v or "").strip().casefold()
    if not _ID.fullmatch(x):
        raise IntakeWorkbenchError(f"{n}_invalid")
    return x


def _text(v: Any, limit: int = 8_000) -> str:
    x = str(v or "").strip()
    if len(x) > limit:
        raise IntakeWorkbenchError("text_limit_exceeded")
    return x


class DiscoveryWorkbenchStore:
    schema = "maine_family_law_llm.discovery_workbench.v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).resolve()
        self.root = self.case_root / "24_DISCOVERY_DISCLOSURE"
        if (
            not self.case_root.is_dir()
            or self.case_root.is_symlink()
            or (self.root.exists() and self.root.is_symlink())
        ):
            raise IntakeWorkbenchError("discovery_store_unavailable", 409)
        self.encryptor = LocalEnvelopeEncryptor(
            encryption_key
            or os.environ.get("MAINE_MATTER_STORE_KEY")
            or "local-development-key-change-me"
        )
        self.scope = hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24]

    @property
    def path(self) -> Path:
        return self.root / "discovery.json.enc"

    @property
    def lock(self) -> Path:
        return self.root / ".discovery.lock"

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "schema": self.schema,
                "scope": self.scope,
                "items": [],
                "productions": [],
                "history": [],
                "revision": 0,
            }
        try:
            value = self.encryptor.decrypt_json(
                strict_json_load_path(self.path, max_bytes=8 * 1024 * 1024, require_object=True)
            )
        except Exception as exc:
            raise IntakeWorkbenchError("discovery_store_unavailable", 409) from exc
        if value.get("schema") != self.schema or value.get("scope") != self.scope:
            raise IntakeWorkbenchError("cross_matter_access_denied", 404)
        return value

    def _save(self, v: dict[str, Any]) -> None:
        atomic_write_bytes(
            self.path,
            json.dumps(self.encryptor.encrypt_json(v), sort_keys=True).encode(),
            mode=0o600,
        )

    def _mutate(self, action: str, ids: list[str], fn):  # type: ignore[no-untyped-def]
        with exclusive_file_lock(self.lock):
            v = self._load()
            result = fn(v)
            prior = v["history"][-1]["hash"] if v["history"] else ""
            event = {
                "event_id": f"discovery_event_{uuid.uuid4().hex}",
                "at": _now(),
                "action": action,
                "ids": ids,
                "previous_hash": prior,
                "review_required": True,
            }
            event["hash"] = _hash(event)
            v["history"].append(event)
            v["revision"] += 1
            self._save(v)
            return result

    def public(self, v: dict[str, Any]) -> dict[str, Any]:
        r = deepcopy(v)
        r.pop("scope", None)
        r.update(
            {
                "status": "review_required",
                "review_required": True,
                "local_only": True,
                "automatic_service": False,
                "subpoena_issuance": False,
                "privilege_determination": "not_determined",
            }
        )
        return r

    def inventory(self) -> dict[str, Any]:
        return self.public(self._load())

    def add_items(self, payload: dict[str, Any]) -> dict[str, Any]:
        rows = payload.get("items")
        if not isinstance(rows, list) or not rows:
            raise IntakeWorkbenchError("discovery_items_invalid")

        def fn(v):
            seen = {x["item_id"] for x in v["items"]}
            for x in rows:
                if not isinstance(x, dict):
                    raise IntakeWorkbenchError("discovery_item_invalid")
                item_id = _id(x.get("item_id"), "item_id")
                kind = str(x.get("kind") or "unknown")
                if item_id in seen or kind not in _KINDS:
                    raise IntakeWorkbenchError("item_id_or_kind_invalid")
                source = x.get("source_ref") or {}
                status = str(x.get("mapping_status") or "reviewer_required")
                v["items"].append(
                    {
                        "item_id": item_id,
                        "kind": kind,
                        "set_number": _text(x.get("set_number"), 64),
                        "item_number": _text(x.get("item_number"), 64),
                        "exact_request_text": _text(x.get("exact_request_text"), 20_000),
                        "source_ref": {
                            "record_id": _id(source.get("record_id"), "record_id"),
                            "source_hash": _text(source.get("source_hash"), 128),
                            "page": source.get("page"),
                        },
                        "requesting_role": _text(x.get("requesting_role"), 128),
                        "responding_role": _text(x.get("responding_role"), 128),
                        "service_event_id": _text(x.get("service_event_id"), 80),
                        "candidate_response_date": _text(x.get("candidate_response_date"), 64),
                        "response_text": _text(x.get("response_text"), 20_000),
                        "objection_text": _text(x.get("objection_text"), 20_000),
                        "mapping_status": status,
                        "privilege_flags": [
                            _text(i, 128)
                            for i in x.get("privilege_flags", [])
                            if isinstance(i, str)
                        ],
                        "reviewer_status": "review_required",
                    }
                )
                seen.add(item_id)
            return self.public(v)

        return self._mutate(
            "items_added",
            [_id(x.get("item_id"), "item_id") for x in rows if isinstance(x, dict)],
            fn,
        )

    def add_productions(self, payload: dict[str, Any]) -> dict[str, Any]:
        rows = payload.get("productions")
        if not isinstance(rows, list):
            raise IntakeWorkbenchError("productions_invalid")

        def fn(v):
            for x in rows:
                if not isinstance(x, dict):
                    raise IntakeWorkbenchError("production_invalid")
                v["productions"].append(
                    {
                        "production_id": _id(x.get("production_id"), "production_id"),
                        "source_hash": _text(x.get("source_hash"), 128),
                        "page_range": _text(x.get("page_range"), 128),
                        "produced_by_role": _text(x.get("produced_by_role"), 128),
                        "production_date_candidate": _text(x.get("production_date_candidate"), 64),
                        "request_ids": [_id(i, "request_id") for i in x.get("request_ids", [])],
                        "confidentiality_designation": _text(
                            x.get("confidentiality_designation"), 256
                        ),
                        "duplicate_group": _text(x.get("duplicate_group"), 128),
                        "missing_range": _text(x.get("missing_range"), 256),
                        "changed_copy": bool(x.get("changed_copy")),
                        "review_status": "review_required",
                    }
                )
            return self.public(v)

        return self._mutate(
            "productions_added",
            [_id(x.get("production_id"), "production_id") for x in rows if isinstance(x, dict)],
            fn,
        )

    def gaps(self) -> dict[str, Any]:
        v = self._load()
        produced = {i for p in v["productions"] for i in p["request_ids"]}
        return {
            "status": "review_required",
            "review_required": True,
            "unanswered_items": [
                x["item_id"]
                for x in v["items"]
                if not x["response_text"] and not x["objection_text"]
            ],
            "objection_only_items": [
                x["item_id"] for x in v["items"] if x["objection_text"] and not x["response_text"]
            ],
            "unmapped_productions": [
                x["production_id"] for x in v["productions"] if not x["request_ids"]
            ],
            "items_without_production": [
                x["item_id"] for x in v["items"] if x["item_id"] not in produced
            ],
            "privilege_candidates": [x["item_id"] for x in v["items"] if x["privilege_flags"]],
            "compliance": "not_determined",
        }

    def receipt(self) -> dict[str, Any]:
        v = self._load()
        r = {
            "revision": v["revision"],
            "items_hash": _hash(v["items"]),
            "productions_hash": _hash(v["productions"]),
            "review_required": True,
            "issued_at": _now(),
        }
        r["receipt_hash"] = _hash(r)
        return r
