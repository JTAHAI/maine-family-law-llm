from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.security import _path_is_within_prefix, review_response
from legal.release.release_candidate_operations import (
    GAReleaseCandidateError,
    GAReleaseCandidateOperationsStore,
)
from legal.security.strict_json import StrictJSONError, strict_json_loads


ROOT = Path(__file__).resolve().parents[1]
AUTH_HEADERS = {"X-User-Role": "attorney", "X-Tenant-Id": "tenant-final-hardening"}


def test_v602_audit_id_is_server_generated_and_matches_denial_payload() -> None:
    client = TestClient(app)
    supplied = str(uuid.uuid4())
    response = client.post(
        "/api/query",
        json={"query": "custody"},
        headers={"X-Audit-Event-Id": supplied},
    )
    assert response.status_code == 403
    emitted = response.headers["X-MFLL-Audit-Event-Id"]
    assert emitted != supplied
    uuid.UUID(emitted)
    assert response.json()["detail"]["audit_event_id"] == emitted


def test_v602_tenant_scope_rejects_pathlike_or_ambiguous_labels() -> None:
    client = TestClient(app)
    for tenant in ("tenant/escape", " tenant with spaces ", ".hidden", "a" * 65, "tenant:"):
        response = client.post(
            "/api/query",
            json={"query": "custody"},
            headers={"X-User-Role": "attorney", "X-Tenant-Id": tenant},
        )
        assert response.status_code == 403
        assert response.json()["detail"]["error"] == "tenant_scope_invalid"


def test_v602_admin_prefix_uses_path_component_boundary() -> None:
    assert _path_is_within_prefix("/api/admin", "/api/admin") is True
    assert _path_is_within_prefix("/api/admin/users", "/api/admin") is True
    assert _path_is_within_prefix("/api/administrator", "/api/admin") is False


def test_v602_review_response_safety_fields_cannot_be_overridden() -> None:
    payload = {
        "review_required": False,
        "rbac": {"enforced": False},
        "audit_event": {"audit_status": "caller_supplied"},
    }
    result = review_response("POST /api/test", "hardening_test", payload)
    assert result["review_required"] is True
    assert result["rbac"]["enforced"] is True
    assert result["audit_event"]["audit_status"] == "emitted"


@pytest.mark.parametrize(
    ("path", "field", "default"),
    [
        ("/api/draft", "human_review_complete", False),
        ("/api/review", "auto_extract_claims", True),
        ("/api/citations/verify", "auto_extract_claims", False),
        ("/api/authority/verify-output", "auto_extract_claims", True),
    ],
)
def test_v602_safety_sensitive_api_booleans_are_exact_json_booleans(
    path: str, field: str, default: bool
) -> None:
    client = TestClient(app)
    response = client.post(path, json={field: "true"}, headers=AUTH_HEADERS)
    assert response.status_code == 422
    assert response.json()["detail"] == {
        "error": "strict_json_boolean_required",
        "field": field,
    }

    accepted = client.post(path, json={field: default}, headers=AUTH_HEADERS)
    assert accepted.status_code == 200


def test_v602_strict_json_rejects_duplicate_keys_and_nonfinite_numbers() -> None:
    with pytest.raises(StrictJSONError, match="duplicate_key"):
        strict_json_loads('{"status":"pass","status":"blocked"}', require_object=True)
    for raw in ('{"score":NaN}', '{"score":Infinity}', '{"score":1e400}'):
        with pytest.raises(StrictJSONError, match="non_finite_number"):
            strict_json_loads(raw, require_object=True)


def test_v602_strict_json_enforces_size_depth_and_root_type() -> None:
    with pytest.raises(StrictJSONError, match="maximum_bytes_exceeded"):
        strict_json_loads('"' + ("x" * 100) + '"', max_bytes=16)
    with pytest.raises(StrictJSONError, match="maximum_depth_exceeded"):
        strict_json_loads("[" * 8 + "0" + "]" * 8, max_depth=4)
    with pytest.raises(StrictJSONError, match="object_required"):
        strict_json_loads("[]", require_object=True)


def test_v602_release_ledger_rejects_ambiguous_json_rows(tmp_path: Path) -> None:
    release_root = tmp_path / "release"
    store = GAReleaseCandidateOperationsStore(ROOT, release_root)
    release_root.mkdir(parents=True, exist_ok=True)
    assert store.ledger_path is not None
    store.ledger_path.write_text(
        '{"sequence":1,"sequence":2,"event_type":"candidate_created"}\n',
        encoding="utf-8",
    )
    with pytest.raises(GAReleaseCandidateError, match="ledger_invalid_json"):
        store.verify()


def test_v602_release_ledgers_flush_and_fsync_before_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    release_root = tmp_path / "release"
    store = GAReleaseCandidateOperationsStore(ROOT, release_root)
    calls: list[int] = []

    import legal.release.release_candidate_operations as module

    monkeypatch.setattr(module.os, "fsync", lambda fd: calls.append(fd))
    store.create_candidate(
        candidate_id="v6-0-2-rc-test",
        version="5.18.0",
        source_repo_zip_sha256="a" * 64,
        source_repo_zip_name="source.zip",
        approved=True,
    )
    assert calls
    assert store.verify()["status"] == "pass"
