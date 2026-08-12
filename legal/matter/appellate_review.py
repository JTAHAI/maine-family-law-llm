"""Encrypted appellate record and preservation review; never predicts merits or deadlines."""

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


class AppellateReviewStore:
    schema = "maine_family_law_llm.appellate_review.v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).resolve()
        self.root = self.case_root / "28_APPELLATE_REVIEW"
        if (
            not self.case_root.is_dir()
            or self.case_root.is_symlink()
            or (self.root.exists() and self.root.is_symlink())
        ):
            raise IntakeWorkbenchError("appellate_store_unavailable", 409)
        self.encryptor = LocalEnvelopeEncryptor(
            encryption_key
            or os.environ.get("MAINE_MATTER_STORE_KEY")
            or "local-development-key-change-me"
        )
        self.scope = hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24]

    @property
    def path(self) -> Path:
        return self.root / "appeals.json.enc"

    @property
    def lock(self) -> Path:
        return self.root / ".appeals.lock"

    def _load(self):
        if not self.path.exists():
            return {
                "schema": self.schema,
                "scope": self.scope,
                "appeals": [],
                "history": [],
                "revision": 0,
            }
        try:
            v = self.encryptor.decrypt_json(
                strict_json_load_path(self.path, max_bytes=8 * 1024 * 1024, require_object=True)
            )
        except Exception as e:
            raise IntakeWorkbenchError("appellate_store_unavailable", 409) from e
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
                "event_id": f"appeal_event_{uuid.uuid4().hex}",
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
                "merit_prediction": "not_available",
                "reversal_prediction": "not_available",
                "deadline_advice": "candidate_only",
            }
        )
        return v

    def add(self, p):
        rows = p.get("appeals")
        if not isinstance(rows, list) or not rows:
            raise IntakeWorkbenchError("appeals_invalid")

        def fn(v):
            ids = {x["appeal_id"] for x in v["appeals"]}
            for x in rows:
                aid = _id(x.get("appeal_id"), "appeal_id")
                jud = x.get("judgment_ref") or {}
                if aid in ids:
                    raise IntakeWorkbenchError("duplicate_appeal_id", 409)
                v["appeals"].append(
                    {
                        "appeal_id": aid,
                        "lower_matter": _t(x.get("lower_matter"), 128),
                        "judgment_ref": {
                            "record_id": _id(jud.get("record_id"), "judgment_record_id"),
                            "source_hash": _t(jud.get("source_hash"), 128),
                        },
                        "entry_date": _t(x.get("entry_date"), 64),
                        "post_judgment_motions": x.get("post_judgment_motions", []),
                        "record_items": x.get("record_items", []),
                        "issues": x.get("issues", []),
                        "authority": x.get("authority", []),
                        "citations": x.get("citations", []),
                        "reviewer_status": "review_required",
                    }
                )
                ids.add(aid)
            return self.inventory()

        return self._mut(
            "appeal_added",
            [_id(x.get("appeal_id"), "appeal_id") for x in rows if isinstance(x, dict)],
            fn,
        )

    def verify(self, aid):
        a = next(
            (x for x in self._load()["appeals"] if x["appeal_id"] == _id(aid, "appeal_id")), None
        )
        if not a:
            raise IntakeWorkbenchError("appeal_not_found", 404)
        missing = []
        if not a["judgment_ref"]["record_id"]:
            missing.append("missing_judgment")
        for i in a["issues"]:
            if not isinstance(i, dict) or not i.get("ruling_ref"):
                missing.append("missing_ruling")
        for c in a["citations"]:
            if not isinstance(c, dict) or not c.get("source_hash") or not c.get("locator"):
                missing.append("unresolved_citation")
        if any(
            not isinstance(i, dict)
            or not i.get("source_ref")
            or i.get("freshness") not in ("fresh", "current")
            for i in a["authority"]
        ):
            missing.append("stale_or_unresolved_authority")
        if any(
            not isinstance(i, dict)
            or i.get("kind") in ("transcript", "exhibit")
            and not i.get("record_id")
            for i in a["record_items"]
        ):
            missing.append("missing_record_component")
        return {
            "status": "review_required",
            "appeal_id": a["appeal_id"],
            "blockers": sorted(set(missing)),
            "preservation": "not_determined",
            "merit_prediction": "not_available",
            "final_like_export_blocked": bool(missing),
        }

    def packet(self, aid):
        a = next(
            (x for x in self._load()["appeals"] if x["appeal_id"] == _id(aid, "appeal_id")), None
        )
        if not a:
            raise IntakeWorkbenchError("appeal_not_found", 404)
        p = {
            "appeal_id": a["appeal_id"],
            "judgment": a["judgment_ref"],
            "issues": a["issues"],
            "authority": a["authority"],
            "record_inventory": a["record_items"],
            "citations": a["citations"],
            "verification": self.verify(aid),
            "review_required": True,
        }
        p["packet_hash"] = _h(p)
        return p

    def receipt(self):
        v = self._load()
        r = {
            "revision": v["revision"],
            "appeals_hash": _h(v["appeals"]),
            "history_hash": _h(v["history"]),
            "review_required": True,
            "issued_at": _now(),
        }
        r["receipt_hash"] = _h(r)
        return r
