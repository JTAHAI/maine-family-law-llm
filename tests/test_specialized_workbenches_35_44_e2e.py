from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from maine_family_law_llm import api as api_module
from maine_family_law_llm.local_workbench_ui import read_workbench_asset, render_local_workbench_html


def _client(monkeypatch, tmp_path: Path) -> tuple[TestClient, Path]:
    matter = tmp_path / "fictional-matter"
    matter.mkdir()
    monkeypatch.setattr(api_module, "active_case_root", lambda: matter)
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-acceptance-passphrase")
    return TestClient(api_module.app), matter


def test_specialized_workbenches_35_44_support_meaningful_local_actions(
    monkeypatch, tmp_path: Path
) -> None:
    client, matter = _client(monkeypatch, tmp_path)
    actions = [
        ("/api/negotiation/proposals", {"proposals": [{"proposal_id": "proposal_one", "author_role": "party_one", "topics": ["schedule"], "exact_text": "Fictional proposal one.", "source_ref": {"record_id": "record_one"}}]}),
        ("/api/negotiation/proposals", {"proposals": [{"proposal_id": "proposal_two", "author_role": "party_two", "topics": ["schedule"], "exact_text": "Fictional proposal two.", "source_ref": {"record_id": "record_two"}}]}),
        ("/api/property/items", {"items": [{"item_id": "asset_one", "kind": "account", "description": "Fictional asset candidate.", "owner_candidate": "party_one", "value_candidate": "100", "source_ref": {"record_id": "record_one"}}]}),
        ("/api/modification/changes", {"changes": [{"change_id": "change_one", "category": "schedule", "description": "Fictional changed circumstance candidate.", "source_ref": {"record_id": "record_one"}, "disputed": True}]}),
        ("/api/foaa/requests", {"requests": [{"request_id": "request_one", "agency_safe_id": "agency_one", "draft_text": "Fictional public-record request draft.", "scope": "Fictional docket metadata.", "source_refs": [{"record_id": "record_one"}]}]}),
        ("/api/filing-readiness/packages", {"packages": [{"package_id": "package_one", "document_ids": ["record_one"], "court_safe_id": "court_one", "service_proof_candidate": "proof_one"}]}),
        ("/api/image-evidence/items", {"items": [{"image_id": "image_one", "original_hash": "a" * 64, "kind": "screenshot", "source_ref": {"record_id": "record_one"}, "metadata_warning": True}]}),
        ("/api/email-integrity/exports", {"exports": [{"export_id": "export_one", "source_hash": "b" * 64, "header_hash": "c" * 64, "attachment_hashes": ["d" * 64], "format": "eml", "source_ref": {"record_id": "record_one"}}]}),
        ("/api/reviewer-handoff", {"handoff_id": "handoff_one", "record_ids": ["record_one"], "reviewer_safe_id": "reviewer_one", "purpose": "Fictional review handoff."}),
        ("/api/language-access/copies", {"copies": [{"copy_id": "copy_one", "source_record_id": "record_one", "source_hash": "e" * 64, "kind": "plain_language", "target_language": "English", "working_text": "Fictional plain-language working copy."}]}),
        ("/api/resources", {"resources": [{"resource_id": "resource_one", "name": "Fictional Maine Resource", "category": "support", "county_or_region": "Cumberland", "source_url_or_record": "https://example.invalid/fictional", "contact_note": "Verify availability before outreach."}]}),
    ]
    for route, payload in actions:
        response = client.post(route, json=payload)
        assert response.status_code == 200, (route, response.text)
        assert response.json().get("review_required") is True, route
        assert str(matter) not in response.text

    comparison = client.post(
        "/api/negotiation/compare",
        json={"left_id": "proposal_one", "right_id": "proposal_two"},
    )
    assert comparison.status_code == 200
    assert comparison.json()["agreement"] == "not_determined"
    validation = client.get("/api/filing-readiness/package_one/validate")
    assert validation.status_code == 200
    assert validation.json()["automatic_filing"] is False

    inventories = (
        "/api/negotiation/inventory", "/api/property/inventory", "/api/modification/inventory",
        "/api/foaa/inventory", "/api/filing-readiness/inventory", "/api/image-evidence/inventory",
        "/api/email-integrity/inventory", "/api/reviewer-handoff/inventory",
        "/api/language-access/inventory", "/api/resources/inventory",
    )
    for route in inventories:
        response = client.get(route)
        assert response.status_code == 200
        assert response.json()["local_only"] is True
        assert response.json()["review_required"] is True

    encrypted_files = list(matter.rglob("*.enc"))
    assert len(encrypted_files) == 10
    combined = "".join(path.read_text(encoding="utf-8") for path in encrypted_files)
    for private_text in ("Fictional proposal one", "Fictional asset candidate", "Fictional review handoff"):
        assert private_text not in combined


def test_specialized_workbench_ui_has_creation_review_and_exact_source_actions() -> None:
    html = render_local_workbench_html()
    javascript = read_workbench_asset("workbench.js")
    assert 'id="late-review-create"' in html
    assert 'id="late-review-action"' in html
    assert 'id="late-review-source-id"' in html
    for marker in (
        "lateReviewDefinitions", "createLateReviewItem", "runLateReviewAction",
        "installSpecializedSourceInspectors", "openSpecializedSourceRecord",
        "/api/records/${encodeURIComponent(safeId)}/integrity",
        "Review required", "no external action",
    ):
        assert marker in javascript
    for route in (
        "/api/negotiation/proposals", "/api/property/items", "/api/modification/changes",
        "/api/foaa/requests", "/api/filing-readiness/packages", "/api/image-evidence/items",
        "/api/email-integrity/exports", "/api/reviewer-handoff", "/api/language-access/copies",
        "/api/resources",
    ):
        assert route in javascript
    assert "C:\\Users\\" not in json.dumps({"html": html, "javascript": javascript})
