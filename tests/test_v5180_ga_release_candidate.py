from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import maine_family_law_llm.api as api_module
from legal.release.release_candidate_operations import (
    GAReleaseCandidateError,
    GAReleaseCandidateOperationsStore,
)


VERSION = "5.18.0"
SOURCE_HASH = "a" * 64


def _policy(path: Path) -> Path:
    path.write_text(json.dumps({
        "version": "test-v5.18",
        "product_version": VERSION,
        "pass_number": 50,
    }), encoding="utf-8")
    return path


def _store(tmp_path: Path) -> GAReleaseCandidateOperationsStore:
    return GAReleaseCandidateOperationsStore(
        Path.cwd(), tmp_path / "release", policy_path=_policy(tmp_path / "policy.json")
    )


def _candidate(store: GAReleaseCandidateOperationsStore) -> None:
    store.create_candidate(
        candidate_id="v5-18-0-rc1",
        version=VERSION,
        source_repo_zip_sha256=SOURCE_HASH,
        source_repo_zip_name="Maine-Family-Law-LLM-v5.18.0-ga-release-candidate-full-source.zip",
        approved=True,
    )


def _record_all_artifacts(store: GAReleaseCandidateOperationsStore) -> None:
    for index, artifact_type in enumerate(sorted(store.REQUIRED_ARTIFACT_TYPES), start=1):
        external = artifact_type in store.EXTERNAL_ARTIFACT_TYPES
        digest = SOURCE_HASH if artifact_type == "source_repo_zip" else f"{index:064x}"[-64:]
        store.record_artifact(
            candidate_id="v5-18-0-rc1",
            artifact_type=artifact_type,
            artifact_version=VERSION,
            reference=f"artifact-{artifact_type}",
            sha256=digest,
            present=True,
            external=external,
            immutable=True,
            approved=True,
        )


def _record_all_signoffs(store: GAReleaseCandidateOperationsStore) -> None:
    for index, role in enumerate(sorted(store.REQUIRED_SIGNOFF_ROLES), start=1):
        store.record_signoff(
            candidate_id="v5-18-0-rc1",
            role=role,
            signer_label=f"{role}-reviewer",
            status="approved",
            signed_at="2026-07-29T01:30:00-04:00",
            evidence_sha256=f"{index + 20:064x}"[-64:],
            approved=True,
        )


def test_v518_status_is_fail_closed_without_external_release_root(tmp_path: Path):
    store = GAReleaseCandidateOperationsStore(Path.cwd(), None, policy_path=_policy(tmp_path / "policy.json"))
    status = store.status()
    assert status["status"] == "blocked"
    assert "release_root_not_configured" in status["blockers"]
    assert status["pass50_complete"] is False
    assert status["external_launch_evidence_gate_required"] is True


def test_v518_candidate_identity_and_version_are_immutable(tmp_path: Path):
    store = _store(tmp_path)
    with pytest.raises(GAReleaseCandidateError, match="approval_required"):
        store.create_candidate(
            candidate_id="v5-18-0-rc1", version=VERSION,
            source_repo_zip_sha256=SOURCE_HASH, source_repo_zip_name="source.zip", approved=False,
        )
    with pytest.raises(GAReleaseCandidateError, match="version_mismatch"):
        store.create_candidate(
            candidate_id="v5-18-0-rc1", version="5.17.0",
            source_repo_zip_sha256=SOURCE_HASH, source_repo_zip_name="source.zip", approved=True,
        )
    _candidate(store)
    same = store.create_candidate(
        candidate_id="v5-18-0-rc1", version=VERSION,
        source_repo_zip_sha256=SOURCE_HASH,
        source_repo_zip_name="Maine-Family-Law-LLM-v5.18.0-ga-release-candidate-full-source.zip",
        approved=True,
    )
    assert same["candidate_id"] == "v5-18-0-rc1"
    with pytest.raises(GAReleaseCandidateError, match="id_immutable"):
        store.create_candidate(
            candidate_id="v5-18-0-rc1", version=VERSION,
            source_repo_zip_sha256="b" * 64,
            source_repo_zip_name="Maine-Family-Law-LLM-v5.18.0-ga-release-candidate-full-source.zip",
            approved=True,
        )


def test_v518_external_artifacts_cannot_be_recorded_as_packaged_source(tmp_path: Path):
    store = _store(tmp_path)
    _candidate(store)
    with pytest.raises(GAReleaseCandidateError, match="must_remain_external"):
        store.record_artifact(
            candidate_id="v5-18-0-rc1",
            artifact_type="gold_eval_pack_manifest",
            artifact_version=VERSION,
            reference="gold-eval-v1",
            sha256="b" * 64,
            present=True,
            external=False,
            immutable=True,
            approved=True,
        )
    with pytest.raises(GAReleaseCandidateError, match="source_zip_hash_mismatch"):
        store.record_artifact(
            candidate_id="v5-18-0-rc1",
            artifact_type="source_repo_zip",
            artifact_version=VERSION,
            reference="source-zip-v1",
            sha256="b" * 64,
            present=True,
            external=False,
            immutable=True,
            approved=True,
        )


