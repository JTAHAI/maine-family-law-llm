"""Fictional truncation and real interrupted-process recovery, not immutable storage."""

import json
import os
import subprocess
import sys

import pytest
from test_review_storage_boundary import reviewed as review_fixture

from legal.documents import storage
from legal.review import integrity
from legal.review import review_ledger as ledger


@pytest.fixture
def reviewed(tmp_path):
    return review_fixture.__wrapped__(tmp_path)


def _root(case, doc):
    return case / "19_DOCUMENT_WORKSPACE/reviews" / doc["document_id"]


def test_retained_head_detects_deleted_newest_decision(reviewed):
    case, doc, _, args = reviewed
    first = ledger.commit_review_decision(case, doc["document_id"], **args)
    new = ledger.prepare_review_request(
        case, doc["document_id"], authority_result={"status": "blocked"}
    )
    second = ledger.commit_review_decision(
        case,
        doc["document_id"],
        **{
            **args,
            "request_id": new["request_id"],
            "confirmation_token": new["confirmation_token"],
        },
    )
    root = _root(case, doc)
    # Delete only a newly-created fictional test record to simulate truncation.
    (root / "decisions" / (second["decision_id"] + ".json")).unlink()
    result = ledger.verify_review_ledger(case, doc["document_id"])
    assert not result["valid"] and result["history_head"]["status"] == "mismatch"
    history = ledger.list_review_history(case, doc["document_id"])
    assert (
        history["decision_count"] == 1
        and history["decisions"][0]["decision_id"] == first["decision_id"]
    )
    assert history["latest"] is None and history["review_required"]
    with pytest.raises(ledger.ReviewLedgerError):
        ledger.commit_review_decision(case, doc["document_id"], **args)


def test_deleted_head_is_not_silently_recreated_for_existing_history(reviewed):
    case, doc, _, args = reviewed
    ledger.commit_review_decision(case, doc["document_id"], **args)
    path = _root(case, doc) / integrity.HEAD
    path.unlink()
    assert not ledger.verify_review_ledger(case, doc["document_id"])["valid"]
    with pytest.raises(ledger.ReviewLedgerError, match="no authenticated head"):
        ledger.prepare_review_request(case, doc["document_id"], authority_result={})
    assert not path.exists()


@pytest.mark.parametrize("phase", [1, 2, 3])
def test_interruption_recovers_exactly_one_confirmed_decision(reviewed, monkeypatch, phase):
    case, doc, _, args = reviewed
    original = integrity._write
    calls = []

    def interrupted(path, value):
        original(path, value)
        calls.append(path)
        if len(calls) == phase:
            raise OSError("Fictional interrupted write")

    with monkeypatch.context() as scoped:
        scoped.setattr(integrity, "_write", interrupted)
        with pytest.raises(ledger.ReviewLedgerError, match="interrupted"):
            ledger.commit_review_decision(case, doc["document_id"], **args)
    history = ledger.list_review_history(case, doc["document_id"])
    assert history["decision_count"] == 1 and history["latest"]["notes"] == args["notes"]
    assert history["history_head"]["recovered_interrupted_commit"] is True
    assert ledger.verify_review_ledger(case, doc["document_id"])["valid"]
    assert history["pending_request_count"] == 0 and history["review_required"]
    with pytest.raises(ledger.ReviewLedgerError):
        ledger.commit_review_decision(case, doc["document_id"], **args)
    for path in _root(case, doc).rglob("*.json"):
        assert b"Fictional" not in path.read_bytes()


