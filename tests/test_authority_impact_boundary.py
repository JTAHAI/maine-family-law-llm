"""Fictional authority-change review: both route families fail closed."""

import json

import pytest
import test_v5150_authority_change_impact as authority_fixtures
from fastapi.testclient import TestClient
from test_filing_assignment_privacy import _headers

from legal.documents.workspace import create_document
from legal.review import authority_impact as impact
from maine_family_law_llm import api


@pytest.fixture
def case(tmp_path, monkeypatch):
    root = tmp_path / "fictional-impact-matter"
    root.mkdir()
    monkeypatch.setattr(api, "active_case_root", lambda: root)
    return root


@pytest.mark.parametrize(
    "header,code",
    [
        ("X-User-Role", 403),
        ("X-Tenant-Id", 403),
        ("X-MFLL-Client-Session", 403),
        ("X-MFLL-Matter-Id", 409),
    ],
)
@pytest.mark.parametrize("family", ["desktop", "matter"])
@pytest.mark.parametrize("operation", ["status", "document", "matter", "build", "verify"])
def test_both_route_families_require_scope_before_store(case, header, code, family, operation):
    from app.api.main import app as canonical

    document_id, build_id = "a" * 32, "b" * 24
    pair = {"base_build_id": "c" * 24, "target_build_id": "d" * 24}
    if family == "desktop":
        root = "/api/authority-change-impact"
        routes = {
            "status": ("GET", root + "/status", None),
            "document": ("POST", root + "/analyze", {**pair, "document_id": document_id}),
            "matter": ("POST", root + "/matter/analyze", pair),
            "build": (
                "POST",
                root + "/build",
                {
                    **pair,
                    "document_id": document_id,
                    "expected_revision_id": document_id,
                    "approved": True,
                },
            ),
            "verify": ("GET", root + "/verify?build_id=" + build_id, None),
        }
        app = api.app
    else:
        root = f"/api/matters/{api._case_id(case)}/authority-change-impact"
        routes = {
            "status": ("GET", root + "/status", None),
            "document": ("POST", root + "/documents/" + document_id + "/analyze", pair),
            "matter": ("POST", root + "/analyze", pair),
            "build": (
                "POST",
                root + "/documents/" + document_id + "/packet",
                {**pair, "expected_revision_id": document_id, "approved": True},
            ),
            "verify": ("GET", root + "/packets/" + build_id, None),
        }
        app = canonical
    headers = _headers(case)
    headers[header] = ""
    method, url, payload = routes[operation]
    response = TestClient(app, headers=headers).request(method, url, json=payload)
    assert response.status_code == code, response.text
    assert "fictional-impact-matter" not in response.text
    assert not (case / impact.ROOT_FOLDER).exists()


def test_private_redirect_guard_before_creation(case, tmp_path, monkeypatch):
    from pathlib import Path

    repository = tmp_path / "fictional-repository"
    authority = tmp_path / "fictional-authority"
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda p: p.name == impact.ROOT_FOLDER or original(p))
    with pytest.raises(impact.AuthorityImpactError) as error:
        impact.AuthorityChangeImpactStore(case, data_root=authority, repo_root=repository)
    assert error.value.code == "authority_impact_storage_redirect_refused"
    assert not (case / impact.ROOT_FOLDER).exists()


def test_audit_tampering_refused_without_rewriting(case, tmp_path):
    store = impact.AuthorityChangeImpactStore(
        case, data_root=tmp_path / "authority", repo_root=tmp_path / "source"
    )
    args = dict(
        action="compare", actor_role="reviewer", tenant_id="local-desktop", audit_event_id="a" * 32
    )
    store.record_access(**args)
    ledger = store.encryptor.decrypt_json(json.loads(store.audit_path.read_bytes()))
    ledger["events"][0]["action"] = "altered"
    store.audit_path.write_text(json.dumps(store.encryptor.encrypt_json(ledger)))
    before = store.audit_path.read_bytes()
    with pytest.raises(impact.AuthorityImpactError) as error:
        store.record_access(**args)
    assert error.value.code == "authority_impact_audit_invalid"
    assert store.audit_path.read_bytes() == before


