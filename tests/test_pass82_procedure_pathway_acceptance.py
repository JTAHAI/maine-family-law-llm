from pathlib import Path

from fastapi.testclient import TestClient

from legal.matter.procedure_pathway import ProcedurePathwayStore
from maine_family_law_llm import api as api_module


def _records():
    return [{"evidence_id": "ORDER-FICTION-001", "title": "Fictional prior order", "source_locator": "fictional-order.pdf", "source_hash": "a" * 64, "page_number": 2, "text": "Fictional order text."}]


def _authority():
    return {"authority_id": "authority_001", "source_id": "fictional-official-source", "source_hash": "b" * 64, "citation": "Fictional Maine authority fixture", "title": "Fictional official authority", "exact_span": "Fictional exact source span.", "freshness_status": "fresh"}


def _payload():
    return {"pathway_id": "procedure_001", "reviewer_safe_id": "reviewer_001", "case_type": "family_matter", "posture": "post_judgment", "venue_label": "Fictional venue note", "existing_orders": [{"record_id": "ORDER-FICTION-001", "source_hash": "a" * 64, "page_number": 2}], "authority_source_id": "fictional-official-source", "user_confirmed": True}


def test_pass82_pathway_is_encrypted_source_bound_and_non_advisory(tmp_path: Path):
    root = tmp_path / "fictional-matter"; root.mkdir()
    store = ProcedurePathwayStore(root, encryption_key="fictional-test-key")
    pathway = store.create(_payload(), records=_records(), authority=_authority())
    assert pathway["review_required"] is True and pathway["filing_ready"] is False
    assert pathway["legal_conclusion"] == "not_determined"
    assert any(step["step_id"] == "change_or_compliance" for step in pathway["steps"])
    assert "Fictional venue note" not in store.path.read_text(encoding="utf-8")
    assert store.source("procedure_001", "private_matter_record", "ORDER-FICTION-001")["source"]["source_hash"] == "a" * 64
    assert store.source("procedure_001", "official_authority", "authority_001")["source"]["source_hash"] == "b" * 64


def test_pass82_refuses_unconfirmed_and_foreign_order(tmp_path: Path):
    root = tmp_path / "fictional-matter"; root.mkdir()
    store = ProcedurePathwayStore(root, encryption_key="fictional-test-key")
    try:
        store.create(_payload() | {"user_confirmed": False}, records=_records(), authority=_authority())
    except Exception as exc:
        assert str(exc) == "procedure_pathway_confirmation_required"
    else:
        raise AssertionError("explicit reviewer confirmation is required")
    foreign = _payload(); foreign["existing_orders"] = [{"record_id": "FOREIGN", "source_hash": "a" * 64}]
    try:
        store.create(foreign, records=_records(), authority=_authority())
    except Exception as exc:
        assert str(exc) == "existing_order_not_in_active_matter"
    else:
        raise AssertionError("foreign order record must fail closed")


def test_pass82_canonical_api_revalidates_authority_and_scopes_sources(monkeypatch, tmp_path: Path):
    matter_a, matter_b = tmp_path / "matter-a", tmp_path / "matter-b"; matter_a.mkdir(); matter_b.mkdir()
    active = {"root": matter_a}
    monkeypatch.setattr(api_module, "active_case_root", lambda: active["root"])
    monkeypatch.setattr(api_module, "load_case_search_records", lambda _root: _records())
    monkeypatch.setattr(api_module, "inspect_source", lambda _source: {"status": "pass", "source_card": {**_authority(), "source_span_preview": "Fictional exact source span."}})
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-test-key")
    client = TestClient(api_module.app)
    created = client.post("/api/procedure-pathways", json=_payload())
    assert created.status_code == 200
    pathway = created.json()["pathway"]
    private = client.get("/api/procedure-pathways/procedure_001/private_matter_record/ORDER-FICTION-001/source")
    assert private.status_code == 200 and len(private.json()["source"]["source_token"]) == 64
    authority_id = pathway["authority"]["authority_id"]
    official = client.get(f"/api/procedure-pathways/procedure_001/official_authority/{authority_id}/source")
    assert official.status_code == 200 and official.json()["source"]["citation"] == "Fictional Maine authority fixture"
    active["root"] = matter_b
    assert client.get("/api/procedure-pathways/procedure_001").status_code == 404


def test_pass82_production_assets_are_mirrored_and_operable():
    assert Path("src/maine_family_law_llm/api.py").read_bytes() == Path("maine_family_law_llm/api.py").read_bytes()
    assert Path("src/maine_family_law_llm/ui/workbench.js").read_bytes() == Path("maine_family_law_llm/ui/workbench.js").read_bytes()
    text = Path("src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    assert "Procedure pathway" in text
    assert "/api/procedure-pathways" in text
    assert "Open known order" in text and "Open official source" in text