def test_journal_never_overwrites_changed_request(reviewed, monkeypatch):
    case, doc, _, args = reviewed
    original = integrity._write

    def interrupted(path, value):
        original(path, value)
        raise OSError("Fictional interruption")

    with monkeypatch.context() as scoped:
        scoped.setattr(integrity, "_write", interrupted)
        with pytest.raises(ledger.ReviewLedgerError):
            ledger.commit_review_decision(case, doc["document_id"], **args)
    root = _root(case, doc)
    path = root / "requests" / (args["request_id"] + ".json")
    request = storage.decode(path, path.read_bytes())
    request["packet"]["document_title"] = "Fictional changed request"
    request.pop("request_sha256")
    request["request_sha256"] = integrity._hash(request)
    changed = storage.encode(path, request)
    path.write_bytes(changed)
    head_before = (root / integrity.HEAD).read_bytes()
    assert not ledger.verify_review_ledger(case, doc["document_id"])["valid"]
    with pytest.raises(ledger.ReviewLedgerError, match="recovered"):
        ledger.list_review_history(case, doc["document_id"])
    assert path.read_bytes() == changed and (root / integrity.HEAD).read_bytes() == head_before
    assert not list((root / "decisions").glob("*.json"))


def test_real_process_exit_and_fresh_process_recovery(reviewed):
    case, doc, _, args = reviewed
    code = """import json,sys,os
from pathlib import Path
from legal.review import integrity,review_ledger as ledger
original=integrity._write
def die(path,value):
 original(path,value)
 if path.parent.name=='decisions': os._exit(73)
integrity._write=die
ledger.commit_review_decision(Path(sys.argv[1]),sys.argv[2],**json.loads(sys.argv[3]))
"""
    kwargs = dict(
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "TEMP": str(case), "TMP": str(case)},
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    crashed = subprocess.run(
        [sys.executable, "-B", "-c", code, str(case), doc["document_id"], json.dumps(args)],
        **kwargs,
    )
    assert crashed.returncode == 73
    resume = """from pathlib import Path
import sys,json
from legal.review.review_ledger import list_review_history
h=list_review_history(Path(sys.argv[1]),sys.argv[2])
print(json.dumps({'count':h['decision_count'],
 'recovered':h['history_head']['recovered_interrupted_commit'],
 'review_required':h['review_required']}))
"""
    restarted = subprocess.run(
        [sys.executable, "-B", "-c", resume, str(case), doc["document_id"]], **kwargs
    )
    assert restarted.returncode == 0, restarted.stderr
    assert json.loads(restarted.stdout) == {"count": 1, "recovered": True, "review_required": True}


def test_changed_revision_keeps_recovered_review_stale(reviewed, monkeypatch):
    from legal.documents.workspace import commit_revision, propose_revision
    from legal.review.reviewer_queue import build_reviewer_queue

    case, doc, _, args = reviewed
    original = integrity._write

    def interrupted(path, value):
        original(path, value)
        if path.parent.name == "decisions":
            raise OSError("Fictional interruption")

    with monkeypatch.context() as scoped:
        scoped.setattr(integrity, "_write", interrupted)
        with pytest.raises(ledger.ReviewLedgerError):
            ledger.commit_review_decision(case, doc["document_id"], **args)
    proposal = propose_revision(
        case,
        doc["document_id"],
        content="Fictional changed draft",
        base_revision_id=doc["current_revision_id"],
    )
    commit_revision(
        case,
        doc["document_id"],
        revision_id=proposal["revision_id"],
        confirmation_token=proposal["confirmation_token"],
        confirmed=True,
    )
    history = ledger.list_review_history(case, doc["document_id"])
    assert history["history_head"]["recovered_interrupted_commit"]
    assert not history["latest_is_current"] and history["review_required"]
    queue = build_reviewer_queue(case)["items"][0]
    assert queue["queue_status"] == "stale_review_after_revision_change"
    assert not queue["filing_ready"] and queue["review_required"]


def test_corrupt_head_fails_closed_without_repairing_it(reviewed):
    case, doc, _, args = reviewed
    ledger.commit_review_decision(case, doc["document_id"], **args)
    head = _root(case, doc) / integrity.HEAD
    raw = json.loads(head.read_bytes())
    raw["envelope"]["ciphertext"] = "AAAA"
    changed = json.dumps(raw).encode()
    head.write_bytes(changed)
    assert not ledger.verify_review_ledger(case, doc["document_id"])["valid"]
    with pytest.raises(ledger.ReviewLedgerError, match="authenticated or recovered"):
        ledger.list_review_history(case, doc["document_id"])
    assert head.read_bytes() == changed