def test_v518_complete_software_inventory_is_ready_only_for_external_pass50_gate(tmp_path: Path):
    store = _store(tmp_path)
    _candidate(store)
    _record_all_artifacts(store)
    _record_all_signoffs(store)
    result = store.freeze_candidate(
        candidate_id="v5-18-0-rc1",
        audit_enterprise_readiness_status="pass",
        approved=True,
    )
    assert result["report"]["status"] == "pass"
    assert result["release_candidate_frozen"] is True
    assert result["status"] == "ready_for_external_pass50_gate"
    assert result["pass50_complete"] is False
    assert result["external_launch_evidence_gate_required"] is True
    assert store.verify()["status"] == "pass"


def test_v518_open_p1_and_missing_signoff_block_freeze(tmp_path: Path):
    store = _store(tmp_path)
    _candidate(store)
    _record_all_artifacts(store)
    for role in ("security", "product", "ops"):
        store.record_signoff(
            candidate_id="v5-18-0-rc1", role=role, signer_label=f"{role}-reviewer",
            status="approved", signed_at="2026-07-29T01:30:00-04:00",
            evidence_sha256="c" * 64, approved=True,
        )
    store.record_blocker(
        candidate_id="v5-18-0-rc1", blocker_id="signed-msix-missing",
        severity="P1", status="open", description_code="signed-msix-not-qualified",
        evidence_sha256="d" * 64, approved=True,
    )
    result = store.freeze_candidate(
        candidate_id="v5-18-0-rc1", audit_enterprise_readiness_status="pass", approved=True,
    )
    assert result["report"]["status"] == "blocked"
    assert "missing_signoff:legal" in result["report"]["blockers"]
    assert any(item.startswith("open_P1_blocker") for item in result["report"]["blockers"])
    assert result["release_candidate_frozen"] is False


def test_v518_packet_is_immutable_and_tamper_evident(tmp_path: Path):
    store = _store(tmp_path)
    _candidate(store)
    built = store.build_evidence_packet(approved=True)
    assert built["status"] == "pass"
    assert built["pass50_complete"] is False
    generation = store.evidence_root / built["generation_id"]
    assert store.verify_generation(built["generation_id"])["status"] == "pass"
    (generation / "ga-release-candidate.json").write_text("{}", encoding="utf-8")
    with pytest.raises(GAReleaseCandidateError, match="generation_verification_failed"):
        store.verify_generation(built["generation_id"])


def test_v518_api_and_ui_surface_are_available(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    release_root = tmp_path / "release"
    monkeypatch.setenv("MAINE_FAMILY_LAW_RELEASE_ROOT", str(release_root))
    client = TestClient(api_module.app)
    blocked = client.get("/api/ga-release-candidate/status")
    assert blocked.status_code == 200
    assert blocked.json()["pass50_complete"] is False
    created = client.post("/api/ga-release-candidate/candidates", json={
        "candidate_id": "v5-18-0-rc1",
        "version": VERSION,
        "source_repo_zip_sha256": SOURCE_HASH,
        "source_repo_zip_name": "Maine-Family-Law-LLM-v5.18.0-ga-release-candidate-full-source.zip",
        "approved": True,
    })
    assert created.status_code == 200
    built = client.post("/api/ga-release-candidate/evidence/build", json={"approved": True})
    assert built.status_code == 200
    assert len(built.json()["artifacts"]) == 4
    download = client.get(built.json()["artifacts"][0]["download_url"])
    assert download.status_code == 200

    html = (Path.cwd() / "src" / "maine_family_law_llm" / "ui" / "workbench.html").read_text(encoding="utf-8")
    js = (Path.cwd() / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_text(encoding="utf-8")
    assert "Pass 50 GA release candidate" in html
    assert "ga-release-candidate-freeze" in html
    assert "/api/ga-release-candidate/status" in js
    assert "buildGAReleaseCandidateEvidence" in js


def test_v518_api_rejects_absolute_artifact_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MAINE_FAMILY_LAW_RELEASE_ROOT", str(tmp_path / "release"))
    client = TestClient(api_module.app)
    client.post("/api/ga-release-candidate/candidates", json={
        "candidate_id": "v5-18-0-rc1", "version": VERSION,
        "source_repo_zip_sha256": SOURCE_HASH,
        "source_repo_zip_name": "Maine-Family-Law-LLM-v5.18.0-ga-release-candidate-full-source.zip",
        "approved": True,
    })
    response = client.post("/api/ga-release-candidate/artifacts", json={
        "candidate_id": "v5-18-0-rc1", "artifact_type": "release_notes",
        "artifact_version": VERSION, "reference": "C:\\private\\release-notes.md",
        "sha256": "b" * 64, "present": True, "external": False,
        "immutable": True, "approved": True,
    })
    assert response.status_code == 409
    assert response.json()["detail"] == "ga_release_candidate_artifact_reference_invalid"
