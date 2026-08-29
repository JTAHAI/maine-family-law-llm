from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.main import app as canonical_app
from app.api.routes import authority as authority_routes
from app.services.authority_library_service import AuthorityLibraryService
from maine_family_law_llm import api as frozen_api


ROOT = Path(__file__).resolve().parents[1]
HEADERS = {"X-User-Role": "reviewer", "X-Tenant-Id": "tenant-authority-update"}
FIRST_BUILD = "a" * 24
SECOND_BUILD = "b" * 24


def _write_build(root: Path, build_id: str, sources: list[dict[str, str]]) -> None:
    path = root / "authority_product" / "builds" / build_id / "authority_product_manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"schema_version": "1.1", "build_id": build_id, "source_snapshots": sources, "artifacts": []}),
        encoding="utf-8",
    )


def test_pass31_staged_builds_diff_activate_and_restore_atomically(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "external-authority"
    root.mkdir()
    _write_build(root, FIRST_BUILD, [{"source_id": "statute-a", "sha256": "1" * 64}])
    _write_build(
        root,
        SECOND_BUILD,
        [
            {"source_id": "statute-a", "sha256": "2" * 64},
            {"source_id": "rule-b", "sha256": "3" * 64},
        ],
    )

    monkeypatch.setattr(
        "app.services.authority_library_service.AuthorityProductVerifier.verify",
        lambda _self, *, build_id=None: SimpleNamespace(status="pass", blockers=[]),
    )
    service = AuthorityLibraryService(data_root=root, repo_root=tmp_path / "source-repo")

    first = service.activate_build(FIRST_BUILD)
    assert first["status"] == "pass"
    pointer_path = root / "authority_product" / "ACTIVE_BUILD.json"
    assert json.loads(pointer_path.read_text(encoding="utf-8"))["build_id"] == FIRST_BUILD

    diff = service.compare_builds(SECOND_BUILD)
    assert diff["status"] == "needs_review"
    assert diff["source_diff"]["added"] == ["rule-b"]
    assert diff["source_diff"]["hash_changed"] == ["statute-a"]
    assert diff["review_required"] is True

    activated = service.activate_build(SECOND_BUILD)
    assert activated["status"] == "pass"
    assert activated["previous_build_id"] == FIRST_BUILD
    assert json.loads(pointer_path.read_text(encoding="utf-8"))["build_id"] == SECOND_BUILD

    restored = service.activate_build(FIRST_BUILD, operation="rollback")
    assert restored["status"] == "pass"
    assert restored["operation"] == "rollback"
    assert json.loads(pointer_path.read_text(encoding="utf-8"))["build_id"] == FIRST_BUILD
    receipts = [json.loads(line) for line in (root / "authority_product" / "activation_receipts.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [row["operation"] for row in receipts] == ["activate", "activate", "rollback"]


def test_pass31_fixture_update_refuses_nonqualifying_authority_without_activation(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "external-authority"
    from legal.connectors import load_official_source_targets

    fixture_target = next(item for item in load_official_source_targets() if item.target_id == "me-courts-forms-index")
    monkeypatch.setattr("app.services.authority_library_service.load_official_source_targets", lambda: [fixture_target])
    service = AuthorityLibraryService(data_root=root, repo_root=ROOT, fixture_dir=ROOT / "data" / "fixtures")
    queued = service.update(fixture_mode=True, max_targets=1)
    deadline = time.monotonic() + 20
    job = service.get_job(queued["job_id"])
    while job is not None and job.status in {"queued", "running"} and time.monotonic() < deadline:
        time.sleep(0.05)
        job = service.get_job(queued["job_id"])

    assert job is not None
    assert job.status == "failed", job.as_dict()
    assert job.result["status"] == "partial"
    assert job.result["activation_performed"] is False
    assert not (root / "authority_product" / "ACTIVE_BUILD.json").exists()
    assert job.result["publication"]["status"] == "blocked"


def test_pass31_canonical_activation_requires_role_acknowledgement_and_audit(monkeypatch) -> None:
    monkeypatch.setattr(
        authority_routes.AuthorityLibraryService,
        "activate_build",
        lambda _self, build_id, *, operation="activate": {
            "status": "pass",
            "operation": operation,
            "build_id": build_id,
            "previous_build_id": FIRST_BUILD,
            "review_required": True,
        },
    )
    client = TestClient(canonical_app)

    denied = client.post("/api/authority/activate", json={"build_id": SECOND_BUILD, "acknowledged": True})
    assert denied.status_code == 403

    unacknowledged = client.post("/api/authority/activate", headers=HEADERS, json={"build_id": SECOND_BUILD, "acknowledged": False})
    assert unacknowledged.status_code == 200
    assert "authority_activation_acknowledgement_required" in unacknowledged.json()["blockers"]

    activated = client.post("/api/authority/activate", headers=HEADERS, json={"build_id": SECOND_BUILD, "acknowledged": True})
    assert activated.status_code == 200
    assert activated.headers["X-MFLL-RBAC"] == "enforced"
    assert activated.headers["X-MFLL-Audit-Event-Id"]
    assert activated.json()["audit_event"]["action"] == "authority_build_activation"


def test_pass31_frozen_runtime_activation_route_requires_acknowledgement(monkeypatch) -> None:
    monkeypatch.setattr(
        frozen_api.AuthorityLibraryService,
        "activate_build",
        lambda _self, build_id, *, operation="activate": {
            "status": "pass",
            "operation": operation,
            "build_id": build_id,
            "review_required": True,
        },
    )
    client = TestClient(frozen_api.app)

    blocked = client.post("/api/authority/activate", json={"build_id": SECOND_BUILD, "acknowledged": False})
    assert blocked.status_code == 200
    assert "authority_activation_acknowledgement_required" in blocked.json()["blockers"]

    activated = client.post("/api/authority/activate", json={"build_id": SECOND_BUILD, "acknowledged": True})
    assert activated.status_code == 200
    assert activated.json()["operation"] == "activate"


def test_pass31_frozen_runtime_and_production_ui_expose_staged_build_controls() -> None:
    frozen_api = (ROOT / "src" / "maine_family_law_llm" / "api.py").read_text(encoding="utf-8")
    source_ui = (ROOT / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_bytes()
    mirrored_ui = (ROOT / "maine_family_law_llm" / "ui" / "workbench.js").read_bytes()

    assert '@app.post("/api/authority/activate")' in frozen_api
    assert '@app.post("/api/authority/rollback")' in frozen_api
    assert b"installAuthorityUpdateCenter" in source_ui
    assert b"Stage official-source update" in source_ui
    assert b"/api/authority/builds/${encodeURIComponent(buildId)}/diff" in source_ui
    assert b"operation === 'rollback' ? 'rollback' : 'activate'" in source_ui
    assert source_ui == mirrored_ui
