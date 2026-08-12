from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.web.ui_contracts import REQUIRED_UI_MARKERS
from app.web.ui_inventory import UIViewInventory
from legal.governance import GovernanceControlCenterService
from maine_family_law_llm import api as api_module


ROOT = Path(__file__).resolve().parents[1]


def _service(tmp_path: Path) -> GovernanceControlCenterService:
    return GovernanceControlCenterService(ROOT, evidence_root=tmp_path / "governance-evidence")


def _headers(role: str = "reviewer") -> dict[str, str]:
    return {"X-User-Role": role, "X-Tenant-Id": "tenant-a", "host": "testserver"}


def test_governance_control_registry_framework_mapping_and_cards(tmp_path: Path) -> None:
    service = _service(tmp_path)

    controls = service.control_registry()
    assert controls["status"] == "pass"
    by_id = {row["control_id"]: row for row in controls["controls"]}
    assert by_id["authentication"]["implementation_status"] == "implemented_and_tested"
    assert by_id["vendor_risk_review"]["implementation_status"] == "partially_implemented"
    assert by_id["sign_off_matrix"]["implementation_status"] == "evidence_missing"
    assert by_id["sign_off_matrix"]["release_blocking_status"] is True
    assert by_id["authentication"]["evidence_hashes"]

    frameworks = service.framework_mappings()
    assert frameworks["status"] == "pass"
    assert any(row["framework"] == "NIST AI RMF" for row in frameworks["framework_rows"])
    assert any(row["framework"] == "OWASP LLM" for row in frameworks["framework_rows"])

    models = service.model_cards()
    assert models["status"] == "pass"
    assert models["model_count"] >= 1
    assert all(len(str(card["artifact_hash"])) == 64 for card in models["cards"])

    data_cards = service.data_cards()
    assert data_cards["status"] == "pass"
    assert {card["data_class"] for card in data_cards["cards"]} >= {
        "authority_store",
        "parsed_authority",
        "private_matter_store",
        "audit",
    }

    vendors = service.vendor_risks()
    assert vendors["status"] == "pass"
    assert any(row["vendor_project"] == "openai" for row in vendors["vendor_risks"])


def test_policy_pack_workflow_blocks_weakening_and_keeps_history(tmp_path: Path) -> None:
    service = _service(tmp_path)

    weakened = service.draft_policy_pack("attorney", {"baseline_guardrails": {"no_fake_authority": False}})
    assert weakened["status"] == "failed"
    assert "baseline_guardrail:no_fake_authority" in weakened["blockers"]

    draft = service.draft_policy_pack(
        "attorney",
        {
            "sharing_modes": ["local_only"],
            "exports": ["review_required_only"],
        },
    )
    assert draft["status"] == "draft"
    pack_id = draft["policy_pack"]["pack_id"]

    review = service.review_policy_pack(pack_id, reviewer="admin", decision="approve", reason="safe pack")
    assert review["status"] == "pass"

    activation = service.activate_policy_pack(pack_id, reviewer="admin", reason="release check")
    assert activation["status"] == "blocked"
    assert activation["blockers"]

    rollback = service.rollback_policy_pack(pack_id, reviewer="admin", reason="revert")
    assert rollback["status"] == "pass"

    history = service.history_report()
    assert history["history"]["status"] == "pass"
    assert history["history"]["event_count"] >= 4


def test_exceptions_signoffs_and_diligence_packet_are_redacted(tmp_path: Path) -> None:
    service = _service(tmp_path)

    exceptions = service.exceptions()
    assert any(row["expired"] for row in exceptions["exceptions"])

    signoff = service.record_sign_off(
        {
            "role": "product_owner",
            "build_release_id": "release-2026.08.08",
            "scope": "governance_readiness",
            "evidence_reviewed": ["configs/maine_governance_compliance_packet.json"],
            "approve": True,
            "conditions": "Cannot override deterministic gates.",
            "expiration": "2026-09-30T00:00:00Z",
        }
    )
    assert signoff["status"] == "blocked"
    assert signoff["sign_off"]["unresolved_gaps"]

    packet = service.diligence_packet()
    serialized = json.dumps(packet, sort_keys=True)
    assert packet["status"] == "pass"
    assert len(packet["artifact_hashes"]["control_registry_hash"]) == 64
    assert ROOT.as_posix() not in serialized
    assert "api_key" not in serialized.casefold()
    assert "password" not in serialized.casefold()


def test_governance_api_roles_and_ui_markers(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MFL_GOVERNANCE_EVIDENCE_ROOT", str(tmp_path / "governance-evidence"))
    client = TestClient(api_module.app)
    reviewer_headers = _headers("reviewer")
    admin_headers = _headers("admin")

    controls = client.get("/api/governance/controls", headers=reviewer_headers)
    assert controls.status_code == 200
    assert controls.json()["review_required"] is True

    denied = client.post(
        "/api/governance/policy-packs/draft",
        headers=reviewer_headers,
        json={"role": "attorney", "overrides": {"sharing_modes": ["local_only"]}},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"] == "admin_role_required"

    drafted = client.post(
        "/api/governance/policy-packs/draft",
        headers=admin_headers,
        json={"role": "attorney", "overrides": {"sharing_modes": ["local_only"], "exports": ["review_required_only"]}},
    )
    assert drafted.status_code == 200
    pack_id = drafted.json()["policy_pack"]["pack_id"]

    compare = client.post(
        "/api/governance/policy-packs/compare",
        headers=reviewer_headers,
        json={"base_pack_id": "policy-pack-attorney", "target_pack_id": pack_id},
    )
    assert compare.status_code == 200
    assert compare.json()["review_required"] is True

    sign_off = client.post(
        "/api/governance/sign-offs",
        headers=reviewer_headers,
        json={
            "role": "product_owner",
            "build_release_id": "release-2026.08.08",
            "scope": "governance_readiness",
            "evidence_reviewed": ["configs/maine_governance_compliance_packet.json"],
            "approve": True,
        },
    )
    assert sign_off.status_code == 200
    assert sign_off.json()["status"] == "blocked"

    packet = client.get("/api/governance/diligence-packet", headers=reviewer_headers)
    assert packet.status_code == 200
    assert packet.json()["review_required"] is True

    page = (ROOT / "app/web/pages/governance-policy-center.tsx").read_text(encoding="utf-8")
    for marker in (
        REQUIRED_UI_MARKERS["governance_control_registry"],
        REQUIRED_UI_MARKERS["framework_mappings"],
        REQUIRED_UI_MARKERS["policy_library"],
        REQUIRED_UI_MARKERS["policy_packs"],
        REQUIRED_UI_MARKERS["model_cards"],
        REQUIRED_UI_MARKERS["data_cards"],
        REQUIRED_UI_MARKERS["vendor_risks"],
        REQUIRED_UI_MARKERS["exceptions"],
        REQUIRED_UI_MARKERS["sign_offs"],
        REQUIRED_UI_MARKERS["diligence_packet"],
        REQUIRED_UI_MARKERS["gaps_remediation"],
        REQUIRED_UI_MARKERS["governance_history"],
    ):
        assert marker in page

    inventory = UIViewInventory(ROOT / "app/web/pages").validate()
    assert inventory["status"] == "pass"
    assert "governance-policy-center.tsx" in {view["file"] for view in inventory["views"]}
