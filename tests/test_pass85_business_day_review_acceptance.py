from pathlib import Path

from fastapi.testclient import TestClient

from legal.matter.business_day_review import BusinessDayReviewStore
from maine_family_law_llm import api as api_module


def _authority():
    return {
        "authority_id": "authority_001",
        "source_id": "fictional-official-calendar-source",
        "source_hash": "a" * 64,
        "citation": "Fictional Maine calendar authority fixture",
        "title": "Fictional official calendar source",
        "exact_span": "Fictional exact source span.",
        "freshness_status": "fresh",
    }


def _input_payload():
    return {
        "input_id": "calendar_2026a",
        "calendar_key": "maine_family_court",
        "version_label": "Fictional reviewer-entered 2026 calendar",
        "jurisdiction_label": "Fictional Maine review context",
        "reviewer_safe_id": "reviewer_001",
        "valid_from": "2026-01-01",
        "valid_through": "2026-12-31",
        "holidays": ["2026-01-05"],
        "authority_source_id": "fictional-official-calendar-source",
        "user_confirmed": True,
    }


def _calculation_payload():
    return {
        "calculation_id": "business_calc_001",
        "input_id": "calendar_2026a",
        "reviewer_safe_id": "reviewer_001",
        "start_date": "2026-01-02",
        "business_days": 3,
        "user_confirmed": True,
    }


def test_pass85_encrypted_versioned_input_produces_bound_business_day_receipt(tmp_path: Path):
    root = tmp_path / "fictional-matter"; root.mkdir()
    store = BusinessDayReviewStore(root, encryption_key="fictional-test-key")
    input_row = store.create_input(_input_payload(), authority=_authority())
    calculation = store.calculate(_calculation_payload())
    assert input_row["input_hash"] == calculation["input_hash"]
    assert calculation["candidate_date"] == "2026-01-08"
    assert "2026-01-03" in calculation["skipped_non_business_dates"]
    assert "2026-01-05" in calculation["skipped_non_business_dates"]
    assert calculation["review_required"] is True and calculation["deadline_determined"] is False
    assert "Fictional reviewer-entered" not in store.path.read_text(encoding="utf-8")
    assert store.authority_source("calendar_2026a")["source"]["lane"] == "official_authority"


def test_pass85_refuses_unconfirmed_invalid_date_and_missing_input(tmp_path: Path):
    root = tmp_path / "fictional-matter"; root.mkdir()
    store = BusinessDayReviewStore(root, encryption_key="fictional-test-key")
    try:
        store.create_input(_input_payload() | {"user_confirmed": False}, authority=_authority())
    except Exception as exc:
        assert str(exc) == "business_day_input_confirmation_required"
    else:
        raise AssertionError("calendar input confirmation is required")
    invalid = _input_payload(); invalid["holidays"] = ["not-a-date"]
    try:
        store.create_input(invalid, authority=_authority())
    except Exception as exc:
        assert str(exc) == "business_day_holiday_invalid"
    else:
        raise AssertionError("malformed holiday date must fail closed")
    try:
        store.calculate(_calculation_payload())
    except Exception as exc:
        assert str(exc) == "business_day_input_not_found"
    else:
        raise AssertionError("calculation without a versioned input must fail closed")
    store.create_input(_input_payload(), authority=_authority())
    try:
        store.calculate(_calculation_payload() | {"start_date": "2027-01-02"})
    except Exception as exc:
        assert str(exc) == "business_day_start_outside_input"
    else:
        raise AssertionError("a calculation outside the input version must fail closed")


def test_pass85_canonical_api_revalidates_authority_and_scopes_state(monkeypatch, tmp_path: Path):
    matter_a, matter_b = tmp_path / "matter-a", tmp_path / "matter-b"; matter_a.mkdir(); matter_b.mkdir()
    active = {"root": matter_a}
    monkeypatch.setattr(api_module, "active_case_root", lambda: active["root"])
    monkeypatch.setattr(api_module, "inspect_source", lambda _source: {"status": "pass", "source_card": {**_authority(), "source_span_preview": "Fictional exact source span."}})
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-test-key")
    client = TestClient(api_module.app)
    saved = client.post("/api/business-day-calendar-inputs", json=_input_payload())
    assert saved.status_code == 200 and saved.json()["input"]["input_hash"]
    calculated = client.post("/api/business-day-calculations", json=_calculation_payload())
    assert calculated.status_code == 200 and calculated.json()["calculation"]["candidate_date"] == "2026-01-08"
    source = client.get("/api/business-day-calendar-inputs/calendar_2026a/authority/source")
    assert source.status_code == 200 and source.json()["source"]["citation"] == "Fictional Maine calendar authority fixture"
    active["root"] = matter_b
    assert client.get("/api/business-day-calendar-inputs/calendar_2026a").status_code == 404


def test_pass85_production_assets_are_mirrored_and_operable():
    assert Path("src/maine_family_law_llm/api.py").read_bytes() == Path("maine_family_law_llm/api.py").read_bytes()
    assert Path("src/maine_family_law_llm/ui/workbench.js").read_bytes() == Path("maine_family_law_llm/ui/workbench.js").read_bytes()
    text = Path("src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    assert "Business-day review" in text
    assert "/api/business-day-calendar-inputs" in text and "/api/business-day-calculations" in text
    assert "Save versioned calendar input" in text and "Calculate review candidate" in text
