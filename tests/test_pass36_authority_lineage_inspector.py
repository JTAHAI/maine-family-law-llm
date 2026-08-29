from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.main import app as canonical_app
from app.api.routes import authority as authority_routes
from app.services.authority_product_service import ActiveAuthorityProduct, AuthorityProductService
from maine_family_law_llm import api as frozen_api


ROOT = Path(__file__).resolve().parents[1]
HEADERS = {"X-User-Role": "reviewer", "X-Tenant-Id": "tenant-lineage"}


def _active_product(tmp_path: Path, *, source_hash: str = "a" * 64) -> ActiveAuthorityProduct:
    manifest_path = tmp_path / "authority_product_manifest.json"
    manifest = {
        "schema_version": "1.1",
        "build_id": "b" * 24,
        "build_fingerprint": "c" * 64,
        "data_root_policy": "external_only",
        "source_snapshots": [
            {
                "source_id": "maine-title-19a",
                "relative_path": "authority_product/builds/b/sources/000001.html",
                "sha256": source_hash,
                "size": 49,
            }
        ],
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return ActiveAuthorityProduct(
        data_root=tmp_path,
        build_id="b" * 24,
        manifest_path=manifest_path,
        manifest=manifest,
    )


def _parsed_row(*, source_hash: str = "a" * 64) -> dict:
    return {
        "record_id": "statute-19a-1653",
        "source_id": "maine-title-19a",
        "source_hash": source_hash,
        "source_class": "statute_section",
        "authority_kind": "statute_section",
        "jurisdiction": "maine",
        "citation": "19-A M.R.S. § 1653",
        "parser_status": "parsed",
        "source_span": {"start_offset": 10, "end_offset": 44},
        "source_url_or_path": "https://legislature.maine.gov/statutes/19-a/",
        "retrieved_at": "2026-08-26T00:00:00+00:00",
        "parser_audit": {"status": "parsed", "parser_name": "fixture", "parser_version": "v1"},
        "metadata": {
            "target_id": "title-19a",
            "status_code": 200,
            "final_url": "https://legislature.maine.gov/statutes/19-a/",
            "fetch_metadata": {"attempt_count": 1, "robots_policy_result": "checked"},
        },
        "_parsed_relative_path": "statutes/statute_sections.jsonl",
        "_parsed_line_number": 7,
    }


def test_pass36_lineage_joins_admitted_node_snapshot_event_and_build_without_network(monkeypatch, tmp_path: Path) -> None:
    service = AuthorityProductService(data_root=tmp_path)
    monkeypatch.setattr(service, "_active_product", lambda *, verify_all: _active_product(tmp_path))
    monkeypatch.setattr(service, "_iter_active_parsed_rows", lambda _active: iter([_parsed_row()]))

    result = service.authority_lineage("statute-19a-1653")

    assert result["status"] == "lineage_observed"
    assert result["review_required"] is True
    assert result["network_used"] is False
    assert result["current_law_determined"] is False
    assert result["build"]["build_id"] == "b" * 24
    assert result["parsed_node"]["source_span"] == {"start_offset": 10, "end_offset": 44}
    assert result["parsed_node"]["parsed_record_locator"] == {
        "relative_path": "statutes/statute_sections.jsonl",
        "line_number": 7,
    }
    assert result["snapshot"]["materialized_in_active_build"] is True
    assert result["snapshot"]["sha256"] == "a" * 64
    assert result["official_source"]["url"] == "https://legislature.maine.gov/statutes/19-a/"
    assert result["retrieval_event"]["network_used_by_inspector"] is False


def test_pass36_lineage_fails_closed_when_parsed_hash_does_not_match_active_snapshot(monkeypatch, tmp_path: Path) -> None:
    service = AuthorityProductService(data_root=tmp_path)
    monkeypatch.setattr(service, "_active_product", lambda *, verify_all: _active_product(tmp_path))
    monkeypatch.setattr(service, "_iter_active_parsed_rows", lambda _active: iter([_parsed_row(source_hash="d" * 64)]))

    result = service.authority_lineage("maine-title-19a")

    assert result["status"] == "needs_review"
    assert "parsed_source_hash_does_not_match_active_snapshot" in result["blockers"]
    assert result["review_required"] is True
    assert result["current_law_determined"] is False


def test_pass36_lineage_invalid_source_id_is_blocked_without_reading_authority(monkeypatch, tmp_path: Path) -> None:
    service = AuthorityProductService(data_root=tmp_path)
    monkeypatch.setattr(service, "_active_product", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected read")))

    result = service.authority_lineage("../not-an-admitted-source")

    assert result["status"] == "blocked"
    assert result["blockers"] == ["source_id_invalid"]


def test_pass36_canonical_route_requires_role_tenant_and_writes_audit(monkeypatch) -> None:
    monkeypatch.setattr(
        authority_routes.AuthorityProductService,
        "authority_lineage",
        lambda _self, source_id: {
            "status": "lineage_observed",
            "source_id": source_id,
            "review_required": True,
            "network_used": False,
            "current_law_determined": False,
            "build": {"build_id": "b" * 24},
        },
    )
    client = TestClient(canonical_app)

    assert client.get("/api/authority/lineage/statute-19a-1653").status_code == 403
    response = client.get("/api/authority/lineage/statute-19a-1653", headers=HEADERS)

    assert response.status_code == 200
    assert response.headers["X-MFLL-RBAC"] == "enforced"
    assert response.headers["X-MFLL-Audit-Event-Id"]
    assert response.json()["audit_event"]["action"] == "authority_lineage_inspection"


def test_pass36_frozen_route_and_production_ui_are_registered(monkeypatch) -> None:
    monkeypatch.setattr(
        frozen_api.AuthorityProductService,
        "authority_lineage",
        lambda _self, source_id: {
            "status": "lineage_observed",
            "source_id": source_id,
            "review_required": True,
            "network_used": False,
            "current_law_determined": False,
        },
    )
    response = TestClient(frozen_api.app).get("/api/authority/lineage/statute-19a-1653")

    assert response.status_code == 200
    assert response.json()["source_id"] == "statute-19a-1653"
    frozen_source = (ROOT / "src" / "maine_family_law_llm" / "api.py").read_text(encoding="utf-8")
    source_ui = (ROOT / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_bytes()
    mirrored_ui = (ROOT / "maine_family_law_llm" / "ui" / "workbench.js").read_bytes()
    assert '@app.get("/api/authority/lineage/{source_id}")' in frozen_source
    assert b"installAuthorityLineageInspector" in source_ui
    assert b"/api/authority/lineage/" in source_ui
    assert b"data-authority-lineage-source" in source_ui
    assert b"does not contact or update any official source" in source_ui
    assert source_ui == mirrored_ui
