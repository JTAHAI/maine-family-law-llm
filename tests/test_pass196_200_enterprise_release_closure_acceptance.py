from __future__ import annotations

import base64
import hashlib
import json
import zipfile
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from legal.release.enterprise_ga_closure import (
    EnterpriseDecisionPacket,
    IncidentResponseProgram,
    OrganizationalSignoffGate,
    PackageSbomGate,
    ReleaseReproducibilityGate,
    REQUIRED_DECISION_EVIDENCE,
    REQUIRED_SIGNOFF_LANES,
    REQUIRED_VULNERABILITY_TOOLS,
    _signature_payload,
)


ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _package(path: Path) -> None:
    manifest = """<?xml version=\"1.0\" encoding=\"utf-8\"?>
<Package xmlns=\"http://schemas.microsoft.com/appx/manifest/foundation/windows10\">
  <Identity Name=\"Fictional.MaineFamilyLawLLM\" Publisher=\"CN=Fictional\" Version=\"8.0.0.0\" ProcessorArchitecture=\"x64\"/>
  <Properties><DisplayName>Fictional</DisplayName><PublisherDisplayName>Fictional</PublisherDisplayName><Logo>Assets\\StoreLogo.png</Logo></Properties>
  <Resources><Resource Language=\"en-us\"/></Resources>
  <Applications><Application Id=\"App\" Executable=\"MaineFamilyLawLLM.exe\" EntryPoint=\"Windows.FullTrustApplication\"/></Applications>
</Package>"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("AppxManifest.xml", manifest)
        archive.writestr("THIRD_PARTY_NOTICES.txt", "Fictional license notice")
        archive.writestr("Assets/StoreLogo.png", b"fictional-png")


def _signed(payload: dict, *, key: Ed25519PrivateKey, key_id: str = "external-release-key") -> tuple[dict, dict]:
    payload["signature"] = {"key_id": key_id, "signature": base64.b64encode(key.sign(_signature_payload(payload))).decode("ascii")}
    public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return payload, {"trusted_keys": {key_id: base64.b64encode(public).decode("ascii")}}


def _closure_bundle(root: Path, package: Path) -> tuple[dict, Ed25519PrivateKey]:
    gate = PackageSbomGate(project_root=ROOT)
    preliminary = gate.audit(package=package, evidence_root=root).as_dict()
    _write(
        root / "release_vulnerability_audit.json",
        {
            "schema_version": "release_vulnerability_audit_v1",
            "package_sha256": preliminary["package_sha256"],
            "source_sbom_sha256": preliminary["source_sbom_sha256"],
            "tools": [{"tool": tool, "status": "pass", "report_sha256": hashlib.sha256(tool.encode()).hexdigest()} for tool in REQUIRED_VULNERABILITY_TOOLS],
            "blocking_finding_count": 0,
        },
    )
    package_report = gate.audit(package=package, evidence_root=root).as_dict()
    assert package_report["status"] == "pass", package_report
    key = Ed25519PrivateKey.generate()
    runs = {
        "schema_version": "release_reproducibility_runs_v1",
        "runs": [
            {"run_id": "independent_build_one", "status": "pass", "package_sha256": package_report["package_sha256"], "payload_manifest_sha256": package_report["payload_manifest_sha256"], "source_sbom_sha256": package_report["source_sbom_sha256"], "toolchain_manifest_sha256": hashlib.sha256(b"toolchain").hexdigest()},
            {"run_id": "independent_build_two", "status": "pass", "package_sha256": package_report["package_sha256"], "payload_manifest_sha256": package_report["payload_manifest_sha256"], "source_sbom_sha256": package_report["source_sbom_sha256"], "toolchain_manifest_sha256": hashlib.sha256(b"toolchain").hexdigest()},
        ],
    }
    runs_path = root / "release_reproducibility_runs.json"; _write(runs_path, runs)
    repro, trust = _signed({"schema_version": "release_reproducibility_attestation_v1", "runs_sha256": _sha(runs_path), "package_sha256": package_report["package_sha256"]}, key=key)
    _write(root / "release_reproducibility_attestation.json", repro)
    _write(root / "release_reproducibility_trust.json", {"schema_version": "release_reproducibility_trust_v1", **trust})
    signoffs = {"schema_version": "organizational_signoff_bundle_v1", "approvals": [{"lane": lane, "decision": "approved", "authorization_evidence_sha256": hashlib.sha256(lane.encode()).hexdigest()} for lane in REQUIRED_SIGNOFF_LANES]}
    signoff_path = root / "organizational_signoff_bundle.json"; _write(signoff_path, signoffs)
    signoff_attestation, signoff_trust = _signed({"schema_version": "organizational_signoff_attestation_v1", "bundle_sha256": _sha(signoff_path)}, key=key)
    _write(root / "organizational_signoff_attestation.json", signoff_attestation)
    _write(root / "organizational_signoff_trust.json", {"schema_version": "organizational_signoff_trust_v1", **signoff_trust})
    decision = {"schema_version": "enterprise_ga_evidence_manifest_v1", "evidence": [{"category": category, "status": "pass", "external_attested": True, "sha256": hashlib.sha256(category.encode()).hexdigest()} for category in REQUIRED_DECISION_EVIDENCE]}
    decision_path = root / "enterprise_ga_evidence_manifest.json"; _write(decision_path, decision)
    decision_attestation, decision_trust = _signed({"schema_version": "enterprise_ga_evidence_attestation_v1", "manifest_sha256": _sha(decision_path)}, key=key)
    _write(root / "enterprise_ga_evidence_attestation.json", decision_attestation)
    _write(root / "enterprise_ga_evidence_trust.json", {"schema_version": "enterprise_ga_evidence_trust_v1", **decision_trust})
    return package_report, key


def test_pass196_197_exact_package_sbom_and_signed_reproducibility_contract(tmp_path: Path) -> None:
    package = tmp_path / "Fictional_8.0.0.0_x64.msix"; _package(package)
    external = tmp_path / "external-release-evidence"; package_report, _key = _closure_bundle(external, package)
    assert package_report["license_status"] == "pass"
    assert package_report["vulnerability_status"] == "pass"
    assert set(package_report["sbom_artifacts"]) == {"exact-source-sbom.json", "exact-msix-sbom.json"}
    exact_msix = json.loads((external / "exact-msix-sbom.json").read_text(encoding="utf-8"))
    assert exact_msix["package_sha256"] == package_report["package_sha256"]
    assert exact_msix["license_notice_members"] == ["THIRD_PARTY_NOTICES.txt"]
    report = ReleaseReproducibilityGate(project_root=ROOT).verify(
        evidence_root=external, package_report=PackageSbomGate(project_root=ROOT).audit(package=package, evidence_root=external)
    ).as_dict()
    assert report["status"] == "pass", report
    assert report["independent_run_count"] == 2
    assert report["attestation_verified"] is True
    altered = json.loads((external / "release_reproducibility_runs.json").read_text(encoding="utf-8"))
    altered["runs"][1]["package_sha256"] = "0" * 64
    _write(external / "release_reproducibility_runs.json", altered)
    blocked = ReleaseReproducibilityGate(project_root=ROOT).verify(
        evidence_root=external, package_report=PackageSbomGate(project_root=ROOT).audit(package=package, evidence_root=external)
    ).as_dict()
    assert blocked["status"] == "blocked"
    assert "release_reproducibility_package_hash_mismatch" in blocked["blockers"]


def test_pass198_200_incident_signoffs_and_decision_remain_honest(tmp_path: Path) -> None:
    package = tmp_path / "Fictional_8.0.0.0_x64.msix"; _package(package)
    external = tmp_path / "external-release-evidence"; _closure_bundle(external, package)
    tabletop = IncidentResponseProgram().tabletop("fictional_private_record_exposure")
    assert tabletop["status"] == "fictional_tabletop_completed_review_required"
    assert tabletop["operational_drill_verified"] is False
    signoffs = OrganizationalSignoffGate(project_root=ROOT).verify(evidence_root=external).as_dict()
    assert set(signoffs["approved_lanes"]) == set(REQUIRED_SIGNOFF_LANES)
    assert signoffs["attestation_verified"] is True
    assert signoffs["status"] == "blocked"
    assert "external_organizational_authority_validation_required" in signoffs["blockers"]
    decision = EnterpriseDecisionPacket(project_root=ROOT).assemble(evidence_root=external).as_dict()
    assert set(decision["evidence_categories_present"]) == set(REQUIRED_DECISION_EVIDENCE)
    assert decision["attestation_verified"] is True
    assert decision["store_ga_decision"] == "STORE_GA_BLOCKED"
    assert decision["enterprise_ga_decision"] == "ENTERPRISE_GA_BLOCKED"


def test_pass196_200_production_routes_protect_tenant_and_redact_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from app.api.contracts import EndpointInventory
    from app.api.production import app

    package = tmp_path / "Fictional_8.0.0.0_x64.msix"; _package(package)
    external = tmp_path / "external-release-evidence"; _closure_bundle(external, package)
    monkeypatch.setenv("MFL_RELEASE_CLOSURE_MSIX_PATH", str(package))
    monkeypatch.setenv("MFL_RELEASE_CLOSURE_EVIDENCE_ROOT", str(external))
    client = TestClient(app)
    assert client.get("/api/release-provenance/status", headers={"X-User-Role": "reviewer"}).status_code == 403
    headers = {"X-User-Role": "reviewer", "X-Tenant-Id": "fictional_tenant"}
    provenance = client.post("/api/release-provenance/audit", headers=headers)
    assert provenance.status_code == 200
    assert provenance.json()["status"] == "pass", provenance.json()
    repro = client.post("/api/release-reproducibility/verify", headers=headers)
    assert repro.status_code == 200 and repro.json()["status"] == "pass", repro.json()
    tabletop = client.post("/api/incident-response/tabletop", headers=headers, json={"scenario_id": "fictional_malicious_document"})
    assert tabletop.status_code == 200 and tabletop.json()["status"] == "fictional_tabletop_completed_review_required"
    decision = client.post("/api/enterprise-ga-decision/assemble", headers=headers)
    assert decision.status_code == 200 and decision.json()["enterprise_ga_decision"] == "ENTERPRISE_GA_BLOCKED"
    assert str(tmp_path) not in json.dumps({"provenance": provenance.json(), "repro": repro.json(), "decision": decision.json()})
    registered = {(method, str(route.path)) for route in app.routes for method in (getattr(route, "methods", None) or set()) if method not in {"HEAD", "OPTIONS"}}
    assert EndpointInventory().compare_to_registered(registered, surface="production")["status"] == "pass"
    for relative in ("src/maine_family_law_llm/ui/workbench.js", "maine_family_law_llm/ui/workbench.js"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "enterprise-release-closure-control" in text
        assert "/api/enterprise-ga-decision/assemble" in text
