"""Encrypted local review head and recoverable single-decision journal.

Detects loss/reordering relative to the retained head. This is not an external
timestamp or protection against replacing the complete workspace with a backup.
Callers hold the workspace review lock throughout every operation.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from legal.documents import storage
from legal.security.durable_io import atomic_write_bytes, read_bounded_regular_file

HEAD = ".review-head.json"
SCHEMA = "encrypted_review_head_v1"
ZERO = "0" * 64


def _hash(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def _valid_hash(value):
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def _valid_id(value):
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{32}", value) is not None


def _check_hash(value, field):
    if not isinstance(value, dict) or not _valid_hash(value.get(field)):
        raise ValueError("review_history_payload_invalid")
    if _hash({key: item for key, item in value.items() if key != field}) != value[field]:
        raise ValueError("review_history_hash_mismatch")


def _read(path):
    raw = read_bounded_regular_file(path, max_bytes=storage.MAX_ENVELOPE)
    if json.loads(raw).get("storage_format") != storage.FORMAT:
        raise ValueError("review_head_plaintext_refused")
    value = storage.decode(path, raw)
    if not isinstance(value, dict):
        raise ValueError("review_history_payload_invalid")
    return value


def _write(path, value):
    atomic_write_bytes(path, storage.encode(path, value))


def load(root: Path):
    path = root / HEAD
    storage._location(path)
    if not path.exists():
        return None
    value = _read(path)
    if (
        set(value)
        != {
            "schema",
            "document_id",
            "sequence",
            "head_sha256",
            "pending",
            "recovered_interrupted_commit",
        }
        or value["schema"] != SCHEMA
        or value["document_id"] != root.name
        or type(value["sequence"]) is not int
        or not 0 <= value["sequence"] <= 500
        or not _valid_hash(value["head_sha256"])
        or type(value["recovered_interrupted_commit"]) is not bool
    ):
        raise ValueError("review_head_invalid")
    return value


def initialize(root: Path):
    if load(root) is not None:
        return
    if next((root / "decisions").glob("*.json"), None) is not None:
        raise ValueError("review_existing_history_has_no_head")
    _write(
        root / HEAD,
        {
            "schema": SCHEMA,
            "document_id": root.name,
            "sequence": 0,
            "head_sha256": ZERO,
            "pending": None,
            "recovered_interrupted_commit": False,
        },
    )


def verify(root: Path, rows: list[dict]):
    head = load(root)
    if head is None:
        return {
            "valid": not rows,
            "status": "missing" if rows else "not_started",
            "recovered_interrupted_commit": False,
        }
    valid = (
        head["pending"] is None
        and head["sequence"] == len(rows)
        and head["head_sha256"] == (rows[-1].get("decision_sha256") if rows else ZERO)
    )
    return {
        "valid": valid,
        "status": "verified" if valid else "mismatch",
        "recovered_interrupted_commit": head["recovered_interrupted_commit"],
        "sequence": head["sequence"],
        "head_sha256": head["head_sha256"],
    }


def recover(root: Path, *, interrupted: bool = True):
    head = load(root)
    if head is None or head["pending"] is None:
        return
    pending = head["pending"]
    if not isinstance(pending, dict) or set(pending) != {
        "record",
        "request",
        "previous_request_sha256",
    }:
        raise ValueError("review_journal_invalid")
    record, request = pending["record"], pending["request"]
    _check_hash(record, "decision_sha256")
    _check_hash(request, "request_sha256")
    if (
        not _valid_id(record.get("decision_id"))
        or not _valid_id(record.get("request_id"))
        or record.get("document_id") != root.name
        or request.get("document_id") != root.name
        or record.get("request_id") != request.get("request_id")
        or request.get("decision_id") != record["decision_id"]
        or record.get("revision_id") != request.get("revision_id")
        or record.get("packet_sha256") != request.get("packet", {}).get("packet_sha256")
        or record.get("sequence") != head["sequence"] + 1
        or record.get("previous_decision_sha256") != head["head_sha256"]
        or request.get("status") != "consumed"
        or "confirmation_token_sha256" in request
        or not _valid_hash(pending["previous_request_sha256"])
    ):
        raise ValueError("review_journal_binding_invalid")

    target = root / "decisions" / (record["decision_id"] + ".json")
    request_path = root / "requests" / (record["request_id"] + ".json")
    # Check every precondition before restoring any interrupted write. Never
    # overwrite a changed/corrupt existing record to manufacture a valid history.
    existing = []
    for path in (root / "decisions").glob("*.json"):
        if len(existing) > 500:
            raise ValueError("review_history_limit")
        item = _read(path)
        _check_hash(item, "decision_sha256")
        if item.get("document_id") != root.name or item.get("decision_id") != path.stem:
            raise ValueError("review_history_binding_invalid")
        if path == target:
            if item != record:
                raise ValueError("review_interrupted_decision_changed")
        else:
            existing.append(item)
    existing.sort(key=lambda item: item.get("sequence", -1))
    previous = ZERO
    for sequence, item in enumerate(existing, 1):
        if item.get("sequence") != sequence or item.get("previous_decision_sha256") != previous:
            raise ValueError("review_history_chain_invalid")
        previous = item["decision_sha256"]
    if len(existing) != head["sequence"] or previous != head["head_sha256"]:
        raise ValueError("review_history_truncated")
    current_request = _read(request_path)
    _check_hash(current_request, "request_sha256")
    if current_request["request_sha256"] not in {
        pending["previous_request_sha256"],
        request["request_sha256"],
    }:
        raise ValueError("review_interrupted_request_changed")
    if not target.exists():
        _write(target, record)
    if current_request != request:
        _write(request_path, request)
    _write(
        root / HEAD,
        {
            **head,
            "sequence": record["sequence"],
            "head_sha256": record["decision_sha256"],
            "pending": None,
            "recovered_interrupted_commit": interrupted,
        },
    )


def commit(root: Path, record: dict, request: dict, previous_request_sha256: str):
    initialize(root)
    head = load(root)
    if head["pending"] is not None:
        raise ValueError("review_commit_already_pending")
    if (
        record["sequence"] != head["sequence"] + 1
        or record["previous_decision_sha256"] != head["head_sha256"]
    ):
        raise ValueError("review_commit_head_changed")
    _write(
        root / HEAD,
        {
            **head,
            "pending": {
                "record": record,
                "request": request,
                "previous_request_sha256": previous_request_sha256,
            },
        },
    )
    recover(root, interrupted=False)
