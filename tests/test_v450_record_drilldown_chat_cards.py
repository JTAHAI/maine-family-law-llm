"""v4.5.0 regression tests: private-record chat cards, drill-down controls, and security.

Covers:
- Version and Store target remain aligned after later releases
- Chat response groups citations into clickable record cards (no plain repeated text)
- Duplicate snippets collapse within the same source/page key
- Cards surface safe filename, doc type, match count, page list, and snippet
- workbench.js renders data-open-record controls and /api/records/open/ links
- No file:// URLs anywhere in the workbench script
- Opaque tokens scope correctly to the active corpus (cross-corpus rejected)
- Missing file → 404, hash mismatch → 409, traversal → 404
- ZIP members and email attachments open correctly
- records-only responses never append raw "Relevant record slices:" boilerplate
- record_groups present for both direct and non-direct private-record answers
"""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from email.message import EmailMessage
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from maine_family_law_llm import api
from maine_family_law_llm.version import (
    BUILD_NUMBER,
    PACKAGE_VERSION,
    UI_PASS_MARKER,
    VERSION,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=144, height=144)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _staged_row(
    case_root: Path,
    *,
    evidence_id: str = "REC-1",
    data: bytes | None = None,
    suffix: str = ".pdf",
) -> dict:
    data = data if data is not None else _pdf_bytes()
    staged = case_root / "02_PRIVATE_FORENSIC_MASTER" / "files" / f"{evidence_id}{suffix}"
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_bytes(data)
    return {
        "evidence_id": evidence_id,
        "source_path": str(case_root.parent / "never-open-this-original.pdf"),
        "private_copy_relpath": staged.relative_to(case_root).as_posix(),
        "source_hash": hashlib.sha256(data).hexdigest(),
        "source_type": suffix.lstrip("."),
        "source_locator": staged.name,
    }


def _client_for(monkeypatch, case_root: Path, rows: list[dict]) -> TestClient:
    monkeypatch.setattr(api, "active_case_root", lambda: case_root)
    monkeypatch.setattr(api, "load_case_search_records", lambda _root: rows)
    api._record_open_tokens.clear()
    return TestClient(api.app)


# ---------------------------------------------------------------------------
# version gate
# ---------------------------------------------------------------------------


def test_v450_version_and_store_package_advance() -> None:
    """Version constants must reflect the current release while retaining v4.5 drill-down behavior."""
    assert VERSION == "5.2.0"
    assert PACKAGE_VERSION == "5.2.0.0"
    assert BUILD_NUMBER == 29
    assert UI_PASS_MARKER == "v5.2.0-answer-first-evidence-security"
    identity = json.loads(
        (Path(__file__).parents[1] / "store" / "msix" / "identity.example.json").read_text(encoding="utf-8")
    )
    assert identity["package_version"] == "5.2.0.0"


# ---------------------------------------------------------------------------
# workbench.js static contract
# ---------------------------------------------------------------------------


def test_v450_workbench_js_has_record_card_controls_and_no_file_urls() -> None:
    """workbench.js must contain all record-card HTML hooks and never emit file://."""
    script = (
        Path(__file__).parents[1]
        / "src" / "maine_family_law_llm" / "ui" / "workbench.js"
    ).read_text(encoding="utf-8")
    # Actions present
    assert "data-open-record" in script
    assert "Inspect page" in script
    assert "Show all matches in this document" in script
    # Token-based API — never a raw filesystem URL
    assert "/api/records/open/" in script
    assert "file://" not in script
    # Dedicated bind function to attach click handlers after DOM insertion
    assert "bindRecordOpenActions" in script


def test_v450_workbench_js_renders_record_groups_section() -> None:
    """renderRecordGroups must emit an article per group with proper ARIA labels."""
    script = (
        Path(__file__).parents[1]
        / "src" / "maine_family_law_llm" / "ui" / "workbench.js"
    ).read_text(encoding="utf-8")
    assert "record-result-card" in script
    assert "record-result-actions" in script
    assert "record-match-details" in script
    assert "renderRecordGroups" in script


# ---------------------------------------------------------------------------
# grouping and deduplication
# ---------------------------------------------------------------------------


