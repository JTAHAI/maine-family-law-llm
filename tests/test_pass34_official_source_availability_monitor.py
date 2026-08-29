from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.main import app as canonical_app
from app.api.routes import authority as authority_routes
from app.services.authority_library_service import AuthorityLibraryService
from maine_family_law_llm import api as frozen_api


ROOT = Path(__file__).resolve().parents[1]
HEADERS = {"X-User-Role": "reviewer", "X-Tenant-Id": "tenant-availability"}


def test_pass34_monitor_classifies_stored_metadata_without_network_or_mirror(monkeypatch, tmp_path: Path) -> None:
    authority_root = tmp_path / "external-authority"
    authority_root.mkdir()
    service = AuthorityLibraryService(data_root=authority_root, repo_root=tmp_path / "source")
    rows = [
        {
            "source_id": "moved-statute",
            "source_class": "statute_section",
            "source_url_or_path": "https://legislature.maine.gov/title",
            "metadata": {"final_url": "https://www.mainelegislature.org/title", "status_code": 200},
        },
        {
            "source_id": "changed-rule",
            "source_class": "court_rule",
            "source_url_or_path": "https://www.courts.maine.gov/rules",
            "hash": "b" * 64,
            "metadata": {"previous_sha256": "a" * 64},
        },
        {
            "source_id": "tls-opinion",
            "source_class": "law_court_opinion",
            "source_url_or_path": "https://www.courts.maine.gov/opinions",
            "metadata": {"fetch_metadata": {"failure_code": "tls_certificate_verify_failed"}},
        },
        {
            "source_id": "restricted-form",
            "source_class": "court_form",
            "source_url_or_path": "https://www.courts.maine.gov/forms",
            "metadata": {"status_code": 403, "fetch_metadata": {"robots_policy_result": "disallow"}},
        },
    ]
    monkeypatch.setattr(service, "_source_rows", lambda _root: rows)
    monkeypatch.setattr(
        service,
        "_latest_update_report",
        lambda _root: {
            "generated_at": "2026-08-26T00:00:00Z",
            "changed_since_last_build": {"hash_changed": ["report-hash-change"]},
            "findings": [{"source_id": "report-tls", "code": "tls_handshake_failed"}],
        },
    )
    monkeypatch.setattr(
        "app.services.authority_library_service.AuthorityProductVerifier.verify",
        lambda _self: SimpleNamespace(status="pass", build_id="a" * 24, blockers=[]),
    )

    result = service.availability_monitor()

    assert result["network_used"] is False
    assert result["mirror_substitution"] is False
    assert result["availability_determined"] is False
    assert result["review_required"] is True
    assert [row["source_id"] for row in result["categories"]["moved_urls"]] == ["moved-statute"]
    assert {row["source_id"] for row in result["categories"]["changed_hashes"]} == {"changed-rule", "report-hash-change"}
    assert {row["source_id"] for row in result["categories"]["tls_failures"]} == {"report-tls", "tls-opinion"}
    assert [row["source_id"] for row in result["categories"]["access_restrictions"]] == ["restricted-form"]
    moved = result["categories"]["moved_urls"][0]
    assert moved["expected_official_url"] == "https://legislature.maine.gov/title"
    assert moved["observed_url"] == "https://www.mainelegislature.org/title"


def test_pass34_canonical_route_requires_role_tenant_and_audits(monkeypatch) -> None:
    monkeypatch.setattr(
        authority_routes.AuthorityLibraryService,
        "availability_monitor",
        lambda _self: {
            "status": "needs_review",
            "categories": {"moved_urls": [{"source_id": "fictional-source", "review_required": True}]},
            "blockers": ["official_url_moved_or_redirected_review_required"],
            "review_required": True,
            "availability_determined": False,
            "network_used": False,
            "mirror_substitution": False,
        },
    )
    client = TestClient(canonical_app)

    assert client.get("/api/authority/availability").status_code == 403
    response = client.get("/api/authority/availability", headers=HEADERS)
    assert response.status_code == 200
    assert response.headers["X-MFLL-RBAC"] == "enforced"
    assert response.headers["X-MFLL-Audit-Event-Id"]
    payload = response.json()
    assert payload["review_required"] is True
    assert payload["mirror_substitution"] is False
    assert payload["audit_event"]["action"] == "official_source_availability_monitor"


def test_pass34_frozen_route_and_production_ui_are_registered(monkeypatch) -> None:
    monkeypatch.setattr(
        frozen_api.AuthorityLibraryService,
        "availability_monitor",
        lambda _self: {
            "status": "metadata_observed",
            "categories": {},
            "blockers": [],
            "review_required": True,
            "availability_determined": False,
            "network_used": False,
            "mirror_substitution": False,
        },
    )
    client = TestClient(frozen_api.app)
    response = client.get("/api/authority/availability")
    assert response.status_code == 200
    assert response.json()["network_used"] is False

    frozen_source = (ROOT / "src" / "maine_family_law_llm" / "api.py").read_text(encoding="utf-8")
    source_ui = (ROOT / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_bytes()
    mirrored_ui = (ROOT / "maine_family_law_llm" / "ui" / "workbench.js").read_bytes()
    assert '@app.get("/api/authority/availability")' in frozen_source
    assert b"installAuthorityAvailabilityMonitor" in source_ui
    assert b"/api/authority/availability" in source_ui
    assert b"data-authority-availability-source" in source_ui
    assert b"mirror substitution remain disabled" in source_ui
    assert source_ui == mirrored_ui
