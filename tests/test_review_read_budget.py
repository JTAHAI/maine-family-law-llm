"""Real encryption/read budget on a tiny fictional review; no timing mocks."""

import json
import os
import time
from collections import Counter
from pathlib import Path

import pytest
from test_review_storage_boundary import reviewed as review_fixture

from legal.documents import storage
from legal.documents.workspace import DocumentWorkspaceError, get_document
from legal.review import review_ledger as ledger
from legal.review.reviewer_queue import build_reviewer_queue


def test_queue_read_budget(tmp_path, monkeypatch):
    case, doc, _, args = review_fixture.__wrapped__(tmp_path)
    ledger.commit_review_decision(case, doc["document_id"], **args)
    original = storage.decode
    reads = Counter()

    def decode(path, raw):
        reads[path.relative_to(case).as_posix()] += 1
        return original(path, raw)

    monkeypatch.setattr(storage, "decode", decode)
    started = time.monotonic()
    queue = build_reviewer_queue(case)
    elapsed = time.monotonic() - started
    assert queue["items"][0]["queue_status"] == "changes_requested"
    assert queue["items"][0]["review_required"]
    report = {
        "fictional_only": True,
        "real_encryption": True,
        "seconds": elapsed,
        "decryptions": dict(reads),
        "total_decryptions": sum(reads.values()),
    }
    target = os.environ.get("MFL_REVIEW_BUDGET_REPORT")
    if target:
        output = Path(target).resolve()
        assert output.is_relative_to(Path(__file__).resolve().parents[1] / "dist")
        assert not output.exists()
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    assert all(n == 1 for p, n in reads.items() if "/decisions/" in p or "/requests/" in p)
    assert sum(n for p, n in reads.items() if "/revisions/" in p) == 1
    assert sum(reads.values()) <= 7


@pytest.mark.parametrize("damage", ["revision", "head", "decision"])
def test_next_queue_read_reauthenticates_changed_bytes(tmp_path, damage):
    case, doc, _, args = review_fixture.__wrapped__(tmp_path)
    ledger.commit_review_decision(case, doc["document_id"], **args)
    assert build_reviewer_queue(case)["count"] == 1
    root = case / "19_DOCUMENT_WORKSPACE"
    patterns = {
        "revision": "documents/*/revisions/*.json",
        "head": "reviews/*/.review-head.json",
        "decision": "reviews/*/decisions/*.json",
    }
    path = next(root.glob(patterns[damage]))
    payload = json.loads(path.read_bytes())
    payload["envelope"]["ciphertext"] = "AAAA"
    raw = json.dumps(payload).encode()
    path.write_bytes(raw)  # Corrupt only this test's fresh fictional artifact.
    with pytest.raises((ledger.ReviewLedgerError, DocumentWorkspaceError)):
        build_reviewer_queue(case)
    assert path.read_bytes() == raw


def test_metadata_option_does_not_change_default_document_response(tmp_path):
    case, doc, _, _ = review_fixture.__wrapped__(tmp_path)
    full = get_document(case, doc["document_id"])
    compact = get_document(case, doc["document_id"], include_history=False)
    assert compact == {k: v for k, v in full.items() if k != "revisions"}
    assert compact["content"] == "Fictional notice."
    assert len(full["revisions"]) == 1
