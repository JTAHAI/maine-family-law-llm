"""Encrypted state-level UCCJEA fact organizer; it cannot decide jurisdiction."""

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


def _t(v: Any, n: int = 4000) -> str:
    x = str(v or "").strip()
    if len(x) > n:
        raise IntakeWorkbenchError("text_limit_exceeded")
    return x


def _h(v: Any) -> str:
    return hashlib.sha256(json.dumps(v, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class UccjeaReviewStore:
    schema = "maine_family_law_llm.uccjea_review.v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).resolve()
        self.root = self.case_root / "29_UCCJEA_REVIEW"
        if (
            not self.case_root.is_dir()
            or self.case_root.is_symlink()
            or (self.root.exists() and self.root.is_symlink())
        ):
            raise IntakeWorkbenchError("uccjea_store_unavailable", 409)
        self.encryptor = LocalEnvelopeEncryptor(
            encryption_key
            or os.environ.get("MAINE_MATTER_STORE_KEY")
            or "local-development-key-change-me"
        )
        self.scope = hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24]

    @property
    def path(self):
        return self.root / "uccjea.json.enc"

    @property
    def lock(self):
        return self.root / ".uccjea.lock"

    def _load(self):
        if not self.path.exists():
            return {
                "schema": self.schema,
                "scope": self.scope,
                "connections": [],
                "proceedings": [],
                "relocations": [],
                "history": [],
                "revision": 0,
            }
        try:
            v = self.encryptor.decrypt_json(
                strict_json_load_path(self.path, max_bytes=8 * 1024 * 1024, require_object=True)
            )
        except Exception as e:
            raise IntakeWorkbenchError("uccjea_store_unavailable", 409) from e
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
                "event_id": f"uccjea_{uuid.uuid4().hex}",
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
                "exact_addresses_exposed": False,
                "jurisdiction_conclusion": "not_determined",
                "relocation_legality": "not_determined",
            }
        )
        return v

    def connections(self, p):
        rows = p.get("connections")
        if not isinstance(rows, list) or not rows:
            raise IntakeWorkbenchError("connections_invalid")

        def fn(v):
            for x in rows:
                src = x.get("source_ref") or {}
                v["connections"].append(
                    {
                        "connection_id": _id(x.get("connection_id"), "connection_id"),
                        "child_id": _id(x.get("child_id"), "child_id"),
                        "state_territory_country": _t(x.get("state_territory_country"), 96),
                        "date_start": _t(x.get("date_start"), 32),
                        "date_end": _t(x.get("date_end"), 32),
                        "residence_type": _t(x.get("residence_type"), 128),
                        "caregiver_role": _t(x.get("caregiver_role"), 128),
                        "school_care_connection": _t(x.get("school_care_connection"), 256),
                        "source_ref": {
                            "record_id": _id(src.get("record_id"), "record_id"),
                            "span": _t(src.get("span"), 128),
                        },
                        "disputed": bool(x.get("disputed")),
                        "address_masked": True,
                        "reviewer_status": "review_required",
                    }
                )
            return self.inventory()

        return self._mut(
            "connections_added",
            [_id(x.get("connection_id"), "connection_id") for x in rows if isinstance(x, dict)],
            fn,
        )

    def proceedings(self, p):
        rows = p.get("proceedings")
        if not isinstance(rows, list):
            raise IntakeWorkbenchError("proceedings_invalid")

        def fn(v):
            for x in rows:
                src = x.get("source_ref") or {}
                v["proceedings"].append(
                    {
                        "proceeding_id": _id(x.get("proceeding_id"), "proceeding_id"),
                        "jurisdiction": _t(x.get("jurisdiction"), 128),
                        "docket_safe_id": _t(x.get("docket_safe_id"), 128),
                        "proceeding_type": _t(x.get("proceeding_type"), 128),
                        "filing_date": _t(x.get("filing_date"), 32),
                        "order_date": _t(x.get("order_date"), 32),
                        "emergency_candidate": bool(x.get("emergency_candidate")),
                        "source_ref": {
                            "record_id": _id(src.get("record_id"), "record_id"),
                            "span": _t(src.get("span"), 128),
                        },
                        "reviewer_status": "review_required",
                    }
                )
            return self.inventory()

        return self._mut(
            "proceedings_added",
            [_id(x.get("proceeding_id"), "proceeding_id") for x in rows if isinstance(x, dict)],
            fn,
        )

    def factors(self):
        v = self._load()
        c = v["connections"]
        conf = []
        for a in c:
            for b in c:
                if (
                    a["connection_id"] < b["connection_id"]
                    and a["child_id"] == b["child_id"]
                    and a["state_territory_country"] != b["state_territory_country"]
                    and a["date_start"] <= b["date_end"]
                    and b["date_start"] <= a["date_end"]
                ):
                    conf.append(
                        {
                            "kind": "overlapping_state_history",
                            "connection_ids": [a["connection_id"], b["connection_id"]],
                        }
                    )
        return {
            "status": "review_required",
            "factors": [
                "home_state_facts",
                "recent_home_state_facts",
                "significant_connections",
                "substantial_evidence",
                "emergency_facts",
                "exclusive_continuing_jurisdiction",
                "inconvenient_forum",
                "simultaneous_proceedings",
                "temporary_absence",
                "relocation",
                "international_tribal_considerations",
            ],
            "conflicts": conf,
            "jurisdiction_conclusion": "not_determined",
        }

    def receipt(self):
        v = self._load()
        r = {
            "revision": v["revision"],
            "connections_hash": _h(v["connections"]),
            "proceedings_hash": _h(v["proceedings"]),
            "history_hash": _h(v["history"]),
            "review_required": True,
            "issued_at": _now(),
        }
        r["receipt_hash"] = _h(r)
        return r
