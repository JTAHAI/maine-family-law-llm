from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app as canonical_app
from app.api.routes import authority as authority_routes
from app.services.authority_product_service import AuthorityProductService
from maine_family_law_llm import api as frozen_api


ROOT = Path(__file__).resolve().parents[1]
HEADERS = {"X-User-Role": "reviewer", "X-Tenant-Id": "tenant-form-sync"}


def _catalog() -> dict:
    return {
        "status": "pass",
        "build_id": "a" * 24,
        "forms": [
            {
                "source_id": "form-fm-001",
                "form_id": "FM-001",
                "title": "Fictional Maine family form",
                "citation": "FM-001",
                "freshness_status": "fresh",
                "version_date": "2026-08-01",
                "source_hash": "b" * 64,
                "source_url_or_path": "https://www.courts.maine.gov/forms/FM-001.pdf",
            }
        ],
        "review_required": True,
    }


def test_pass37_matching_installed_metadata_is_catalog_matched_but_review_required(monkeypatch, tmp_path: Path) -> None:
    service = AuthorityProductService(data_root=tmp_path)
    monkeypatch.setattr(service, "list_forms", lambda *, limit: _catalog())

    result = service.synchronize_forms(
        [{"form_id": "fm 001", "version_date": "2026-08-01", "sha256": "b" * 64}]
    )

    assert result["status"] == "synchronized_review_required"
    assert result["authority_build_id"] == "a" * 24
    assert result["completion_blocked"] is False
    assert result["catalog_match_for_completion"] is True
    assert result["review_required"] is True
    assert result["network_used"] is False
    assert result["persistent_state_changed"] is False
    assert result["rows"][0]["status"] == "catalog_match"
    assert result["rows"][0]["official"]["source_id"] == "form-fm-001"


def test_pass37_mismatch_or_stale_catalog_entry_blocks_completion(monkeypatch, tmp_path: Path) -> None:
    service = AuthorityProductService(data_root=tmp_path)
    stale = _catalog()
    stale["forms"][0]["freshness_status"] = "stale"
    monkeypatch.setattr(service, "list_forms", lambda *, limit: stale)

    result = service.synchronize_forms(
        [{"form_id": "FM-001", "version_date": "2025-01-01", "sha256": "c" * 64}]
    )

    assert result["status"] == "completion_blocked"
    assert result["completion_blocked"] is True
    assert "official_form_freshness_not_verified:FM-001" in result["blockers"]
    assert "installed_form_hash_differs_from_active_catalog:FM-001" in result["blockers"]
    assert "installed_form_version_differs_from_active_catalog:FM-001" in result["blockers"]


def test_pass37_conflicting_active_catalog_entries_fail_closed(monkeypatch, tmp_path: Path) -> None:
    service = AuthorityProductService(data_root=tmp_path)
    conflicting = _catalog()
    conflicting["forms"].append(
        {
            **conflicting["forms"][0],
            "source_id": "form-fm-001-revision",
            "version_date": "2026-08-15",
            "source_hash": "d" * 64,
        }
    )
    monkeypatch.setattr(service, "list_forms", lambda *, limit: conflicting)

    result = service.synchronize_forms([{"form_id": "FM-001", "version_date": "2026-08-01"}])

    assert result["status"] == "completion_blocked"
    assert result["rows"][0]["status"] == "active_catalog_metadata_conflict"
    assert "active_catalog_form_metadata_conflict:FM-001" in result["blockers"]


def test_pass37_rejects_form_content_and_invalid_metadata_before_catalog_read(monkeypatch, tmp_path: Path) -> None:
    service = AuthorityProductService(data_root=tmp_path)
    monkeypatch.setattr(service, "list_forms", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("catalog should not be read")))

    result = service.synchronize_forms(
        [{"form_id": "FM-001", "version_date": "2026-08-01", "form_content": "private text"}]
    )

    assert result["status"] == "blocked"
    assert result["completion_blocked"] is True
    assert result["blockers"] == ["installed_form_metadata_field_not_allowed:0"]
    assert result["persistent_state_changed"] is False


def test_pass37_canonical_route_requires_role_tenant_and_audits(monkeypatch) -> None:
    monkeypatch.setattr(
        authority_routes.AuthorityProductService,
        "synchronize_forms",
        lambda _self, installed_forms: {
            "status": "synchronized_review_required",
            "rows": [{"installed": installed_forms[0], "status": "catalog_match", "review_required": True}],
            "completion_blocked": False,
            "review_required": True,
            "network_used": False,
        },
    )
    client = TestClient(canonical_app)
    payload = {"installed_forms": [{"form_id": "FM-001", "version_date": "2026-08-01"}]}

    assert client.post("/api/authority/forms/synchronize", json=payload).status_code == 403
    response = client.post("/api/authority/forms/synchronize", json=payload, headers=HEADERS)

    assert response.status_code == 200
    assert response.headers["X-MFLL-RBAC"] == "enforced"
    assert response.headers["X-MFLL-Audit-Event-Id"]
    assert response.json()["audit_event"]["action"] == "authority_form_catalog_synchronization"


def test_pass37_frozen_route_and_production_ui_are_registered(monkeypatch) -> None:
    monkeypatch.setattr(
        frozen_api.AuthorityProductService,
        "synchronize_forms",
        lambda _self, installed_forms: {
            "status": "synchronized_review_required",
            "rows": [{"installed": installed_forms[0], "status": "catalog_match", "review_required": True}],
            "completion_blocked": False,
            "review_required": True,
            "network_used": False,
        },
    )
    response = TestClient(frozen_api.app).post(
        "/api/authority/forms/synchronize",
        json={"installed_forms": [{"form_id": "FM-001", "version_date": "2026-08-01"}]},
    )

    assert response.status_code == 200
    assert response.json()["rows"][0]["status"] == "catalog_match"
    frozen_source = (ROOT / "src" / "maine_family_law_llm" / "api.py").read_text(encoding="utf-8")
    source_ui = (ROOT / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_bytes()
    mirrored_ui = (ROOT / "maine_family_law_llm" / "ui" / "workbench.js").read_bytes()
    assert '@app.post("/api/authority/forms/synchronize")' in frozen_source
    assert b"installAuthorityFormSynchronizer" in source_ui
    assert b"/api/authority/forms/synchronize" in source_ui
    assert b"data-authority-form-sync-source" in source_ui
    assert b"Form contents are never read or sent" in source_ui
    assert source_ui == mirrored_ui
