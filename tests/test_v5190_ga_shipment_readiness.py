from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import maine_family_law_llm.api as api_module
from maine_family_law_llm.version import VERSION as PRODUCT_VERSION
from legal.release.shipment_readiness_operations import (
    GAShipmentReadinessError,
    GAShipmentReadinessStore,
)

VERSION = "5.19.0"
SOURCE_HASH = "a" * 64
RC_HASH = "b" * 64
RC_INVENTORY = "c" * 64


def _policy(path: Path) -> Path:
    path.write_text(json.dumps({
        "version": "test-v5.19",
        "product_version": VERSION,
        "pass_number": 51,
    }), encoding="utf-8")
    return path


def _store(tmp_path: Path) -> GAShipmentReadinessStore:
    return GAShipmentReadinessStore(
        Path.cwd(), tmp_path / "release", policy_path=_policy(tmp_path / "policy.json")
    )


def _shipment(store: GAShipmentReadinessStore) -> None:
    store.create_shipment(
        shipment_id="v5-19-0-ga1",
        version=VERSION,
        source_repo_zip_name="Maine-Family-Law-LLM-v5.19.0-ga-shipment-readiness-full-source.zip",
        source_repo_zip_sha256=SOURCE_HASH,
        release_candidate_id="v5-18-0-rc1",
        release_candidate_report_sha256=RC_HASH,
        release_candidate_inventory_hash=RC_INVENTORY,
        release_channel="source_release",
        approved=True,
    )


def _record_all_artifacts(store: GAShipmentReadinessStore) -> None:
    for index, artifact_type in enumerate(sorted(store.REQUIRED_ARTIFACT_TYPES), start=1):
        external = artifact_type in store.EXTERNAL_ARTIFACT_TYPES
        digest = SOURCE_HASH if artifact_type == "clean_source_zip" else f"{index:064x}"[-64:]
        store.record_artifact(
            shipment_id="v5-19-0-ga1",
            artifact_type=artifact_type,
            artifact_version=VERSION,
            reference=f"artifact-{artifact_type}",
            sha256=digest,
            present=True,
            external=external,
            immutable=True,
            approved=True,
        )


def _record_all_controls(store: GAShipmentReadinessStore) -> None:
    for index, control in enumerate(sorted(store.REQUIRED_CONTROLS), start=1):
        store.record_control(
            shipment_id="v5-19-0-ga1",
            control=control,
            satisfied=True,
            evidence_sha256=f"{index + 30:064x}"[-64:],
            approved=True,
        )


def _qualify_channel(store: GAShipmentReadinessStore) -> None:
    store.record_channel(
        shipment_id="v5-19-0-ga1",
        channel="source_release",
        status="qualified",
        package_sha256=SOURCE_HASH,
        qualification_evidence_sha256="d" * 64,
        rollback_evidence_sha256="e" * 64,
        distribution_reference="urn:release:v5-19-0",
        receipt_sha256="f" * 64,
        approved=True,
    )


def test_v519_status_is_fail_closed_without_external_root(tmp_path: Path):
    store = GAShipmentReadinessStore(Path.cwd(), None, policy_path=_policy(tmp_path / "policy.json"))
    status = store.status()
    assert status["status"] == "blocked"
    assert "release_root_not_configured" in status["blockers"]
    assert status["pass51_complete"] is False
    assert status["external_shipment_evidence_required"] is True


def test_v519_shipment_identity_and_channel_are_immutable(tmp_path: Path):
    store = _store(tmp_path)
    with pytest.raises(GAShipmentReadinessError, match="approval_required"):
        store.create_shipment(
            shipment_id="v5-19-0-ga1", version=VERSION,
            source_repo_zip_name="source.zip", source_repo_zip_sha256=SOURCE_HASH,
            release_candidate_id="v5-18-0-rc1", release_candidate_report_sha256=RC_HASH,
            release_candidate_inventory_hash=RC_INVENTORY, release_channel="source_release", approved=False,
        )
    _shipment(store)
    same = store.create_shipment(
        shipment_id="v5-19-0-ga1", version=VERSION,
        source_repo_zip_name="Maine-Family-Law-LLM-v5.19.0-ga-shipment-readiness-full-source.zip",
        source_repo_zip_sha256=SOURCE_HASH, release_candidate_id="v5-18-0-rc1",
        release_candidate_report_sha256=RC_HASH, release_candidate_inventory_hash=RC_INVENTORY,
        release_channel="source_release", approved=True,
    )
    assert same["shipment_id"] == "v5-19-0-ga1"
    with pytest.raises(GAShipmentReadinessError, match="id_immutable"):
        store.create_shipment(
            shipment_id="v5-19-0-ga1", version=VERSION,
            source_repo_zip_name="Maine-Family-Law-LLM-v5.19.0-ga-shipment-readiness-full-source.zip",
            source_repo_zip_sha256="1" * 64, release_candidate_id="v5-18-0-rc1",
            release_candidate_report_sha256=RC_HASH, release_candidate_inventory_hash=RC_INVENTORY,
            release_channel="source_release", approved=True,
        )


def test_v519_external_artifact_and_source_hash_boundaries(tmp_path: Path):
    store = _store(tmp_path)
    _shipment(store)
    with pytest.raises(GAShipmentReadinessError, match="must_remain_external"):
        store.record_artifact(
            shipment_id="v5-19-0-ga1", artifact_type="gold_eval_pack_manifest",
            artifact_version=VERSION, reference="gold-eval-v1", sha256="1" * 64,
            present=True, external=False, immutable=True, approved=True,
        )
    with pytest.raises(GAShipmentReadinessError, match="source_zip_hash_mismatch"):
        store.record_artifact(
            shipment_id="v5-19-0-ga1", artifact_type="clean_source_zip",
            artifact_version=VERSION, reference="source-v1", sha256="1" * 64,
            present=True, external=False, immutable=True, approved=True,
        )


