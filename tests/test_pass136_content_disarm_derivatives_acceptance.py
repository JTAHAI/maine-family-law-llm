from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from legal.document_intelligence.service import DocumentIntelligenceError, create_content_disarm_copy
from maine_family_law_llm import api
from maine_family_law_llm.local_workbench_ui import read_workbench_asset, render_local_workbench_html


def _row(case_root: Path, record_id: str, text: str) -> dict[str, str]:
    source = case_root / "02_PRIVATE_FORENSIC_MASTER" / "files" / f"{record_id}.html"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(text, encoding="utf-8")
    return {
        "evidence_id": record_id,
        "private_copy_relpath": source.relative_to(case_root).as_posix(),
        "source_hash": hashlib.sha256(source.read_bytes()).hexdigest(),
        "source_type": "html",
        "source_locator": source.name,
        "parser_status": "parsed",
        "text_status": "available",
    }


def _client(monkeypatch: pytest.MonkeyPatch, case_root: Path, rows: list[dict[str, str]]) -> TestClient:
    monkeypatch.setattr(api, "active_case_root", lambda: case_root)
    monkeypatch.setattr(api, "load_case_search_records", lambda _root: rows)
    api._record_open_tokens.clear()
    api._document_intelligence_artifacts.clear()
    return TestClient(api.app)


def test_pass136_safe_review_copy_is_inert_hash_bound_and_preserves_original(tmp_path: Path) -> None:
    case_root = tmp_path / "fictional-matter"
    case_root.mkdir()
    source = case_root / "risky.html"
    source.write_text(
        "<h1>Fictional notice</h1><script>fetch('https://example.test/private')</script>"
        "<iframe src='https://example.test'></iframe><p>Read the verified record.</p>",
        encoding="utf-8",
    )
    before = source.read_bytes()

    result = create_content_disarm_copy(case_root=case_root, source_path=source, approved=True)

    copy = case_root / result["artifacts"]["safe_review_copy"]["relative_path"]
    receipt = case_root / result["artifacts"]["receipt"]["relative_path"]
    output = copy.read_text(encoding="utf-8")
    assert source.read_bytes() == before
    assert result["original_modified"] is False
    assert result["review_required"] is True
    assert "<script" not in output.lower()
    assert "fetch(" not in output.lower()
    assert "Fictional notice" in output
    assert result["disarm"]["active_content_executed"] is False
    assert result["disarm"]["external_resources_loaded"] is False
    assert "active_or_nonreview_markup_removed" in result["warnings"]
    assert hashlib.sha256(copy.read_bytes()).hexdigest() == result["output_sha256"]
    stored = json.loads(receipt.read_text(encoding="utf-8"))
    assert stored["artifact_type"] == "content_disarm_safe_review_copy"
    assert stored["source_sha256"] == hashlib.sha256(before).hexdigest()


def test_pass136_requires_explicit_approval_and_rejects_unsafe_output_path(tmp_path: Path) -> None:
    case_root = tmp_path / "fictional-matter"
    case_root.mkdir()
    source = case_root / "record.txt"
    source.write_text("Fictional private record", encoding="utf-8")
    with pytest.raises(DocumentIntelligenceError) as exc:
        create_content_disarm_copy(case_root=case_root, source_path=source, approved=False)
    assert exc.value.code == "content_disarm_consent_required"


def test_pass136_api_is_matter_scoped_capability_bound_and_receipt_drilldown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    case_root = tmp_path / "fictional-matter"
    case_root.mkdir()
    first = _row(case_root, "REC-ONE", "<p>Fictional first record.</p>")
    second = _row(case_root, "REC-TWO", "<p>Fictional second record.</p>")
    client = _client(monkeypatch, case_root, [first, second])
    first_token = api._record_open_token(case_root, "REC-ONE", "REC-ONE.html")
    second_token = api._record_open_token(case_root, "REC-TWO", "REC-TWO.html")

    denied = client.post(
        "/api/records/REC-ONE/safe-review-copy",
        json={"source_token": first_token, "approved": False},
    )
    assert denied.status_code == 409
    mismatch = client.post(
        "/api/records/REC-ONE/safe-review-copy",
        json={"source_token": second_token, "approved": True},
    )
    assert mismatch.status_code == 403

    response = client.post(
        "/api/records/REC-ONE/safe-review-copy",
        json={"source_token": first_token, "approved": True, "reviewer": "fictional-reviewer"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["record_id"] == "REC-ONE"
    assert payload["local_only"] is True
    assert payload["review_required"] is True
    assert str(case_root) not in json.dumps(payload)
    artifact = payload["artifacts"]["safe_review_copy"]
    downloaded = client.get(artifact["download_url"])
    assert downloaded.status_code == 200
    assert downloaded.headers["x-mfl-hash-verified"] == "true"
    receipt = client.get(payload["artifacts"]["receipt"]["receipt_url"])
    assert receipt.status_code == 200
    assert receipt.json()["source_sha256"] == payload["source_sha256"]
    assert receipt.json()["review_required"] is True


def test_pass136_production_ui_exposes_approved_safe_review_action() -> None:
    html = render_local_workbench_html()
    js = read_workbench_asset("workbench.js")
    assert "safe-review-copy" in js
    assert "function runDocumentIntelligenceSafeReviewCopy" in js
    assert "/safe-review-copy" in js
    assert "inert plain-text review copy" in js
    assert "document-intelligence-modal" in html
