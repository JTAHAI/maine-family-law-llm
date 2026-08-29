from __future__ import annotations

import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app as canonical_app
from app.api.routes import authority as authority_routes
from app.services.authority_library_service import AuthorityLibraryService
from legal.connectors.parser_regression import ParserRegressionCorpus
from maine_family_law_llm import api as frozen_api


ROOT = Path(__file__).resolve().parents[1]
HEADERS = {"X-User-Role": "reviewer", "X-Tenant-Id": "tenant-parser-regression"}


def test_pass35_versioned_fixture_corpus_runs_offline_and_quarantines_malformed_download() -> None:
    result = ParserRegressionCorpus(ROOT / "data" / "fixtures" / "parser_regression").run()

    assert result["status"] == "passed"
    assert result["fixture_count"] == 6
    assert result["passed_count"] == 6
    assert result["network_used"] is False
    assert result["persistent_state_changed"] is False
    assert result["corpus_is_legal_authority"] is False
    assert result["can_support_legal_claim"] is False
    by_id = {row["fixture_id"]: row for row in result["fixtures"]}
    assert by_id["revisor-layout-table-v1"]["status"] == "passed"
    assert by_id["forms-table-v1"]["extracted_count"] >= 1
    assert by_id["rules-footnote-v1"]["extracted_count"] >= 2
    assert by_id["malformed-download-v1"]["expected_status"] == "quarantined"
    assert by_id["malformed-download-v1"]["status"] == "passed"
    assert "malformed_download_quarantined" in by_id["malformed-download-v1"]["checks"]


def test_pass35_hash_mismatch_fails_closed_before_parser_invocation(tmp_path: Path) -> None:
    corpus_root = tmp_path / "parser-regression"
    shutil.copytree(ROOT / "data" / "fixtures" / "parser_regression", corpus_root)
    (corpus_root / "forms_table_v1.html").write_text("tampered synthetic fixture", encoding="utf-8")

    result = ParserRegressionCorpus(corpus_root).run_fixture("forms-table-v1")

    assert result["status"] == "blocked"
    assert result["fixture_sha256"] is None
    assert result["extracted_count"] == 0
    assert result["blockers"] == ["fixture_content_hash_mismatch"]
    assert result["can_support_legal_claim"] is False


def test_pass35_canonical_routes_require_role_tenant_and_audit(monkeypatch) -> None:
    monkeypatch.setattr(
        authority_routes.AuthorityLibraryService,
        "parser_regression_corpus",
        lambda _self: {
            "status": "passed",
            "fixture_count": 1,
            "passed_count": 1,
            "fixtures": [{"fixture_id": "fictional-fixture", "status": "passed"}],
            "blockers": [],
            "review_required": True,
            "network_used": False,
            "corpus_is_legal_authority": False,
        },
    )
    monkeypatch.setattr(
        authority_routes.AuthorityLibraryService,
        "parser_regression_fixture",
        lambda _self, fixture_id: {
            "status": "passed",
            "fixture_id": fixture_id,
            "fixture_sha256": "a" * 64,
            "review_required": True,
            "can_support_legal_claim": False,
        },
    )
    client = TestClient(canonical_app)

    assert client.get("/api/authority/parser-regression").status_code == 403
    response = client.get("/api/authority/parser-regression", headers=HEADERS)
    assert response.status_code == 200
    assert response.headers["X-MFLL-RBAC"] == "enforced"
    assert response.headers["X-MFLL-Audit-Event-Id"]
    assert response.json()["audit_event"]["action"] == "authority_parser_regression"

    detail = client.get("/api/authority/parser-regression/fictional-fixture", headers=HEADERS)
    assert detail.status_code == 200
    assert detail.json()["fixture_id"] == "fictional-fixture"
    assert detail.json()["audit_event"]["action"] == "authority_parser_regression_fixture"


def test_pass35_frozen_routes_and_production_ui_are_registered(monkeypatch) -> None:
    monkeypatch.setattr(
        frozen_api.AuthorityLibraryService,
        "parser_regression_corpus",
        lambda _self: {"status": "passed", "fixtures": [], "review_required": True, "network_used": False},
    )
    monkeypatch.setattr(
        frozen_api.AuthorityLibraryService,
        "parser_regression_fixture",
        lambda _self, fixture_id: {"status": "passed", "fixture_id": fixture_id, "review_required": True},
    )
    client = TestClient(frozen_api.app)
    assert client.get("/api/authority/parser-regression").status_code == 200
    assert client.get("/api/authority/parser-regression/revisor-layout-table-v1").json()["fixture_id"] == "revisor-layout-table-v1"

    frozen_source = (ROOT / "src" / "maine_family_law_llm" / "api.py").read_text(encoding="utf-8")
    source_ui = (ROOT / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_bytes()
    mirrored_ui = (ROOT / "maine_family_law_llm" / "ui" / "workbench.js").read_bytes()
    assert '@app.get("/api/authority/parser-regression")' in frozen_source
    assert '@app.get("/api/authority/parser-regression/{fixture_id}")' in frozen_source
    assert b"installAuthorityParserRegressionControl" in source_ui
    assert b"/api/authority/parser-regression" in source_ui
    assert b"data-parser-regression-fixture" in source_ui
    assert b"never legal authority" in source_ui
    assert source_ui == mirrored_ui


def test_pass35_frozen_source_route_runs_bundled_synthetic_corpus() -> None:
    """Exercise the frozen API module with its real bundled-data lookup path."""
    response = TestClient(frozen_api.app).get("/api/authority/parser-regression")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "passed"
    assert payload["fixture_count"] == 6
    assert payload["network_used"] is False
    assert payload["corpus_is_legal_authority"] is False


def test_pass35_store_build_pipeline_includes_parser_fixture_data() -> None:
    spec = (ROOT / "store" / "pyinstaller" / "maine_family_law_llm.spec").read_text(encoding="utf-8")
    assert '(str(ROOT / "data"), "data")' in spec
    assert (ROOT / "data" / "fixtures" / "parser_regression" / "manifest.json").is_file()


def test_pass35_invalid_fixture_id_fails_closed() -> None:
    service = AuthorityLibraryService(repo_root=ROOT)
    result = service.parser_regression_fixture("../../not-a-fixture")
    assert result["status"] == "blocked"
    assert result["blockers"] == ["parser_regression_fixture_id_invalid"]
