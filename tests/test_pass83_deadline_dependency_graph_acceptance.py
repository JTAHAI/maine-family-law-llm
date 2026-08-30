from pathlib import Path

from fastapi.testclient import TestClient

from legal.matter.calendar_review import CalendarReviewStore
from maine_family_law_llm import api as api_module


def _event(event_id: str, digest: str, when: str) -> dict:
    return {"event_id": event_id, "kind": "completed_service_candidate", "date_time": when, "time_zone": "America/New_York", "document_or_notice": "Fictional service proof", "person_or_role": "fictional role", "method": "unknown", "source_ref": {"record_id": event_id.replace("service", "record"), "source_hash": digest, "page": 1}}


def _rule() -> dict:
    return {"rule_id": "rule_001", "citation": "Fictional source-bound deadline rule", "freshness": "fresh", "triggering_event": "completed_service_candidate", "unit": "days", "count": 7, "inclusion_rule": "review required", "weekend_holiday_handling": "unknown", "source_ref": {"record_id": "rule_source_001", "source_hash": "b" * 64, "page": 1}, "jurisdiction": "Maine"}


def test_pass83_changed_trigger_preserves_prior_candidate(tmp_path: Path):
    root = tmp_path / "fictional-matter"; root.mkdir()
    store = CalendarReviewStore(root, encryption_key="fictional-test-key")
    store.add_events({"events": [_event("service_001", "a" * 64, "2026-01-02T12:00:00"), _event("service_002", "c" * 64, "2026-01-03T12:00:00")]})
    store.add_rules({"rules": [_rule()]})
    first = store.calculate_dependency({"dependency_id": "deadline_001", "rule_id": "rule_001", "trigger_event_id": "service_001", "holidays": [], "user_confirmed": True})
    second = store.calculate_dependency({"dependency_id": "deadline_001", "rule_id": "rule_001", "trigger_event_id": "service_002", "holidays": [], "user_confirmed": True})
    graph = store.dependency("deadline_001")
    assert first["candidate_result"] == "2026-01-09" and second["candidate_result"] == "2026-01-10"
    assert len(graph["calculations"]) == 2
    assert graph["calculations"][0]["active"] is False
    assert graph["active_candidate"]["candidate_id"] == second["candidate_id"]
    assert "Fictional service proof" not in store.path.read_text(encoding="utf-8")


def test_pass83_requires_confirmation_and_bound_trigger_hash(tmp_path: Path):
    root = tmp_path / "fictional-matter"; root.mkdir()
    store = CalendarReviewStore(root, encryption_key="fictional-test-key")
    store.add_events({"events": [_event("service_001", "", "2026-01-02T12:00:00")]})
    store.add_rules({"rules": [_rule()]})
    try:
        store.calculate_dependency({"dependency_id": "deadline_001", "rule_id": "rule_001", "trigger_event_id": "service_001", "user_confirmed": False})
    except Exception as exc:
        assert str(exc) == "deadline_dependency_confirmation_required"
    else:
        raise AssertionError("dependency confirmation must be explicit")
    try:
        store.calculate_dependency({"dependency_id": "deadline_001", "rule_id": "rule_001", "trigger_event_id": "service_001", "user_confirmed": True})
    except Exception as exc:
        assert str(exc) == "deadline_dependency_trigger_hash_required"
    else:
        raise AssertionError("unbound trigger must fail closed")


def test_pass83_canonical_api_checks_active_matter_trigger(monkeypatch, tmp_path: Path):
    matter_a, matter_b = tmp_path / "matter-a", tmp_path / "matter-b"; matter_a.mkdir(); matter_b.mkdir()
    active = {"root": matter_a}
    monkeypatch.setattr(api_module, "active_case_root", lambda: active["root"])
    monkeypatch.setattr(api_module, "load_case_search_records", lambda _root: [{"evidence_id": "record_001", "source_hash": "a" * 64, "source_locator": "fictional-proof.pdf"}])
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-test-key")
    store = CalendarReviewStore(matter_a, encryption_key="fictional-test-key")
    store.add_events({"events": [_event("service_001", "a" * 64, "2026-01-02T12:00:00")]}); store.add_rules({"rules": [_rule()]})
    client = TestClient(api_module.app)
    created = client.post("/api/calendar/deadline-dependencies", json={"dependency_id": "deadline_001", "rule_id": "rule_001", "trigger_event_id": "service_001", "holidays": [], "user_confirmed": True})
    assert created.status_code == 200 and created.json()["candidate_id"]
    assert client.get("/api/calendar/deadline-dependencies/deadline_001").json()["active_candidate"]["active"] is True
    source = client.get("/api/calendar/deadline-dependencies/deadline_001/trigger-source")
    assert source.status_code == 200
    assert source.json()["source"]["record_id"] == "record_001"
    assert len(source.json()["source"]["source_token"]) == 64
    assert "fictional-proof.pdf" not in source.text
    active["root"] = matter_b
    assert client.get("/api/calendar/deadline-dependencies/deadline_001").status_code == 404


def test_pass83_canonical_api_matches_normalized_uppercase_record_id(monkeypatch, tmp_path: Path):
    matter = tmp_path / "matter"; matter.mkdir()
    monkeypatch.setattr(api_module, "active_case_root", lambda: matter)
    monkeypatch.setattr(api_module, "load_case_search_records", lambda _root: [{"evidence_id": "REC-DOCX", "source_hash": "a" * 64, "source_locator": "fictional-proof.docx"}])
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-test-key")
    store = CalendarReviewStore(matter, encryption_key="fictional-test-key")
    store.add_events({"events": [{"event_id": "trigger_upper", "kind": "completed_service_candidate", "date_time": "2026-01-02T12:00:00", "time_zone": "America/New_York", "document_or_notice": "Fictional proof", "person_or_role": "fictional role", "method": "unknown", "source_ref": {"record_id": "REC-DOCX", "source_hash": "a" * 64, "page": 1}}]})
    store.add_rules({"rules": [_rule()]})
    client = TestClient(api_module.app)
    created = client.post("/api/calendar/deadline-dependencies", json={"dependency_id": "deadline_upper", "rule_id": "rule_001", "trigger_event_id": "trigger_upper", "holidays": [], "user_confirmed": True})
    assert created.status_code == 200
    source = client.get("/api/calendar/deadline-dependencies/deadline_upper/trigger-source")
    assert source.status_code == 200 and source.json()["source"]["source_hash"] == "a" * 64
    assert source.json()["source"]["record_id"] == "rec-docx"
    assert store.path.name == "calendar.json.enc"
    assert b"Fictional proof" not in store.path.read_bytes()


def test_pass83_production_ui_assets_are_mirrored_and_operable():
    assert Path("src/maine_family_law_llm/api.py").read_bytes() == Path("maine_family_law_llm/api.py").read_bytes()
    assert Path("src/maine_family_law_llm/ui/workbench.js").read_bytes() == Path("maine_family_law_llm/ui/workbench.js").read_bytes()
    text = Path("src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    assert "Deadline dependency graph" in text
    assert "/api/calendar/deadline-dependencies" in text
    assert "Create / recalculate candidate" in text
    assert "Open exact trigger record" in text
