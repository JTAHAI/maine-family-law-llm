from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi.testclient import TestClient

from maine_family_law_llm import api


def _row(case_root: Path) -> dict[str, str]:
    content = b"Fictional source-bound record for capability testing."
    path = case_root / "02_PRIVATE_FORENSIC_MASTER" / "files" / "REC-1.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return {
        "evidence_id": "REC-1",
        "private_copy_relpath": path.relative_to(case_root).as_posix(),
        "source_hash": hashlib.sha256(content).hexdigest(),
        "source_type": "txt",
        "source_locator": "REC-1.txt",
    }


def test_record_capability_binds_session_role_tenant_resource_and_allowed_action(
    monkeypatch, tmp_path: Path
) -> None:
    case_root = tmp_path / "fictional-matter"
    row = _row(case_root)
    monkeypatch.setattr(api, "active_case_root", lambda: case_root)
    monkeypatch.setattr(api, "load_case_search_records", lambda _root: [row])
    api._record_open_tokens.clear()
    owner = {"role": "reviewer", "tenant_id": "fictional-tenant", "client_session_id": "a" * 48}
    context = api._record_capability_identity.set(owner)
    try:
        inspect_only = api._record_open_token(
            case_root,
            "REC-1",
            "REC-1.txt",
            allowed_actions={"record_inspect"},
        )
    finally:
        api._record_capability_identity.reset(context)

    client = TestClient(api.app)
    owner_headers = {
        "X-User-Role": "reviewer",
        "X-Tenant-Id": "fictional-tenant",
        "X-MFLL-Client-Session": "a" * 48,
    }
    assert client.get(f"/api/records/inspect/{inspect_only}", headers=owner_headers).status_code == 200
    assert client.get(f"/api/records/open/{inspect_only}", headers=owner_headers).status_code == 404
    assert client.get(
        f"/api/records/inspect/{inspect_only}",
        headers={**owner_headers, "X-MFLL-Client-Session": "b" * 48},
    ).status_code == 404
    assert client.get(
        f"/api/records/inspect/{inspect_only}",
        headers={**owner_headers, "X-User-Role": "attorney"},
    ).status_code == 404
    assert client.get(
        f"/api/records/inspect/{inspect_only}",
        headers={**owner_headers, "X-Tenant-Id": "other-tenant"},
    ).status_code == 404


def test_shipped_workbench_uses_one_random_session_header_for_protected_record_actions() -> None:
    root = Path(__file__).resolve().parents[1]
    for relative in ("src/maine_family_law_llm/ui/workbench.js", "maine_family_law_llm/ui/workbench.js"):
        script = (root / relative).read_text(encoding="utf-8")
        assert "X-MFLL-Client-Session" in script
        assert "localCapabilitySession" in script
        assert "const endpoint = `/api/records/open/" in script
        assert "headers: localRequestHeaders()" in script