def test_v519_complete_software_inventory_is_ready_only_for_external_gate(tmp_path: Path):
    store = _store(tmp_path)
    _shipment(store)
    _record_all_artifacts(store)
    _record_all_controls(store)
    _qualify_channel(store)
    result = store.evaluate_shipment(
        shipment_id="v5-19-0-ga1",
        release_candidate_status="pass",
        release_candidate_frozen=True,
        release_candidate_inventory_hash=RC_INVENTORY,
        approved=True,
    )
    assert result["report"]["status"] == "pass"
    assert result["report"]["ga_shipped"] is False
    assert result["status"] == "ready_for_external_pass51_gate"
    assert result["pass51_complete"] is False
    assert result["external_shipment_evidence_required"] is True


def test_v519_missing_control_channel_and_open_p1_block_readiness(tmp_path: Path):
    store = _store(tmp_path)
    _shipment(store)
    _record_all_artifacts(store)
    controls = sorted(store.REQUIRED_CONTROLS)
    for index, control in enumerate(controls[:-1], start=1):
        store.record_control(
            shipment_id="v5-19-0-ga1", control=control, satisfied=True,
            evidence_sha256=f"{index + 30:064x}"[-64:], approved=True,
        )
    store.record_blocker(
        shipment_id="v5-19-0-ga1", blocker_id="store-receipt-missing",
        severity="P1", status="open", description_code="distribution-not-qualified",
        evidence_sha256="2" * 64, approved=True,
    )
    result = store.evaluate_shipment(
        shipment_id="v5-19-0-ga1", release_candidate_status="pass",
        release_candidate_frozen=True, release_candidate_inventory_hash=RC_INVENTORY,
        approved=True,
    )
    assert result["report"]["status"] == "blocked"
    blockers = "\n".join(result["report"]["blockers"])
    assert "ga_control_not_satisfied" in blockers
    assert "release_channel_not_qualified" in blockers
    assert "open_P1_blocker:store-receipt-missing" in blockers


def test_v519_packet_is_immutable_and_tamper_evident(tmp_path: Path):
    store = _store(tmp_path)
    _shipment(store)
    built = store.build_evidence_packet(approved=True)
    assert built["status"] == "pass"
    assert built["pass51_complete"] is False
    generation = store.evidence_root / built["generation_id"]
    assert store.verify_generation(built["generation_id"])["status"] == "pass"
    (generation / "ga-shipment-readiness.json").write_text("{}", encoding="utf-8")
    with pytest.raises(GAShipmentReadinessError, match="generation_verification_failed"):
        store.verify_generation(built["generation_id"])


def test_v519_api_and_ui_surface_are_available(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MAINE_FAMILY_LAW_RELEASE_ROOT", str(tmp_path / "release"))
    client = TestClient(api_module.app)
    blocked = client.get("/api/ga-shipment-readiness/status")
    assert blocked.status_code == 200
    assert blocked.json()["pass51_complete"] is False
    created = client.post("/api/ga-shipment-readiness/shipments", json={
        "shipment_id": "v5-19-0-ga1", "version": PRODUCT_VERSION,
        "source_repo_zip_name": "Maine-Family-Law-LLM-v6.0.4-extended-hardening-full-source.zip",
        "source_repo_zip_sha256": SOURCE_HASH, "release_candidate_id": "v5-18-0-rc1",
        "release_candidate_report_sha256": RC_HASH,
        "release_candidate_inventory_hash": RC_INVENTORY,
        "release_channel": "source_release", "approved": True,
    })
    assert created.status_code == 200
    built = client.post("/api/ga-shipment-readiness/evidence/build", json={"approved": True})
    assert built.status_code == 200
    assert len(built.json()["artifacts"]) == 4
    download = client.get(built.json()["artifacts"][0]["download_url"])
    assert download.status_code == 200

    html_text = (Path.cwd() / "src" / "maine_family_law_llm" / "ui" / "workbench.html").read_text(encoding="utf-8")
    js = (Path.cwd() / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_text(encoding="utf-8")
    assert "Pass 51 GA shipment readiness" in html_text
    assert "ga-shipment-readiness-evaluate" in html_text
    assert "/api/ga-shipment-readiness/status" in js
    assert "buildGAShipmentReadinessEvidence" in js


def test_v519_api_rejects_absolute_distribution_reference(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MAINE_FAMILY_LAW_RELEASE_ROOT", str(tmp_path / "release"))
    client = TestClient(api_module.app)
    client.post("/api/ga-shipment-readiness/shipments", json={
        "shipment_id": "v5-19-0-ga1", "version": PRODUCT_VERSION,
        "source_repo_zip_name": "Maine-Family-Law-LLM-v6.0.4-extended-hardening-full-source.zip",
        "source_repo_zip_sha256": SOURCE_HASH, "release_candidate_id": "v5-18-0-rc1",
        "release_candidate_report_sha256": RC_HASH,
        "release_candidate_inventory_hash": RC_INVENTORY,
        "release_channel": "source_release", "approved": True,
    })
    response = client.post("/api/ga-shipment-readiness/channels", json={
        "shipment_id": "v5-19-0-ga1", "channel": "source_release", "status": "qualified",
        "package_sha256": SOURCE_HASH, "qualification_evidence_sha256": "d" * 64,
        "rollback_evidence_sha256": "e" * 64,
        "distribution_reference": "C:\\private\\receipt.json", "receipt_sha256": "f" * 64,
        "approved": True,
    })
    assert response.status_code == 409
    assert response.json()["detail"] == "ga_shipment_reference_invalid"