def test_exact_revision_required_before_artifact_write(case, tmp_path, monkeypatch):
    authority_fixtures.fictional_repository_boundary.__wrapped__(monkeypatch, tmp_path)
    root, first, second = authority_fixtures._publish_two_generations(tmp_path)
    doc = create_document(
        case,
        title="Fictional comparison",
        content="Fictional.",
        source_refs=[{"source_id": "maine-title-19a"}],
    )
    store = impact.AuthorityChangeImpactStore(
        case, data_root=root, repo_root=tmp_path / "fictional-source-repository"
    )
    with pytest.raises(impact.AuthorityImpactError) as error:
        store.build(doc["document_id"], first, second, approved=True, expected_revision_id="f" * 32)
    assert error.value.code == "authority_impact_revision_stale"
    assert not list(store.builds.iterdir())


def test_audit_failure_before_analysis_and_matter_switch_suppresses_response(
    case, tmp_path, monkeypatch
):
    from app.services.local_agent_context_service import LocalAgentAuditStore

    authority_fixtures.fictional_repository_boundary.__wrapped__(monkeypatch, tmp_path)
    _, first, second = authority_fixtures._publish_two_generations(tmp_path)
    doc = create_document(
        case,
        title="Fictional comparison",
        content="Fictional.",
        source_refs=[{"source_id": "maine-title-19a"}],
    )
    request = {"document_id": doc["document_id"], "base_build_id": first, "target_build_id": second}
    client = TestClient(api.app, headers=_headers(case))
    original = LocalAgentAuditStore.record

    def fail(*args, **kwargs):
        raise OSError("Private fictional path")

    monkeypatch.setattr(LocalAgentAuditStore, "record", fail)
    result = client.post("/api/authority-change-impact/analyze", json=request)
    assert result.status_code == 409 and "fictional" not in result.text
    monkeypatch.setattr(LocalAgentAuditStore, "record", original)
    analyze = impact.AuthorityChangeImpactStore.analyze_document
    other = tmp_path / "other-fictional"
    other.mkdir()

    def changed(self, *args):
        result = analyze(self, *args)
        monkeypatch.setattr(api, "active_case_root", lambda: other)
        return result

    monkeypatch.setattr(impact.AuthorityChangeImpactStore, "analyze_document", changed)
    response = client.post("/api/authority-change-impact/analyze", json=request)
    assert response.status_code == 409
    assert response.json()["detail"] == "review_active_matter_changed"
    assert "document_title" not in response.text


def test_saved_packet_corruption_is_visible_not_silently_hidden(case, tmp_path, monkeypatch):
    authority_fixtures.fictional_repository_boundary.__wrapped__(monkeypatch, tmp_path)
    _, first, second = authority_fixtures._publish_two_generations(tmp_path)
    doc = create_document(case, title="Fictional", content="Fictional source review.")

    def corrupt(self, **kwargs):
        raise impact.AuthorityImpactError(
            "authority_impact_build_unverified", "Review packet invalid.", status_code=409
        )

    monkeypatch.setattr(impact.AuthorityChangeImpactStore, "active", corrupt)
    response = TestClient(api.app, headers=_headers(case)).get(
        "/api/authority-change-impact/status", params={"document_id": doc["document_id"]}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "blocked"
    assert response.json()["blockers"] == ["authority_impact_build_unverified"]
    assert response.json()["active"] is None and response.json()["review_required"]


def test_alias_constructor_failure_preserves_safe_error(case, tmp_path, monkeypatch):
    from app.api.main import app as canonical
    from app.api.routes import authority_impact as routes

    authority_fixtures.fictional_repository_boundary.__wrapped__(monkeypatch, tmp_path)

    def denied(*args, **kwargs):
        raise impact.AuthorityImpactError(
            "authority_impact_storage_redirect_refused",
            "Private location refused.",
            status_code=409,
        )

    monkeypatch.setattr(routes, "AuthorityChangeImpactStore", denied)
    response = TestClient(canonical, headers=_headers(case)).get(
        f"/api/matters/{api._case_id(case)}/authority-change-impact/status"
    )
    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "authority_impact_storage_redirect_refused"
