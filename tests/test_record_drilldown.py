import hashlib
import io
import zipfile
from email.message import EmailMessage
from pathlib import Path

from fastapi.testclient import TestClient
from pypdf import PdfWriter

from maine_family_law_llm import api


def _pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=144, height=144)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _staged_row(case_root: Path, *, evidence_id: str = "REC-1", data: bytes | None = None, suffix: str = ".pdf") -> dict:
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


def test_record_groups_dedupe_pages_and_never_return_paths(tmp_path: Path) -> None:
    case_root = tmp_path / "case"
    citations = [
        {"source_id": "REC-1-P0002", "snippet": "  Matching   words here. ", "metadata": {"parent_evidence_id": "REC-1", "page_number": 2, "source_locator": r"C:\private\Order.pdf#page=2", "source_type": "pdf_page"}},
        {"source_id": "REC-1-P0002", "snippet": "Matching words here.", "metadata": {"parent_evidence_id": "REC-1", "page_number": 2, "source_locator": r"C:\private\Order.pdf#page=2", "source_type": "pdf_page"}},
        {"source_id": "REC-1-P0003", "snippet": "Another matching passage.", "metadata": {"parent_evidence_id": "REC-1", "page_number": 3, "source_locator": r"C:\private\Order.pdf#page=3", "source_type": "pdf_page"}},
    ]
    groups = api._group_record_cards(case_root, citations)
    assert len(groups) == 1
    assert groups[0]["match_count"] == 2
    assert groups[0]["pages"] == [2, 3]
    assert groups[0]["basename"] == "Order.pdf"
    assert str(tmp_path) not in str(groups)
    assert "C:\\private" not in str(groups)


def test_public_citations_redact_windows_and_attachment_paths() -> None:
    rows = api._redact_citation_paths([
        {"source_id": "REC-1", "metadata": {"source_locator": r"C:\private\archive.zip!nested\record.pdf#page=4", "source_path": r"C:\private\archive.zip"}}
    ])
    metadata = rows[0]["metadata"]
    assert metadata["source_locator"] == "archive.zip!record.pdf#page=4"
    assert "source_path" not in metadata


def test_open_record_is_opaque_hash_checked_and_scoped(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "case"
    row = _staged_row(case_root)
    client = _client_for(monkeypatch, case_root, [row])
    token = api._record_open_token(case_root, "REC-1", "REC-1.pdf#page=1")
    opened = client.get(f"/api/records/open/{token}?page=1")
    assert opened.status_code == 200
    assert opened.headers["content-type"].startswith("application/pdf")
    assert opened.headers["x-mfl-page"] == "1"
    assert str(case_root) not in opened.text
    assert client.get("/api/records/open/" + ("0" * 64)).status_code == 404
    other_case = tmp_path / "other"
    monkeypatch.setattr(api, "active_case_root", lambda: other_case)
    assert client.get(f"/api/records/open/{token}").status_code == 404


def test_open_record_fails_closed_for_missing_staged_file_and_hash_mismatch(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "case"
    row = _staged_row(case_root)
    client = _client_for(monkeypatch, case_root, [row])
    token = api._record_open_token(case_root, "REC-1", "REC-1.pdf")
    staged = case_root / row["private_copy_relpath"]
    staged.unlink()
    missing = client.get(f"/api/records/open/{token}")
    assert missing.status_code == 404
    assert str(case_root) not in missing.text
    staged.write_bytes(b"changed")
    mismatch = client.get(f"/api/records/open/{token}")
    assert mismatch.status_code == 409


def test_open_record_rejects_traversal_in_staged_location(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "case"
    row = _staged_row(case_root)
    row["private_copy_relpath"] = "../../outside.pdf"
    client = _client_for(monkeypatch, case_root, [row])
    token = api._record_open_token(case_root, "REC-1", "REC-1.pdf")
    response = client.get(f"/api/records/open/{token}")
    assert response.status_code == 404
    assert "outside.pdf" not in response.text


def test_open_record_serves_zip_member_without_exposing_cache_path(monkeypatch, tmp_path: Path) -> None:
    payload = _pdf_bytes()
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("nested/attachment.pdf", payload)
    case_root = tmp_path / "case"
    row = _staged_row(case_root, data=archive.getvalue(), suffix=".zip")
    client = _client_for(monkeypatch, case_root, [row])
    token = api._record_open_token(case_root, "REC-1", "REC-1.zip!nested/attachment.pdf")
    opened = client.get(f"/api/records/open/{token}?page=1")
    assert opened.status_code == 200
    assert opened.content == payload
    assert str(case_root) not in opened.text


def test_open_record_serves_email_attachment(monkeypatch, tmp_path: Path) -> None:
    payload = _pdf_bytes()
    message = EmailMessage()
    message.set_content("See attachment")
    message.add_attachment(payload, maintype="application", subtype="pdf", filename="attachment.pdf")
    case_root = tmp_path / "case"
    row = _staged_row(case_root, data=message.as_bytes(), suffix=".eml")
    client = _client_for(monkeypatch, case_root, [row])
    token = api._record_open_token(case_root, "REC-1", "REC-1.eml!attachment.pdf")
    opened = client.get(f"/api/records/open/{token}")
    assert opened.status_code == 200
    assert opened.content == payload


def test_workbench_uses_opaque_open_controls_and_no_file_urls() -> None:
    script = (Path(__file__).parents[1] / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_text(encoding="utf-8")
    assert "data-open-record" in script
    assert "Open at page" in script
    assert "Show all matches in this document" in script
    assert "/api/records/open/" in script
    assert "file://" not in script


def test_records_only_response_is_grouped_and_not_legal_boilerplate(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "case"
    row = _staged_row(case_root)
    citations = [
        {"source_id": "REC-1-P0002", "title": "Order page 2", "snippet": "The matching passage.", "metadata": {"parent_evidence_id": "REC-1", "source_locator": "REC-1.pdf#page=2", "page_number": 2, "source_type": "pdf_page"}},
        {"source_id": "REC-1-P0002", "title": "Order page 2", "snippet": "The matching passage.", "metadata": {"parent_evidence_id": "REC-1", "source_locator": "REC-1.pdf#page=2", "page_number": 2, "source_type": "pdf_page"}},
    ]
    monkeypatch.setattr(api, "active_case_root", lambda: case_root)
    monkeypatch.setattr(api, "load_case_search_records", lambda _root: [row])
    monkeypatch.setattr(api, "describe_case_root", lambda _root: {"label": "Test matter", "indexed_records": 1, "pdf_pages": 1})
    monkeypatch.setattr(api, "answer_case_question", lambda *_args, **_kwargs: {
        "direct_answer": "The matching passage.", "citations": citations,
        "evidence_relied_on": [], "search_summary": {"search_target": "contempt", "result_count": 2, "document_count": 1, "page_count": 1},
    })
    payload = api._active_case_chat_payload(api.AskRequest(question="Find all mentions of contempt", search_mode="my_records"), finalize=False)
    assert payload is not None
    assert payload["direct_record_search"] is True
    assert payload["search_summary"]["unique_document_count"] == 1
    assert payload["record_groups"][0]["match_count"] == 1
    assert "recommended legal action" not in payload["answer"].lower()
