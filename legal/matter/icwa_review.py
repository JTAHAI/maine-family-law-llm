"""Encrypted ICWA inquiry/notice organizer; tribal determinations remain external."""

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


def _t(v: Any, n: int = 8000) -> str:
    x = str(v or "").strip()
    if len(x) > n:
        raise IntakeWorkbenchError("text_limit_exceeded")
    return x


def _h(v: Any) -> str:
    return hashlib.sha256(json.dumps(v, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class IcwaReviewStore:
    schema = "maine_family_law_llm.icwa_review.v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).resolve()
        self.root = self.case_root / "30_ICWA_REVIEW"
        if (
            not self.case_root.is_dir()
            or self.case_root.is_symlink()
            or (self.root.exists() and self.root.is_symlink())
        ):
            raise IntakeWorkbenchError("icwa_store_unavailable", 409)
        self.encryptor = LocalEnvelopeEncryptor(
            encryption_key
            or os.environ.get("MAINE_MATTER_STORE_KEY")
            or "local-development-key-change-me"
        )
        self.scope = hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24]

    @property
    def path(self):
        return self.root / "icwa.json.enc"

    @property
    def lock(self):
        return self.root / ".icwa.lock"

    def _load(self):
        if not self.path.exists():
            return {
                "schema": self.schema,
                "scope": self.scope,
                "inquiries": [],
                "notices": [],
                "responses": [],
                "history": [],
                "revision": 0,
            }
        try:
            v = self.encryptor.decrypt_json(
                strict_json_load_path(self.path, max_bytes=8 * 1024 * 1024, require_object=True)
            )
        except Exception as e:
            raise IntakeWorkbenchError("icwa_store_unavailable", 409) from e
        if v.get("schema") != self.schema or v.get("scope") != self.scope:
            raise IntakeWorkbenchError("cross_matter_access_denied", 404)
        return v

    def _save(self, v):
        atomic_write_bytes(
            self.path,
            json.dumps(self.encryptor.encrypt_json(v), sort_keys=True).encode(),
            mode=0o600,
        )

    def _mut(self, a, ids, fn):
        with exclusive_file_lock(self.lock):
            v = self._load()
            r = fn(v)
            e = {
                "event_id": f"icwa_{uuid.uuid4().hex}",
                "at": _now(),
                "action": a,
                "ids": ids,
                "previous_hash": v["history"][-1]["hash"] if v["history"] else "",
                "review_required": True,
            }
            e["hash"] = _h(e)
            v["history"].append(e)
            v["revision"] += 1
            self._save(v)
            return r

    def inventory(self):
        v = deepcopy(self._load())
        v.pop("scope", None)
        v.update(
            {
                "status": "review_required",
                "review_required": True,
                "local_only": True,
                "indian_child_determination": "not_determined",
                "membership_eligibility": "not_determined",
                "identity_inference": "not_available",
                "automatic_notice": False,
            }
        )
        return v

    def inquiry(self, p):
        rows = p.get("inquiries")
        if not isinstance(rows, list) or not rows:
            raise IntakeWorkbenchError("inquiries_invalid")

        def fn(v):
            for x in rows:
                src = x.get("source_ref") or {}
                v["inquiries"].append(
                    {
                        "inquiry_id": _id(x.get("inquiry_id"), "inquiry_id"),
                        "child_id": _id(x.get("child_id"), "child_id"),
                        "person_safe_id": _id(x.get("person_safe_id"), "person_safe_id"),
                        "question": _t(x.get("question")),
                        "response": _t(x.get("response")),
                        "source_ref": {
                            "record_id": _id(src.get("record_id"), "record_id"),
                            "span": _t(src.get("span"), 128),
                        },
                        "reviewer_status": "review_required",
                    }
                )
            return self.inventory()

        return self._mut(
            "inquiry_added",
            [_id(x.get("inquiry_id"), "inquiry_id") for x in rows if isinstance(x, dict)],
            fn,
        )

    def notices(self, p):
        rows = p.get("notices")
        if not isinstance(rows, list):
            raise IntakeWorkbenchError("notices_invalid")

        def fn(v):
            for x in rows:
                src = x.get("source_ref") or {}
                v["notices"].append(
                    {
                        "notice_id": _id(x.get("notice_id"), "notice_id"),
                        "recipient_safe_id": _id(x.get("recipient_safe_id"), "recipient_safe_id"),
                        "notice_status": _t(x.get("notice_status"), 128),
                        "source_ref": {
                            "record_id": _id(src.get("record_id"), "record_id"),
                            "span": _t(src.get("span"), 128),
                        },
                        "actual_delivery": "not_determined",
                        "reviewer_status": "review_required",
                    }
                )
            return self.inventory()

        return self._mut(
            "notice_recorded",
            [_id(x.get("notice_id"), "notice_id") for x in rows if isinstance(x, dict)],
            fn,
        )

    def completeness(self):
        v = self._load()
        return {
            "status": "review_required",
            "missing_inquiry": not bool(v["inquiries"]),
            "missing_notice_record": not bool(v["notices"]),
            "tribal_response": "not_determined",
            "record_completeness": "not_determined",
            "indian_child_determination": "not_determined",
        }

    def receipt(self):
        v = self._load()
        r = {
            "revision": v["revision"],
            "inquiries_hash": _h(v["inquiries"]),
            "notices_hash": _h(v["notices"]),
            "history_hash": _h(v["history"]),
            "review_required": True,
            "issued_at": _now(),
        }
        r["receipt_hash"] = _h(r)
        return r
