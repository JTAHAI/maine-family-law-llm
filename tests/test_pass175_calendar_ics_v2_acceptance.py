from pathlib import Path

from fastapi.testclient import TestClient

from app.api.production import app as production_app
from legal.matter.calendar_review import CalendarReviewStore
from maine_family_law_llm import api as local_api

def test_pass175_ics_export_has_stable_uid_updates_alarm_and_cancel(tmp_path: Path):
    store=CalendarReviewStore(tmp_path,encryption_key="0123456789abcdef")
    store.add_events({"events":[{"event_id":"hearing_001","kind":"hearing","date_time":"2027-06-15T09:30:00","time_zone":"America/New_York","document_or_notice":"Fictional hearing candidate","source_ref":{"record_id":"record_001","source_hash":"a"*64}}]})
    first=store.ics_export({"export_id":"export_001","event_ids":["hearing_001"],"time_zone":"America/New_York","sequence":2,"alarm_minutes":30,"recurrence_rule":"FREQ=WEEKLY;COUNT=2","status":"CONFIRMED"})
    assert "UID:hearing_001@maine-family-law-llm.local" in first["content"] and "SEQUENCE:2" in first["content"] and "RRULE:FREQ=WEEKLY;COUNT=2" in first["content"] and "BEGIN:VALARM" in first["content"]
    cancelled=store.ics_export({"export_id":"export_002","event_ids":["hearing_001"],"status":"CANCELLED"})
    assert "STATUS:CANCELLED" in cancelled["content"] and "BEGIN:VALARM" not in cancelled["content"]
    assert first["calendar_account_write"] is False and first["automatic_download"] is False


def test_pass175_production_route_denies_viewer_and_ships_control(tmp_path: Path, monkeypatch) -> None:
    matter = tmp_path / "fictional-matter"
    matter.mkdir()
    monkeypatch.setattr(local_api, "active_case_root", lambda: matter)
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-passphrase")
    monkeypatch.setenv("MFL_IDEMPOTENCY_STATE_ROOT", str(tmp_path / "idempotency"))
    client = TestClient(production_app)
    headers = {"X-User-Role": "reviewer", "X-Tenant-Id": "fictional-tenant", "X-MFLL-Client-Session": "g" * 32}
    created = client.post("/api/calendar/events", headers={**headers, "X-MFLL-Idempotency-Key": "pass175-event"}, json={"events":[{"event_id":"hearing_001","kind":"hearing","date_time":"2027-06-15T09:30:00","time_zone":"America/New_York","document_or_notice":"Fictional hearing candidate","source_ref":{"record_id":"record_001","source_hash":"a" * 64}}]})
    assert created.status_code == 200, created.text
    payload = {"export_id":"export_001", "event_ids":["hearing_001"], "status":"CONFIRMED"}
    assert client.post("/api/calendar/ics-export", headers={**headers, "X-User-Role": "viewer", "X-MFLL-Idempotency-Key": "pass175-denied"}, json=payload).status_code == 403
    exported = client.post("/api/calendar/ics-export", headers={**headers, "X-MFLL-Idempotency-Key": "pass175-export"}, json=payload)
    assert exported.status_code == 200, exported.text
    assert "UID:hearing_001@maine-family-law-llm.local" in exported.json()["content"]
    root = Path(__file__).resolve().parents[1]
    for rel in ("src/maine_family_law_llm/ui/workbench.js", "maine_family_law_llm/ui/workbench.js"):
        text = (root / rel).read_text(encoding="utf-8")
        assert "calendar-ics-v2-control" in text and "/api/calendar/ics-export" in text