def test_v450_group_deduplicates_same_page_and_snippet(tmp_path: Path) -> None:
    """Two identical citations for the same page must collapse to one card row."""
    case_root = tmp_path / "case"
    citations = [
        {
            "source_id": "REC-1-P0002",
            "snippet": "  Matching   words here. ",
            "metadata": {
                "parent_evidence_id": "REC-1",
                "page_number": 2,
                "source_locator": r"C:\private\Order.pdf#page=2",
                "source_type": "pdf_page",
            },
        },
        {
            "source_id": "REC-1-P0002",
            "snippet": "Matching words here.",
            "metadata": {
                "parent_evidence_id": "REC-1",
                "page_number": 2,
                "source_locator": r"C:\private\Order.pdf#page=2",
                "source_type": "pdf_page",
            },
        },
        {
            "source_id": "REC-1-P0003",
            "snippet": "Another matching passage.",
            "metadata": {
                "parent_evidence_id": "REC-1",
                "page_number": 3,
                "source_locator": r"C:\private\Order.pdf#page=3",
                "source_type": "pdf_page",
            },
        },
    ]
    groups = api._group_record_cards(case_root, citations)
    # All three citations belong to REC-1 → one group
    assert len(groups) == 1
    card = groups[0]
    assert card["match_count"] == 2          # two distinct (page, snippet) pairs
    assert sorted(card["pages"]) == [2, 3]
    # Safe filename only — no absolute path
    assert card["basename"] == "Order.pdf"
    assert str(tmp_path) not in str(groups)
    assert "C:\\private" not in str(groups)


def test_v450_group_preserves_distinct_documents(tmp_path: Path) -> None:
    """Citations from two different parent records must produce two cards."""
    case_root = tmp_path / "case"
    citations = [
        {"source_id": "R1-P1", "snippet": "alpha", "metadata": {"parent_evidence_id": "REC-1", "page_number": 1, "source_locator": "REC-1.pdf#page=1", "source_type": "pdf_page"}},
        {"source_id": "R2-P1", "snippet": "beta", "metadata": {"parent_evidence_id": "REC-2", "page_number": 1, "source_locator": "REC-2.pdf#page=1", "source_type": "pdf_page"}},
    ]
    groups = api._group_record_cards(case_root, citations)
    assert len(groups) == 2


# ---------------------------------------------------------------------------
# path redaction
# ---------------------------------------------------------------------------


def test_v450_citation_path_redaction_strips_windows_paths_and_attachments() -> None:
    """Absolute paths must never reach the client."""
    rows = api._redact_citation_paths([
        {
            "source_id": "REC-1",
            "metadata": {
                "source_locator": r"C:\private\archive.zip!nested\record.pdf#page=4",
                "source_path": r"C:\private\archive.zip",
            },
        }
    ])
    meta = rows[0]["metadata"]
    assert meta["source_locator"] == "archive.zip!record.pdf#page=4"
    assert "source_path" not in meta


# ---------------------------------------------------------------------------
# open-record token security
# ---------------------------------------------------------------------------


def test_v450_open_record_token_is_opaque_and_corpus_scoped(monkeypatch, tmp_path: Path) -> None:
    """A valid token opens the file; an unknown token or wrong corpus → 404."""
    case_root = tmp_path / "case"
    row = _staged_row(case_root)
    client = _client_for(monkeypatch, case_root, [row])

    token = api._record_open_token(case_root, "REC-1", "REC-1.pdf#page=1")
    response = client.get(f"/api/records/open/{token}?page=1")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.headers["x-mfl-page"] == "1"
    assert str(case_root) not in response.text

    # Unknown token → 404
    assert client.get("/api/records/open/" + ("0" * 64)).status_code == 404

    # Same token, different corpus → 404
    other_case = tmp_path / "other"
    monkeypatch.setattr(api, "active_case_root", lambda: other_case)
    assert client.get(f"/api/records/open/{token}").status_code == 404


def test_v450_open_record_rejects_missing_file_and_hash_mismatch(monkeypatch, tmp_path: Path) -> None:
    """Missing staged file → 404. Changed bytes → 409."""
    case_root = tmp_path / "case"
    row = _staged_row(case_root)
    client = _client_for(monkeypatch, case_root, [row])
    token = api._record_open_token(case_root, "REC-1", "REC-1.pdf")
    staged = case_root / row["private_copy_relpath"]

    staged.unlink()
    assert client.get(f"/api/records/open/{token}").status_code == 404

    staged.write_bytes(b"tampered")
    assert client.get(f"/api/records/open/{token}").status_code == 409


