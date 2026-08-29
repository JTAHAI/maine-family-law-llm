from pathlib import Path

from fastapi.testclient import TestClient

from legal.matter.hearing_countdown import HearingCountdownStore
from maine_family_law_llm import api as api_module


def _records():
    return [{
        "evidence_id": "HEARING-NOTICE-001",
        "title": "Fictional hearing notice",
        "source_locator": "fictional-hearing-notice.pdf",
        "source_hash": "a" * 64,
        "page_number": 2,
        "text": "Fictional notice text.",
    }]


def _payload():
    return {
        "countdown_id": "hearing_countdown_001",
        "reviewer_safe_id": "reviewer_001",
        "hearing_label": "Fictional review hearing",
        "confirmed_date": "2026-02-20",
        "notice_source": {"record_id": "HEARING-NOTICE-001", "source_hash": "a" * 64, "page_number": 2},
        "milestone_offsets": [14, 7, 1, 0],
        "missing_proof_prompts": ["Confirm fictional exhibit source."],
        "user_confirmed": True,
    }


def test_pass86_encrypted_countdown_keeps_source_and_local_prompts(tmp_path: Path):
    root = tmp_path / "fictional-matter"; root.mkdir()
    store = HearingCountdownStore(root, encryption_key="fictional-test-key")
    countdown = store.create(_payload(), records=_records())
    assert [item["candidate_date"] for item in countdown["milestones"]] == ["2026-02-06", "2026-02-13", "2026-02-19", "2026-02-20"]
    assert countdown["review_required"] is True and countdown["court_calendar_write"] is False
    assert countdown["notice_source"]["lane"] == "private_matter_record"
    assert "Fictional hearing notice" not in store.path.read_text(encoding="utf-8")
    assert store.source("hearing_countdown_001")["source"]["source_hash"] == "a" * 64


def test_pass86_refuses_unconfirmed_foreign_and_malformed_source_page(tmp_path: Path):
    root = tmp_path / "fictional-matter"; root.mkdir()
    store = HearingCountdownStore(root, encryption_key="fictional-test-key")
    try:
        store.create(_payload() | {"user_confirmed": False}, records=_records())
    except Exception as exc:
        assert str(exc) == "hearing_countdown_confirmation_required"
    else:
        raise AssertionError("explicit confirmation is required")
    foreign = _payload(); foreign["notice_source"] = {"record_id": "FOREIGN", "source_hash": "a" * 64}
    try:
        store.create(foreign, records=_records())
    except Exception as exc:
        assert str(exc) == "hearing_countdown_notice_not_in_active_matter"
    else:
        raise AssertionError("foreign notice must fail closed")
    malformed = _payload(); malformed["notice_source"] = {"record_id": "HEARING-NOTICE-001", "source_hash": "a" * 64, "page_number": "bad"}
    try:
        store.create(malformed, records=_records())
    except Exception as exc:
        assert str(exc) == "hearing_countdown_notice_page_invalid"
    else:
        raise AssertionError("malformed page data must fail closed")


def test_pass86_canonical_api_scopes_countdown_and_notice_source(monkeypatch, tmp_path: Path):
    matter_a, matter_b = tmp_path / "matter-a", tmp_path / "matter-b"; matter_a.mkdir(); matter_b.mkdir()
    active = {"root": matter_a}
    monkeypatch.setattr(api_module, "active_case_root", lambda: active["root"])
    monkeypatch.setattr(api_module, "load_case_search_records", lambda _root: _records())
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-test-key")
    client = TestClient(api_module.app)
    created = client.post("/api/hearing-countdowns", json=_payload())
    assert created.status_code == 200
    source = client.get("/api/hearing-countdowns/hearing_countdown_001/notice-source")
    assert source.status_code == 200 and len(source.json()["source"]["source_token"]) == 64
    active["root"] = matter_b
    assert client.get("/api/hearing-countdowns/hearing_countdown_001").status_code == 404


def test_pass86_production_assets_are_mirrored_and_operable():
    assert Path("src/maine_family_law_llm/api.py").read_bytes() == Path("maine_family_law_llm/api.py").read_bytes()
    assert Path("src/maine_family_law_llm/ui/workbench.js").read_bytes() == Path("maine_family_law_llm/ui/workbench.js").read_bytes()
    text = Path("src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    assert "Hearing preparation countdown" in text
    assert "/api/hearing-countdowns" in text
    assert "Create local review countdown" in text and "Open exact notice record" in text
