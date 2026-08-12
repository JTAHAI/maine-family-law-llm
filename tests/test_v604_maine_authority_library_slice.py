from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.api.main import app
from app.services import AuthorityLibraryService
from legal.connectors.base import SourceTarget
from legal.connectors.http_fetcher import OfficialSourceFetchError, OfficialSourceFetcher, _OfficialRedirectHandler
from legal.data_boundaries import default_external_data_root, ensure_external_authority_root


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    return path


def test_default_external_authority_root_is_outside_repo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("MAINE_FAMILY_LAW_DATA_ROOT", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))
    root = default_external_data_root(tmp_path / "repo")
    assert root == (tmp_path / "LocalAppData" / "MaineFamilyLawLLM" / "authority-data").resolve()
    with pytest.raises(ValueError, match="outside the source repository"):
        ensure_external_authority_root(tmp_path / "repo" / "authority", project_root=tmp_path / "repo")


def test_authority_library_filters_broad_source_classes_and_exposes_span_preview(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))
    root = default_external_data_root(tmp_path / "repo")
    _write_jsonl(
        root / "parsed_authority_store" / "statutes" / "statutes.jsonl",
        [
            {
                "source_id": "statute-1",
                "source_class": "statute_section",
                "jurisdiction": "maine",
                "source_hash": "a" * 64,
                "freshness_status": "fresh",
                "parser_status": "parsed",
                "source_span": {"start_offset": 0, "end_offset": 12},
                "source_span_preview": "best interest",
                "title": "Best interest",
                "citation": "19-A M.R.S. § 1653",
                "text": "best interest of the child",
                "retrieved_at": "2026-08-06T12:00:00+00:00",
            }
        ],
    )
    _write_jsonl(
        root / "parsed_authority_store" / "forms" / "forms.jsonl",
        [
            {
                "source_id": "form-1",
                "source_class": "court_form",
                "jurisdiction": "maine",
                "source_hash": "b" * 64,
                "freshness_status": "unknown",
                "parser_status": "parsed",
                "title": "Form 1",
                "citation": "FM-001",
                "text": "form body",
                "retrieved_at": "2026-08-06T12:00:00+00:00",
            }
        ],
    )
    service = AuthorityLibraryService(data_root=root)
    statute_results = service.list_sources(source_class="statutes")
    assert statute_results["count"] == 1
    assert statute_results["sources"][0]["source_id"] == "statute-1"
    detail = service.get_source("statute-1")
    assert detail["source_span_preview"] == "best interest"
    assert detail["source_card"]["source_class_group"] == "statutes"


def test_authority_update_requires_network_ack_for_live_mode(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.post(
        "/api/authority/update",
        headers={"X-User-Role": "attorney", "X-Tenant-Id": "tenant-a"},
        json={
            "allow_live": True,
            "network_acknowledged": False,
            "fixture_mode": False,
            "dry_run": False,
        },
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "blocked"
    assert "network_acknowledgement_required" in payload["blockers"]


def test_official_fetcher_blocks_unapproved_redirects_and_oversized_or_mismatched_responses(monkeypatch: pytest.MonkeyPatch) -> None:
    target = SourceTarget(
        target_id="t",
        source_class="court_rules_index",
        jurisdiction="maine",
        url="https://www.courts.maine.gov/rules/index.html",
        parser_name="maine_rules_index",
    )
    handler = _OfficialRedirectHandler()
    with pytest.raises(Exception):
        handler.redirect_request(SourceTarget("t", "court_rules_index", "maine", "https://www.courts.maine.gov/rules/index.html", "maine_rules_index"), None, 302, "Found", {}, "https://example.com/")

    fetcher = OfficialSourceFetcher(strict_content_type=True, max_response_bytes=8)

    class _Response:
        headers = {"Content-Type": "text/html"}
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def geturl(self) -> str:
            return target.url

        def read(self, size: int = -1) -> bytes:
            return b"<html><body>too-long-response-body</body></html>"

    monkeypatch.setattr(fetcher, "_open", lambda request: _Response())
    with pytest.raises(OfficialSourceFetchError) as excinfo:
        fetcher.fetch(target)
    assert excinfo.value.attempts[0].status == "response_too_large"