def test_v450_open_record_rejects_path_traversal(monkeypatch, tmp_path: Path) -> None:
    """A staged relpath with '..' must be rejected without leaking the path."""
    case_root = tmp_path / "case"
    row = _staged_row(case_root)
    row["private_copy_relpath"] = "../../outside.pdf"
    client = _client_for(monkeypatch, case_root, [row])
    token = api._record_open_token(case_root, "REC-1", "REC-1.pdf")
    resp = client.get(f"/api/records/open/{token}")
    assert resp.status_code == 404
    assert "outside.pdf" not in resp.text


def test_v450_open_record_serves_zip_member(monkeypatch, tmp_path: Path) -> None:
    """ZIP member extraction must succeed and not expose the cache path."""
    payload = _pdf_bytes()
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("nested/attachment.pdf", payload)
    case_root = tmp_path / "case"
    row = _staged_row(case_root, data=archive.getvalue(), suffix=".zip")
    client = _client_for(monkeypatch, case_root, [row])
    token = api._record_open_token(case_root, "REC-1", "REC-1.zip!nested/attachment.pdf")
    resp = client.get(f"/api/records/open/{token}?page=1")
    assert resp.status_code == 200
    assert resp.content == payload
    assert str(case_root) not in resp.text


def test_v450_open_record_serves_email_attachment(monkeypatch, tmp_path: Path) -> None:
    """Email attachment extraction must return the embedded PDF bytes."""
    payload = _pdf_bytes()
    msg = EmailMessage()
    msg.set_content("See attachment")
    msg.add_attachment(payload, maintype="application", subtype="pdf", filename="attachment.pdf")
    case_root = tmp_path / "case"
    row = _staged_row(case_root, data=msg.as_bytes(), suffix=".eml")
    client = _client_for(monkeypatch, case_root, [row])
    token = api._record_open_token(case_root, "REC-1", "REC-1.eml!attachment.pdf")
    resp = client.get(f"/api/records/open/{token}")
    assert resp.status_code == 200
    assert resp.content == payload


# ---------------------------------------------------------------------------
# chat payload: no boilerplate, grouped cards for all private-record searches
# ---------------------------------------------------------------------------


def test_v450_active_case_chat_payload_groups_cards_and_no_boilerplate(
    monkeypatch, tmp_path: Path
) -> None:
    """The active-case chat payload must include record_groups and no raw snippet list."""
    case_root = tmp_path / "case"
    row = _staged_row(case_root)
    citations = [
        {
            "source_id": "REC-1-P0002",
            "title": "Order page 2",
            "snippet": "The matching passage.",
            "metadata": {
                "parent_evidence_id": "REC-1",
                "source_locator": "REC-1.pdf#page=2",
                "page_number": 2,
                "source_type": "pdf_page",
            },
        },
        {
            "source_id": "REC-1-P0002",
            "title": "Order page 2",
            "snippet": "The matching passage.",
            "metadata": {
                "parent_evidence_id": "REC-1",
                "source_locator": "REC-1.pdf#page=2",
                "page_number": 2,
                "source_type": "pdf_page",
            },
        },
    ]
    monkeypatch.setattr(api, "active_case_root", lambda: case_root)
    monkeypatch.setattr(api, "load_case_search_records", lambda _root: [row])
    monkeypatch.setattr(api, "describe_case_root", lambda _root: {"label": "Test matter", "indexed_records": 1, "pdf_pages": 1})
    monkeypatch.setattr(api, "answer_case_question", lambda *_args, **_kwargs: {
        "direct_answer": "The matching passage.",
        "citations": citations,
        "evidence_relied_on": [],
        "search_summary": {
            "search_target": "contempt",
            "result_count": 2,
            "document_count": 1,
            "page_count": 1,
        },
    })
    payload = api._active_case_chat_payload(
        api.AskRequest(question="Find all mentions of contempt", search_mode="my_records"),
        finalize=False,
    )
    assert payload is not None
    assert payload["direct_record_search"] is True
    assert "record_groups" in payload
    assert payload["search_summary"]["unique_document_count"] == 1
    assert payload["record_groups"][0]["match_count"] == 1
    # No raw snippet boilerplate
    assert "Relevant record slices:" not in payload["answer"]
    assert "recommended legal action" not in payload["answer"].lower()
