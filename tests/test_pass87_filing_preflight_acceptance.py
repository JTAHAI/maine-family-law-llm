from pathlib import Path

from fastapi.testclient import TestClient

from legal.matter.filing_preflight import FilingPreflightStore
from maine_family_law_llm import api as api_module


def _records():
    return [{"evidence_id": "ATTACHMENT-001", "title": "Fictional proposed attachment", "source_locator": "fictional-attachment.pdf", "source_hash": "a" * 64, "page_number": 1, "text": "Fictional attachment."}]


def _form(freshness: str = "fresh"):
    return {"authority_id": "authority_001", "source_id": "fictional-official-form", "source_hash": "b" * 64, "citation": "Fictional official form fixture", "title": "Fictional form", "exact_span": "Fictional source span.", "freshness_status": freshness}


def _payload():
    return {"preflight_id": "preflight_001", "reviewer_safe_id": "reviewer_001", "caption_label": "Fictional caption review", "attachments": [{"record_id": "ATTACHMENT-001", "source_hash": "a" * 64, "page_number": 1, "declared_format": "pdf"}], "form_source_ids": ["fictional-official-form"], "checks": {"caption_confirmed": True, "names_confirmed": True, "signatures_confirmed": True, "format_confirmed": True, "redactions_confirmed": True, "privacy_review_complete": True, "human_review_complete": True}, "document_id": "", "user_confirmed": True}


def test_pass87_encrypted_preflight_binds_attachment_and_keeps_canonical_gate_blocker(tmp_path: Path):
    root = tmp_path / "fictional-matter"; root.mkdir()
    store = FilingPreflightStore(root, encryption_key="fictional-test-key")
    preflight = store.create(_payload() | {"canonical_packet_gate_seen": False}, records=_records(), forms=[_form()])
    assert preflight["filing_ready"] is False and preflight["submission_attempted"] is False
    assert "canonical_reviewed_filing_packet_not_seen" in preflight["blockers"]
    assert preflight["attachments"][0]["lane"] == "private_matter_record"
    assert preflight["forms"][0]["lane"] == "official_authority"
    assert "Fictional proposed attachment" not in store.path.read_text(encoding="utf-8")
    assert store.source("preflight_001", "private_matter_record", "ATTACHMENT-001")["source"]["source_hash"] == "a" * 64


def test_pass87_refuses_unconfirmed_foreign_and_marks_stale_forms(tmp_path: Path):
    root = tmp_path / "fictional-matter"; root.mkdir()
    store = FilingPreflightStore(root, encryption_key="fictional-test-key")
    try:
        store.create(_payload() | {"user_confirmed": False}, records=_records(), forms=[_form()])
    except Exception as exc:
        assert str(exc) == "filing_preflight_confirmation_required"
    else:
        raise AssertionError("preflight confirmation is required")
    foreign = _payload(); foreign["attachments"] = [{"record_id": "FOREIGN", "source_hash": "a" * 64}]
    try:
        store.create(foreign | {"canonical_packet_gate_seen": False}, records=_records(), forms=[_form()])
    except Exception as exc:
        assert str(exc) == "preflight_attachment_not_in_active_matter"
    else:
        raise AssertionError("foreign attachment must fail closed")
    stale = store.create(_payload() | {"preflight_id": "preflight_002", "canonical_packet_gate_seen": False}, records=_records(), forms=[_form("stale")])
    assert "stale_or_unknown_form" in stale["blockers"]


def test_pass87_canonical_api_reresolves_forms_and_scopes_sources(monkeypatch, tmp_path: Path):
    matter_a, matter_b = tmp_path / "matter-a", tmp_path / "matter-b"; matter_a.mkdir(); matter_b.mkdir()
    active = {"root": matter_a}
    monkeypatch.setattr(api_module, "active_case_root", lambda: active["root"])
    monkeypatch.setattr(api_module, "load_case_search_records", lambda _root: _records())
    monkeypatch.setattr(api_module, "inspect_source", lambda _source: {"status": "pass", "source_card": {**_form(), "source_span_preview": "Fictional source span."}})
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-test-key")
    client = TestClient(api_module.app)
    created = client.post("/api/filing-preflights", json=_payload())
    assert created.status_code == 200
    preflight = created.json()["preflight"]
    assert "canonical_reviewed_filing_packet_not_seen" in preflight["blockers"]
    attachment = client.get("/api/filing-preflights/preflight_001/private_matter_record/ATTACHMENT-001/source")
    assert attachment.status_code == 200 and len(attachment.json()["source"]["source_token"]) == 64
    form = client.get(f"/api/filing-preflights/preflight_001/official_authority/{preflight['forms'][0]['authority_id']}/source")
    assert form.status_code == 200 and form.json()["source"]["citation"] == "Fictional official form fixture"
    active["root"] = matter_b
    assert client.get("/api/filing-preflights/preflight_001").status_code == 404


def test_pass87_production_assets_are_mirrored_and_operable():
    assert Path("src/maine_family_law_llm/api.py").read_bytes() == Path("maine_family_law_llm/api.py").read_bytes()
    assert Path("src/maine_family_law_llm/ui/workbench.js").read_bytes() == Path("maine_family_law_llm/ui/workbench.js").read_bytes()
    text = Path("src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    assert "Filing package preflight" in text
    assert "/api/filing-preflights" in text
    assert "Create blocker preflight" in text and "Open attachment record" in text
