from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi.testclient import TestClient

from maine_family_law_llm import api


def test_document_intelligence_artifact_download_is_bound_to_originating_session(
    monkeypatch, tmp_path: Path
) -> None:
    """A copied opaque URL must not reveal a fictional matter artifact."""

    case_root = tmp_path / "fictional-matter"
    artifact = case_root / "07_WORK_PRODUCTS" / "fictional-review-receipt.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text('{"fictional": true, "review_required": true}', encoding="utf-8")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    monkeypatch.setattr(api, "active_case_root", lambda: case_root)
    api._document_intelligence_artifacts.clear()

    owner = {
        "role": "reviewer",
        "tenant_id": "fictional-tenant",
        "client_session_id": "c" * 48,
    }
    context = api._record_capability_identity.set(owner)
    try:
        token = api._document_intelligence_artifact_token(
            case_root, artifact.relative_to(case_root).as_posix(), digest
        )
    finally:
        api._record_capability_identity.reset(context)

    headers = {
        "X-User-Role": "reviewer",
        "X-Tenant-Id": "fictional-tenant",
        "X-MFLL-Client-Session": "c" * 48,
    }
    client = TestClient(api.app)
    owned = client.get(f"/api/document-intelligence/artifacts/{token}", headers=headers)
    assert owned.status_code == 200
    assert owned.content == artifact.read_bytes()
    replayed = client.get(
        f"/api/document-intelligence/artifacts/{token}",
        headers={**headers, "X-MFLL-Client-Session": "d" * 48},
    )
    assert replayed.status_code == 404


def test_shipped_workbench_fetches_session_bound_artifacts_with_local_headers() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    mirrored = (root / "maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    assert source == mirrored
    assert "downloadSessionBoundArtifact" in source
    assert "isSessionBoundArtifactUrl" in source
    assert "headers: localRequestHeaders()" in source
    assert "copied URL fails closed" in source
    assert "document-workspace\\/exports" in source
    assert "/export-sessions?format=" in source
