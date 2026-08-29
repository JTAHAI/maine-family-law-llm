from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.main import app as canonical_app
from app.api.routes import authority as authority_routes
from app.services.authority_library_service import AuthorityLibraryService
from maine_family_law_llm import api as frozen_api


ROOT = Path(__file__).resolve().parents[1]
HEADERS = {"X-User-Role": "reviewer", "X-Tenant-Id": "tenant-freshness"}


def test_pass33_dashboard_reports_thresholds_overdue_dates_and_parser_failures(monkeypatch, tmp_path: Path) -> None:
    authority_root = tmp_path / "external-authority"
    authority_root.mkdir()
    service = AuthorityLibraryService(data_root=authority_root, repo_root=tmp_path / "source")
    rows = [
        {
            "source_id": "statute-current",
            "source_class": "statute_section",
            "freshness_status": "fresh",
            "retrieved_at": "2026-08-20T00:00:00Z",
            "parser_status": "parsed",
        },
        {
            "source_id": "form-overdue",
            "source_class": "court_form",
            "freshness_status": "fresh",
            "retrieved_at": "2026-06-01T00:00:00Z",
            "parser_status": "parsed",
        },
        {
            "source_id": "rule-date-unknown",
            "source_class": "court_rule",
            "freshness_status": "unknown",
            "retrieved_at": "not-a-timestamp",
            "parser_status": "parsed",
        },
        {
            "source_id": "opinion-parser-failed",
            "source_class": "law_court_opinion",
            "freshness_status": "parser_failed",
            "retrieved_at": "2026-08-19T00:00:00Z",
            "parser_status": "failed",
        },
    ]
    monkeypatch.setattr(service, "_source_rows", lambda _root: rows)
    monkeypatch.setattr(service, "_latest_update_report", lambda _root: {"status": "pass", "generated_at": "2026-08-20T00:00:00Z"})
    monkeypatch.setattr(
        "app.services.authority_library_service.AuthorityProductVerifier.verify",
        lambda _self: SimpleNamespace(status="pass", build_id="a" * 24, blockers=[]),
    )

    result = service.freshness_dashboard(now=datetime(2026, 8, 26, tzinfo=UTC))

    assert result["review_required"] is True
    assert result["current_law_determined"] is False
    assert result["network_used"] is False
    assert result["last_accepted_build"]["verified"] is True
    assert result["source_class_thresholds"]["forms"]["threshold_days"] == 30
    assert [row["source_id"] for row in result["overdue_sources"]] == ["form-overdue"]
    assert [row["source_id"] for row in result["parser_failures"]] == ["opinion-parser-failed"]
    assert [row["source_id"] for row in result["retrieval_date_unknown_sources"]] == ["rule-date-unknown"]
    assert "authority_parser_failures_require_review" in result["blockers"]
    assert "authority_retrieval_dates_missing_or_invalid" in result["blockers"]


def test_pass33_canonical_freshness_route_requires_role_tenant_and_audits(monkeypatch) -> None:
    monkeypatch.setattr(
        authority_routes.AuthorityLibraryService,
        "freshness_dashboard",
        lambda _self: {
            "status": "needs_review",
            "last_accepted_build": {"build_id": "a" * 24, "verified": True},
            "overdue_sources": [{"source_id": "fictional-overdue", "review_required": True}],
            "parser_failures": [],
            "retrieval_date_unknown_sources": [],
            "blockers": ["operational_source_freshness_review_required"],
            "review_required": True,
            "current_law_determined": False,
            "network_used": False,
        },
    )
    client = TestClient(canonical_app)

    assert client.get("/api/authority/freshness").status_code == 403
    response = client.get("/api/authority/freshness", headers=HEADERS)
    assert response.status_code == 200
    assert response.headers["X-MFLL-RBAC"] == "enforced"
    assert response.headers["X-MFLL-Audit-Event-Id"]
    payload = response.json()
    assert payload["review_required"] is True
    assert payload["current_law_determined"] is False
    assert payload["audit_event"]["action"] == "authority_freshness_dashboard"


def test_pass33_frozen_route_and_production_ui_are_registered(monkeypatch) -> None:
    monkeypatch.setattr(
        frozen_api.AuthorityLibraryService,
        "freshness_dashboard",
        lambda _self: {
            "status": "needs_review",
            "overdue_sources": [],
            "parser_failures": [],
            "retrieval_date_unknown_sources": [],
            "blockers": [],
            "review_required": True,
            "current_law_determined": False,
            "network_used": False,
        },
    )
    client = TestClient(frozen_api.app)
    response = client.get("/api/authority/freshness")
    assert response.status_code == 200
    assert response.json()["review_required"] is True

    frozen_source = (ROOT / "src" / "maine_family_law_llm" / "api.py").read_text(encoding="utf-8")
    source_ui = (ROOT / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_bytes()
    mirrored_ui = (ROOT / "maine_family_law_llm" / "ui" / "workbench.js").read_bytes()
    assert '@app.get("/api/authority/freshness")' in frozen_source
    assert b"installAuthorityFreshnessDashboard" in source_ui
    assert b"/api/authority/freshness" in source_ui
    assert b"data-authority-freshness-source" in source_ui
    assert b"Review required." in source_ui
    assert source_ui == mirrored_ui
