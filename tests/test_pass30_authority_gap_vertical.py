from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.main import app as canonical_app
from app.api.routes import authority as authority_routes
from app.services import authority_product_service
from maine_family_law_llm import api as desktop_api

ROOT = Path(__file__).resolve().parents[1]
HEADERS = {"X-User-Role": "reviewer", "X-Tenant-Id": "tenant-authority-gap"}


def test_pass30_canonical_route_requires_scoped_role_and_emits_audit(monkeypatch) -> None:
    def _review(_self, *, issue: str = "") -> dict:
        return {
            "status": "needs_review",
            "issue": issue,
            "record_count": 4,
            "source_class_counts": {
                "statute_section": 1,
                "court_rule": 1,
                "opinion": 1,
                "court_form": 1,
            },
            "freshness_counts": {"fresh": 4},
            "missing_material_source_classes": [],
            "blockers": [],
            "review_required": True,
            "completeness_determined": False,
        }

    monkeypatch.setattr(authority_routes.AuthorityProductService, "authority_gap_review", _review)
    client = TestClient(canonical_app)

    denied = client.get("/api/authority/gaps")
    assert denied.status_code == 403

    response = client.get("/api/authority/gaps?issue=parental%20rights", headers=HEADERS)
    assert response.status_code == 200
    assert response.headers["X-MFLL-RBAC"] == "enforced"
    assert response.headers["X-MFLL-Audit-Event-Id"]
    payload = response.json()
    assert payload["issue"] == "parental rights"
    assert payload["review_required"] is True
    assert payload["completeness_determined"] is False
    assert payload["audit_event"]["action"] == "authority_gap_review"


def test_pass30_real_service_propagates_unknown_metadata_blockers_to_both_api_hosts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    rows = [
        {"source_class": name, "freshness_status": "fresh", "text": "fictional-text-not-for-output"}
        for name in ("statute_section", "court_rule", "opinion", "court_form")
    ]
    rows[0]["freshness_status"] = "parser_failed"
    rows.append({"source_class": "not_statute_rule_opinion_form", "freshness_status": "fresh"})
    monkeypatch.setattr(
        authority_product_service.AuthorityProductService,
        "_active_product",
        lambda _self, **_kwargs: SimpleNamespace(
            data_root=tmp_path, build_id="fictional-gap-build"
        ),
    )
    monkeypatch.setattr(
        authority_product_service.AuthorityProductService, "_authority_gap_rows", lambda _self, _active: iter(rows)
    )

    canonical = TestClient(canonical_app)
    assert (
        canonical.get("/api/authority/gaps", headers={"X-User-Role": "reviewer"}).status_code == 403
    )
    assert (
        canonical.get(
            "/api/authority/gaps",
            headers={**HEADERS, "X-User-Role": "visitor"},
        ).status_code
        == 403
    )
    for app in (canonical_app, desktop_api.app):
        response = TestClient(app).get(
            "/api/authority/gaps", params={"issue": "Fictional review"}, headers=HEADERS
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "needs_review"
        assert set(payload["blockers"]) == {
            "freshness_review_required",
            "source_class_review_required",
        }
        assert payload["record_count"] == 5
        assert payload["build_id"] == "fictional-gap-build"
        assert payload["issue_filter_applied"] is False
        assert payload["current_law_determined"] is False
        assert payload["review_required"] is True
        assert "fictional-text-not-for-output" not in response.text
        assert str(tmp_path) not in response.text
        if app is canonical_app:
            assert payload["audit_event"]["action"] == "authority_gap_review"

        pairs = [
            (route.path, method)
            for route in app.routes
            for method in getattr(route, "methods", [])
            if route.path == "/api/authority/gaps"
        ]
        assert pairs == [("/api/authority/gaps", "GET")]


def test_pass30_frozen_runtime_and_production_ui_expose_the_review_path() -> None:
    frozen_api = (ROOT / "src" / "maine_family_law_llm" / "api.py").read_text(encoding="utf-8")
    source_ui = (ROOT / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_bytes()
    mirrored_ui = (ROOT / "maine_family_law_llm" / "ui" / "workbench.js").read_bytes()

    assert '@app.get("/api/authority/gaps")' in frozen_api
    assert b"installAuthorityGapControl" in source_ui
    assert b"/api/authority/gaps?issue=" in source_ui
    assert b"Review active corpus" in source_ui
    assert b"Browse admitted sources" in source_ui
    assert b"Review required." in source_ui
    assert b"optional; does not filter sources" in source_ui
    assert b"Scope: all active corpus metadata" in source_ui
    assert b"button.addEventListener('mousedown', activateDrawerTab);" in source_ui
    assert b"button.addEventListener('pointerup', activateDrawerTab);" in source_ui
    assert b"button.addEventListener('click', activateDrawerTab);" in source_ui
    assert b"querySelectorAll('[data-v8-view]')" not in source_ui
    assert source_ui.count(b"querySelectorAll('button[data-v8-view]')") == 2
    assert b"/api/authority/gaps/sources/" in source_ui
    assert b"authority_gap_build_id" in source_ui
    assert b"Coverage-build source:" in source_ui
    assert b"if (!pin && (sourcePreviewPinned || Date.now() < sourcePreviewSuppressUntil)) return;" in source_ui
    assert source_ui == mirrored_ui
