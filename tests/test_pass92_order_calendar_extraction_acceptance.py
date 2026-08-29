from pathlib import Path

from fastapi.testclient import TestClient

from legal.matter.order_calendar_extraction import OrderCalendarExtractionStore
from maine_family_law_llm import api as api_module


def _records():
    return [{"evidence_id": "ORDER-001", "source_hash": "a" * 64, "title": "Fictional order"}]


def _term(confirmed=True):
    return {
        "term_id": "term_001",
        "order_id": "order_001",
        "subject": "holidays",
        "exact_language": "Fictional exact holiday language.",
        "source_ref": {"record_id": "ORDER-001", "source_hash": "a" * 64, "page": 2},
        "operative_candidate_review": {
            "confirmed": confirmed,
            "status": "reviewer_confirmed_candidate" if confirmed else "review_required",
            "reviewer_safe_id": "reviewer_001",
            "reviewed_at": "2026-08-26T00:00:00Z",
        },
    }


def _payload():
    return {"extraction_id": "calendar_candidate_001", "reviewer_safe_id": "reviewer_001", "term_id": "term_001", "date_candidate": "2026-07-04", "label": "Fictional holiday candidate", "user_confirmed": True}


def _order_payload():
    return {"orders": [{"order_id": "order_001", "source_ref": {"record_id": "ORDER-001", "source_hash": "a" * 64, "page": 1}, "caption": "Fictional", "docket_safe_id": "docket_001", "court": "Fictional Court", "order_type": "order", "signed_date": "2026-06-01", "entered_date": "2026-06-01", "effective_date": "2026-06-01", "signature_status": "review_required", "status_candidate": "unknown", "freshness_status": "unknown", "terms": [{"term_id": "term_001", "subject": "holidays", "exact_language": "Fictional exact holiday language.", "source_ref": {"record_id": "ORDER-001", "source_hash": "a" * 64, "page": 2}, "dates": [], "party_safe_labels": [], "conditions": "", "exceptions": "", "parser_warnings": []}]}]}


def test_pass92_encrypted_confirmed_term_candidate(tmp_path: Path):
    root = tmp_path / "fictional-matter"
    root.mkdir()
    store = OrderCalendarExtractionStore(root, encryption_key="fictional-test-key")
    created = store.create(_payload(), terms=[_term()], records=_records())
    assert created["candidate_event"]["calendar_account_write"] is False
    assert created["review_required"] and not created["filing_ready"]
    assert store.source("calendar_candidate_001")["source"]["page"] == 2
    assert "Fictional holiday candidate" not in store.path.read_text(encoding="utf-8")


def test_pass92_api_integrates_order_confirmation_scopes_sources_and_assets(monkeypatch, tmp_path: Path):
    matter_a, matter_b = tmp_path / "matter-a", tmp_path / "matter-b"
    matter_a.mkdir()
    matter_b.mkdir()
    active = {"root": matter_a}
    monkeypatch.setattr(api_module, "active_case_root", lambda: active["root"])
    monkeypatch.setattr(api_module, "load_case_search_records", lambda _: _records())
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-test-key")
    client = TestClient(api_module.app)
    assert client.post("/api/orders", json=_order_payload()).status_code == 200
    assert client.post("/api/orders/operative-candidate-review", json={"term_id": "term_001", "reviewer_safe_id": "reviewer_001", "confirmed": True, "note": "fictional reviewer confirmation"}).status_code == 200
    created = client.post("/api/calendar/order-term-extractions", json=_payload())
    assert created.status_code == 200
    assert client.get("/api/calendar/order-term-extractions/calendar_candidate_001/source").json()["source"]["source_token"]
    active["root"] = matter_b
    assert client.get("/api/calendar/order-term-extractions/calendar_candidate_001").status_code == 404
    assert Path("src/maine_family_law_llm/api.py").read_bytes() == Path("maine_family_law_llm/api.py").read_bytes()
    ui = Path("src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    assert "Order-to-calendar candidate" in ui and "Open exact order source" in ui
