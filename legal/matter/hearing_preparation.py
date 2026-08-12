"""Encrypted, review-first hearing packs assembled from explicit local references."""

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


def _id(v: Any, n: str) -> str:
    x = str(v or "").strip().casefold()
    if not _ID.fullmatch(x):
        raise IntakeWorkbenchError(f"{n}_invalid")
    return x


def _text(v: Any, n: int = 8000) -> str:
    x = str(v or "").strip()
    if len(x) > n:
        raise IntakeWorkbenchError("text_limit_exceeded")
    return x


def _hash(v: Any) -> str:
    return hashlib.sha256(json.dumps(v, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class HearingPreparationStore:
    schema = "maine_family_law_llm.hearing_preparation.v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).resolve()
        self.root = self.case_root / "27_HEARING_PREPARATION"
        if (
            not self.case_root.is_dir()
            or self.case_root.is_symlink()
            or (self.root.exists() and self.root.is_symlink())
        ):
            raise IntakeWorkbenchError("hearing_store_unavailable", 409)
        self.encryptor = LocalEnvelopeEncryptor(
            encryption_key
            or os.environ.get("MAINE_MATTER_STORE_KEY")
            or "local-development-key-change-me"
        )
        self.scope = hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24]

    @property
    def path(self) -> Path:
        return self.root / "hearings.json.enc"

    @property
    def lock(self) -> Path:
        return self.root / ".hearings.lock"

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "schema": self.schema,
                "scope": self.scope,
                "hearings": [],
                "notes": [],
                "history": [],
                "revision": 0,
            }
        try:
            v = self.encryptor.decrypt_json(
                strict_json_load_path(self.path, max_bytes=8 * 1024 * 1024, require_object=True)
            )
        except Exception as exc:
            raise IntakeWorkbenchError("hearing_store_unavailable", 409) from exc
        if v.get("schema") != self.schema or v.get("scope") != self.scope:
            raise IntakeWorkbenchError("cross_matter_access_denied", 404)
        return v

    def _save(self, v: dict[str, Any]) -> None:
        atomic_write_bytes(
            self.path,
            json.dumps(self.encryptor.encrypt_json(v), sort_keys=True).encode(),
            mode=0o600,
        )

    def _mutate(self, a: str, ids: list[str], fn):
        with exclusive_file_lock(self.lock):
            v = self._load()
            r = fn(v)
            e = {
                "event_id": f"hearing_event_{uuid.uuid4().hex}",
                "at": _now(),
                "action": a,
                "ids": ids,
                "previous_hash": v["history"][-1]["event_hash"] if v["history"] else "",
                "review_required": True,
            }
            e["event_hash"] = _hash(e)
            v["history"].append(e)
            v["revision"] += 1
            self._save(v)
            return r

    @staticmethod
    def _public(v: dict[str, Any]) -> dict[str, Any]:
        r = deepcopy(v)
        r.pop("scope", None)
        r.update(
            {
                "status": "review_required",
                "review_required": True,
                "local_only": True,
                "outcome_prediction": "not_available",
                "automatic_filing": False,
                "improper_tactics": "not_available",
            }
        )
        return r

    def inventory(self) -> dict[str, Any]:
        return self._public(self._load())

    def add_hearings(self, p: dict[str, Any]) -> dict[str, Any]:
        rows = p.get("hearings")
        if not isinstance(rows, list) or not rows:
            raise IntakeWorkbenchError("hearings_invalid")

        def fn(v):
            known = {x["hearing_id"] for x in v["hearings"]}
            for x in rows:
                h = _id(x.get("hearing_id"), "hearing_id")
                notice = x.get("notice_ref") or {}
                if h in known:
                    raise IntakeWorkbenchError("duplicate_hearing_id", 409)
                v["hearings"].append(
                    {
                        "hearing_id": h,
                        "notice_ref": {
                            "record_id": _id(notice.get("record_id"), "notice_record_id"),
                            "source_hash": _text(notice.get("source_hash"), 128),
                        },
                        "date_time_location": _text(x.get("date_time_location"), 256),
                        "hearing_type_candidate": _text(x.get("hearing_type_candidate"), 128),
                        "issues": x.get("issues", []),
                        "operative_order_ids": [
                            _id(i, "order_id") for i in x.get("operative_order_ids", [])
                        ],
                        "authority": [
                            {
                                "citation": _text(i.get("citation"), 512),
                                "source_ref": i.get("source_ref") or {},
                                "freshness": _text(i.get("freshness"), 32),
                            }
                            for i in x.get("authority", [])
                            if isinstance(i, dict)
                        ],
                        "claims": [
                            {
                                "claim": _text(i.get("claim")),
                                "source_ref": i.get("source_ref") or {},
                            }
                            for i in x.get("claims", [])
                            if isinstance(i, dict)
                        ],
                        "exhibit_ids": [_id(i, "exhibit_id") for i in x.get("exhibit_ids", [])],
                        "witness_topics": x.get("witness_topics", []),
                        "findings": x.get("findings", []),
                        "deadline_service_status": _text(x.get("deadline_service_status"), 256),
                        "reviewer_status": "review_required",
                    }
                )
                known.add(h)
            return self._public(v)

        return self._mutate(
            "hearing_added",
            [_id(x.get("hearing_id"), "hearing_id") for x in rows if isinstance(x, dict)],
            fn,
        )

    def blockers(self, hid: str) -> dict[str, Any]:
        h = next(
            (x for x in self._load()["hearings"] if x["hearing_id"] == _id(hid, "hearing_id")), None
        )
        if h is None:
            raise IntakeWorkbenchError("hearing_not_found", 404)
        b = []
        if not h["notice_ref"]["record_id"]:
            b.append("missing_notice")
        if not h["operative_order_ids"]:
            b.append("missing_operative_order")
        if not h["issues"]:
            b.append("missing_issues")
        if any(
            a["freshness"] not in {"fresh", "current"} or not a["source_ref"]
            for a in h["authority"]
        ):
            b.append("stale_or_unresolved_authority")
        if any(not c["source_ref"] for c in h["claims"]):
            b.append("unsupported_claim")
        if not h["exhibit_ids"]:
            b.append("missing_exhibit")
        return {
            "status": "review_required",
            "hearing_id": h["hearing_id"],
            "blockers": b,
            "outcome_prediction": "not_available",
        }

    def pack(self, hid: str) -> dict[str, Any]:
        h = next(
            (x for x in self._load()["hearings"] if x["hearing_id"] == _id(hid, "hearing_id")), None
        )
        if h is None:
            raise IntakeWorkbenchError("hearing_not_found", 404)
        p = {
            "hearing_id": h["hearing_id"],
            "scope": "review-required local hearing pack",
            "hearing_notice": h["notice_ref"],
            "issues": h["issues"],
            "orders": h["operative_order_ids"],
            "authority": h["authority"],
            "evidence_claims": h["claims"],
            "exhibits": h["exhibit_ids"],
            "witness_topics": h["witness_topics"],
            "findings": h["findings"],
            "deadlines_service": h["deadline_service_status"],
            "blockers": self.blockers(hid)["blockers"],
            "review_required": True,
        }
        p["pack_hash"] = _hash(p)
        return p

    def add_note(self, p: dict[str, Any]) -> dict[str, Any]:
        hid = _id(p.get("hearing_id"), "hearing_id")

        def fn(v):
            if not any(x["hearing_id"] == hid for x in v["hearings"]):
                raise IntakeWorkbenchError("hearing_not_found", 404)
            n = {
                "note_id": f"court_note_{uuid.uuid4().hex}",
                "hearing_id": hid,
                "issue": _text(p.get("issue")),
                "ruling": _text(p.get("ruling")),
                "exhibit_status": _text(p.get("exhibit_status")),
                "witness": _text(p.get("witness")),
                "follow_up": _text(p.get("follow_up")),
                "source_ref": p.get("source_ref") or {},
                "review_required": True,
            }
            n["note_hash"] = _hash(n)
            v["notes"].append(n)
            return deepcopy(n)

        return self._mutate("courtroom_note_added", [hid], fn)

    def receipt(self) -> dict[str, Any]:
        v = self._load()
        r = {
            "revision": v["revision"],
            "hearings_hash": _hash(v["hearings"]),
            "notes_hash": _hash(v["notes"]),
            "history_hash": _hash(v["history"]),
            "review_required": True,
            "issued_at": _now(),
        }
        r["receipt_hash"] = _hash(r)
        return r
