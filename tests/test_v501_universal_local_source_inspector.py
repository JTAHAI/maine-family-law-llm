"""v5.0.1 universal local source inspection and secure-open regression coverage."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from email.message import EmailMessage
from pathlib import Path

from fastapi.testclient import TestClient
from pypdf import PdfWriter

from maine_family_law_llm import api
from maine_family_law_llm.local_workbench_ui import read_workbench_asset, render_local_workbench_html
from maine_family_law_llm.version import BUILD_NUMBER, PACKAGE_VERSION, UI_PASS_MARKER, UI_VERSION, VERSION


def _pdf_bytes(pages: int = 2) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=144, height=144)
    stream = io.BytesIO()
    writer.write(stream)
    return stream.getvalue()


def _row(case_root: Path, *, evidence_id: str, data: bytes, suffix: str, extra: dict | None = None) -> dict:
    staged = case_root / "02_PRIVATE_FORENSIC_MASTER" / "files" / f"{evidence_id}{suffix}"
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_bytes(data)
    row = {
        "evidence_id": evidence_id,
        "private_copy_relpath": staged.relative_to(case_root).as_posix(),
        "source_hash": hashlib.sha256(data).hexdigest(),
        "source_type": suffix.lstrip("."),
        "source_locator": staged.name,
        "parser_status": "parsed",
        "text_status": "available",
    }
    row.update(extra or {})
    return row


def _client(monkeypatch, case_root: Path, rows: list[dict]) -> TestClient:
    monkeypatch.setattr(api, "active_case_root", lambda: case_root)
    monkeypatch.setattr(api, "load_case_search_records", lambda _root: rows)
    api._record_open_tokens.clear()
    return TestClient(api.app)


def test_v501_release_identity() -> None:
    assert VERSION == "5.2.0"
    assert PACKAGE_VERSION == "5.2.0.0"
    assert BUILD_NUMBER == 29
    assert UI_PASS_MARKER == "v5.2.0-answer-first-evidence-security"
    assert UI_VERSION == "5.2.0-answer-first-evidence-security-b29"
    identity = json.loads((Path(__file__).parents[1] / "store/msix/identity.example.json").read_text())
    assert identity["package_version"] == "5.2.0.0"


def test_v501_ui_contains_universal_inspector_and_responsive_controls() -> None:
    html = render_local_workbench_html()
    for marker in (
        'id="record-inspector"',
        'id="record-inspector-viewer"',
        'id="record-inspector-details"',
        'id="record-inspector-page-controls"',
        'id="record-inspector-zoom-controls"',
        'id="record-inspector-open-original"',
        'id="record-inspector-download"',
    ):
        assert marker in html
    js = read_workbench_asset("workbench.js")
    for marker in (
        "function openRecordInspector(binding, page = 0, owner = null)",
        "function openRecordOriginal(binding, page = 0",
        "/api/records/inspect/",
        "emailViewerMarkup",
        "archiveViewerMarkup",
        "tableViewerMarkup",
        "data-inspect-nested-record",
        "Download verified copy",
    ):
        assert marker in js
    assert "file://" not in js.lower()
    css = read_workbench_asset("workbench.css")
    assert ".record-inspector" in css
    assert "resize: both" in css
    assert "@media (max-width: 900px)" in css
    assert ".record-inspector-viewer" in css


def test_v501_tokens_are_random_active_corpus_capabilities(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "case"
    row = _row(case_root, evidence_id="REC-1", data=b"hello", suffix=".txt")
    client = _client(monkeypatch, case_root, [row])
    first = api._record_open_token(case_root, "REC-1", "REC-1.txt")
    second = api._record_open_token(case_root, "REC-1", "REC-1.txt")
    assert first != second
    assert len(first) == len(second) == 64
    assert client.get(f"/api/records/inspect/{first}").status_code == 200
    other = tmp_path / "other"
    monkeypatch.setattr(api, "active_case_root", lambda: other)
    assert client.get(f"/api/records/inspect/{first}").status_code == 404


def test_v501_pdf_inspector_and_open_page(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "case"
    data = _pdf_bytes(2)
    root = _row(case_root, evidence_id="PDF-1", data=data, suffix=".pdf", extra={"page_count": 2})
    page = {
        "evidence_id": "PDF-1-P0002",
        "parent_evidence_id": "PDF-1",
        "source_locator": "PDF-1.pdf#page=2",
        "source_type": "pdf_page",
        "page_number": 2,
        "text_content": "Matching page two text.",
    }
    client = _client(monkeypatch, case_root, [root, page])
    token = api._record_open_token(case_root, "PDF-1", "PDF-1.pdf#page=2")
    inspected = client.get(f"/api/records/inspect/{token}?page=2")
    assert inspected.status_code == 200
    payload = inspected.json()
    assert payload["viewer_kind"] == "pdf"
    assert payload["page"] == 2
    assert payload["page_count"] == 2
    assert payload["preview"]["page_text"] == "Matching page two text."
    assert str(case_root) not in json.dumps(payload)
    opened = client.get(f"/api/records/open/{token}?page=2")
    assert opened.status_code == 200
    assert opened.headers["x-mfl-page"] == "2"
    assert opened.headers["x-mfl-hash-verified"] == "true"
    assert opened.headers["content-type"].startswith("application/pdf")


def test_v501_email_body_and_attachment_drilldown(monkeypatch, tmp_path: Path) -> None:
    attachment = _pdf_bytes(1)
    message = EmailMessage()
    message["From"] = "parent@example.test"
    message["To"] = "other@example.test"
    message["Subject"] = "Parenting schedule"
    message.set_content("Please review the attached schedule and proposed exchange times.")
    message.add_attachment(attachment, maintype="application", subtype="pdf", filename="schedule.pdf")
    case_root = tmp_path / "case"
    root = _row(case_root, evidence_id="MAIL-1", data=message.as_bytes(), suffix=".eml")
    client = _client(monkeypatch, case_root, [root])
    token = api._record_open_token(case_root, "MAIL-1", "MAIL-1.eml")
    payload = client.get(f"/api/records/inspect/{token}").json()
    assert payload["viewer_kind"] == "email"
    assert payload["preview"]["headers"]["Subject"] == "Parenting schedule"
    assert "attached schedule" in payload["preview"]["body"]
    attachments = payload["preview"]["attachments"]
    assert attachments[0]["filename"] == "schedule.pdf"
    nested = client.get(f"/api/records/inspect/{attachments[0]['source_token']}")
    assert nested.status_code == 200
    assert nested.json()["viewer_kind"] == "pdf"
    opened = client.get(f"/api/records/open/{attachments[0]['source_token']}")
    assert opened.content == attachment


def test_v501_text_table_archive_and_active_content_safety(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "case"
    text = _row(case_root, evidence_id="TXT-1", data=b"first line\nsecond line", suffix=".txt")
    table_stream = io.StringIO()
    writer = csv.writer(table_stream)
    writer.writerow(["Date", "Event"])
    writer.writerow(["2026-01-01", "Exchange"])
    table = _row(case_root, evidence_id="CSV-1", data=table_stream.getvalue().encode(), suffix=".csv")
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w") as archive:
        archive.writestr("notes/readme.txt", "archive text")
        archive.writestr("images/photo.jpg", b"jpeg-placeholder")
    archive = _row(case_root, evidence_id="ZIP-1", data=archive_bytes.getvalue(), suffix=".zip")
    html = _row(case_root, evidence_id="HTML-1", data=b"<script>alert(1)</script><p>safe words</p>", suffix=".html")
    rows = [text, table, archive, html]
    client = _client(monkeypatch, case_root, rows)

    text_payload = client.get(f"/api/records/inspect/{api._record_open_token(case_root, 'TXT-1', 'TXT-1.txt')}").json()
    assert text_payload["viewer_kind"] == "text"
    assert "second line" in text_payload["preview"]["text"]

    table_payload = client.get(f"/api/records/inspect/{api._record_open_token(case_root, 'CSV-1', 'CSV-1.csv')}").json()
    assert table_payload["viewer_kind"] == "table"
    assert table_payload["preview"]["rows"][1][1] == "Exchange"

    archive_payload = client.get(f"/api/records/inspect/{api._record_open_token(case_root, 'ZIP-1', 'ZIP-1.zip')}").json()
    assert archive_payload["viewer_kind"] == "archive"
    assert archive_payload["preview"]["member_count"] == 2
    nested_token = archive_payload["preview"]["members"][0]["source_token"]
    assert client.get(f"/api/records/inspect/{nested_token}").status_code == 200

    html_token = api._record_open_token(case_root, "HTML-1", "HTML-1.html")
    html_payload = client.get(f"/api/records/inspect/{html_token}").json()
    assert html_payload["viewer_kind"] == "text"
    assert "safe words" in html_payload["preview"]["text"]
    opened = client.get(f"/api/records/open/{html_token}")
    assert opened.headers["content-type"].startswith("text/plain")
    assert "attachment" in opened.headers["content-disposition"].lower()
    assert "sandbox" in opened.headers["content-security-policy"]


def test_v501_citations_receive_direct_inspection_capabilities(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "case"
    root = _row(case_root, evidence_id="REC-1", data=b"record", suffix=".txt")
    monkeypatch.setattr(api, "load_case_search_records", lambda _root: [root])
    citations = api._attach_record_open_capabilities(case_root, [{
        "source_id": "REC-1-P1",
        "title": "Record page",
        "metadata": {
            "parent_evidence_id": "REC-1",
            "source_locator": "REC-1.txt",
            "page_number": 1,
            "source_lane": "private_record",
        },
    }])
    meta = citations[0]["metadata"]
    assert len(meta["record_open_token"]) == 64
    assert meta["record_open_page"] == 1
    assert meta["record_inspection_available"] is True
    assert str(case_root) not in json.dumps(citations)
