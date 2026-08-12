from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.web.ui_inventory import UIViewInventory
from maine_family_law_llm import api as api_module


def _client(monkeypatch, case_root: Path) -> TestClient:
    monkeypatch.setattr(api_module, "active_case_root", lambda: case_root)
    return TestClient(api_module.app)


def _headers() -> dict[str, str]:
    return {"X-User-Role": "attorney", "X-Tenant-Id": "tenant-child"}


def _child_payload() -> dict[str, object]:
    return {
        "child_name": "Ada Lovelace",
        "date_of_birth": "2016-05-08",
        "school_name": "Maine Community School",
        "medical_care": "Pediatric follow-up",
        "school_notes": "School attendance and pickup notes remain local.",
        "care_notes": "After-school care change after Tuesday.",
        "routines_notes": "Bedtime remains consistent on school nights.",
        "transportation_notes": "Exchange route changes stay documented.",
        "contact_notes": "Sibling phone call window stays separate from school pickup.",
        "source_refs": [{"source_id": "doc-1", "source_hash": "a" * 64, "source_span": {"start": 12, "end": 47}}],
    }


def test_child_continuity_workbench_lifecycle_and_export_are_masked_and_hash_bound(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "case"
    case_root.mkdir()
    client = _client(monkeypatch, case_root)

    created = client.post("/api/children", json=_child_payload(), headers=_headers())
    assert created.status_code == 200
    created_payload = created.json()
    child = created_payload["child"]
    child_id = child["child_id"]
    assert child["profile"]["sensitive_fields_masked"] is True
    assert child["profile"]["child_alias"].startswith("Child ")
    assert "Ada Lovelace" not in json.dumps(created_payload)

    school = client.post(
        f"/api/children/{child_id}/events",
        json={
                "event_type": "appointment",
                "category": "school",
                "label": "Attendance review",
                "date": "2026-08-05",
                "status": "missed",
                "details": "The note says the visit may have been rescheduled.",
                "source_span": {"source_id": "doc-1", "source_hash": "a" * 64, "start": 5, "end": 42},
            },
        headers=_headers(),
    )
    assert school.status_code == 200
    school_event = school.json()["event"]
    assert school_event["review_required"] is True
    assert school_event["status"] == "missed_or_rescheduled"

    care = client.post(
        f"/api/children/{child_id}/events",
        json={
            "event_type": "care",
            "category": "care",
            "label": "After-school care",
            "date": "2026-08-05",
            "status": "attended",
            "details": "Synthetic care handoff.",
            "source_span": {"source_id": "doc-2", "source_hash": "b" * 64, "start": 10, "end": 44},
        },
        headers=_headers(),
    )
    assert care.status_code == 200

    service = client.post(
        f"/api/children/{child_id}/events",
        json={
            "event_type": "service",
            "category": "services",
            "label": "Therapy check-in",
            "date": "2026-08-06",
            "status": "unknown",
            "details": "Synthetic service coordination record.",
            "source_span": {"source_id": "doc-3", "source_hash": "c" * 64, "start": 20, "end": 61},
        },
        headers=_headers(),
    )
    assert service.status_code == 200

    transportation = client.post(
        f"/api/children/{child_id}/events",
        json={
            "event_type": "transportation",
            "category": "transportation",
            "label": "Pickup route",
            "date": "2026-08-07",
            "status": "changed",
            "details": "Route changed after a weather delay.",
            "source_span": {"source_id": "doc-4", "source_hash": "d" * 64, "start": 7, "end": 39},
        },
        headers=_headers(),
    )
    assert transportation.status_code == 200

    contact = client.post(
        f"/api/children/{child_id}/events",
        json={
            "event_type": "contact",
            "category": "contact",
            "label": "Sibling contact",
            "date": "2026-08-07",
            "status": "unknown",
            "details": "User-entered note only.",
            "user_entered": True,
        },
        headers=_headers(),
    )
    assert contact.status_code == 200

    with_source = client.patch(
        f"/api/children/{child_id}/events/{school_event['event_id']}",
        json={"details": "Updated school note.", "source_span": {"source_id": "doc-1", "source_hash": "a" * 64, "start": 6, "end": 43}},
        headers=_headers(),
    )
    assert with_source.status_code == 200
    assert with_source.json()["event"]["updated_at"]

    continuity = client.get(f"/api/children/{child_id}/continuity", headers=_headers())
    assert continuity.status_code == 200
    continuity_payload = continuity.json()
    assert continuity_payload["review_required"] is True
    assert continuity_payload["no_custody_score"] is True
    assert continuity_payload["no_diagnosis"] is True
    assert continuity_payload["gaps"]
    assert any(gap["gap_type"] == "medical_continuity_data_missing" for gap in continuity_payload["gaps"])

    school_summary = client.get(f"/api/children/{child_id}/school", headers=_headers())
    care_summary = client.get(f"/api/children/{child_id}/care", headers=_headers())
    services_summary = client.get(f"/api/children/{child_id}/services", headers=_headers())
    gaps_summary = client.get(f"/api/children/{child_id}/gaps", headers=_headers())
    assert school_summary.json()["count"] >= 1
    assert care_summary.json()["count"] >= 1
    assert services_summary.json()["count"] >= 1
    assert gaps_summary.json()["gaps"]

    schedule = client.post(
        f"/api/children/{child_id}/schedule-scenarios",
        json={
            "scenarios": [
                {"title": "School-night handoffs", "exchanges": 3, "commute_minutes": 24, "notes": "Keep routine consistent."},
                {"title": "Low-disruption weekend", "exchanges": 1, "commute_minutes": 12, "notes": "Neutral comparison only."},
            ]
        },
        headers=_headers(),
    )
    assert schedule.status_code == 200
    schedule_payload = schedule.json()
    assert schedule_payload["neutral_schedule_calculation"] is True
    assert schedule_payload["no_parent_ranking"] is True
    assert all(item["review_required"] for item in schedule_payload["scenarios"])

    claims = client.post(
        f"/api/children/{child_id}/claims/review",
        json={
            "claims": [
                {
                    "statement": "The pickup changed after the weather delay.",
                    "scope": "transportation",
                    "supporting_event_ids": [transportation.json()["event"]["event_id"]],
                    "contradicting_event_ids": [care.json()["event"]["event_id"]],
                    "missing_context": ["Weather log"],
                    "qualified_by": ["Subject to the written schedule"],
                    "alternatives": ["A route swap may have been used"],
                    "reviewer_decision": "needs_more_context",
                }
            ]
        },
        headers=_headers(),
    )
    assert claims.status_code == 200
    claims_payload = claims.json()
    assert claims_payload["child_impact_lens"] is True
    assert claims_payload["no_custody_score"] is True
    assert claims_payload["no_diagnosis"] is True
    assert claims_payload["claims"][0]["supporting_events"]
    assert claims_payload["claims"][0]["contradicting_events"]

    packet = client.post(
        f"/api/children/{child_id}/packet",
        json={"approved": True},
        headers=_headers(),
    )
    assert packet.status_code == 200
    packet_payload = packet.json()
    assert packet_payload["receipt"]["receipt_sha256"]
    assert packet_payload["manifest"]["manifest_sha256"]
    assert packet_payload["artifacts"][0]["relative_path"].startswith(packet_payload["build_id"])
    serialized = json.dumps(packet_payload)
    assert str(case_root) not in serialized
    assert "Ada Lovelace" not in serialized

    export_dir = case_root / "19_CHILD_CONTINUITY_WORKBENCH" / "exports" / packet_payload["build_id"]
    assert (export_dir / "child-focused-evidence-packet.json").exists()
    assert (export_dir / "child-focused-evidence-packet.txt").exists()
    assert (export_dir / "child-continuity-packet.json").exists()
    assert (export_dir / "child-continuity-packet.txt").exists()
    assert (export_dir / "child-continuity-receipt.json").exists()
    assert (export_dir / "child-continuity-summary.json").exists()
    assert (export_dir / "child-continuity-summary.txt").exists()

    state_path = case_root / "19_CHILD_CONTINUITY_WORKBENCH" / "children" / child_id / "child-workbench.json.enc"
    assert state_path.exists()
    raw_state = state_path.read_text(encoding="utf-8")
    assert "Ada Lovelace" not in raw_state
    assert "2016-05-08" not in raw_state

    listing = client.get("/api/children", headers=_headers())
    assert listing.status_code == 200
    assert listing.json()["child_count"] == 1


def test_child_continuity_workbench_requires_source_spans_or_user_entered_and_stays_case_scoped(monkeypatch, tmp_path: Path) -> None:
    case_a = tmp_path / "case-a"
    case_b = tmp_path / "case-b"
    case_a.mkdir()
    case_b.mkdir()

    client_a = _client(monkeypatch, case_a)
    child_id = client_a.post("/api/children", json=_child_payload(), headers=_headers()).json()["child"]["child_id"]

    blocked = client_a.post(
        f"/api/children/{child_id}/events",
        json={"event_type": "contact", "category": "contact", "label": "No source", "details": "Missing source and user flag."},
        headers=_headers(),
    )
    assert blocked.status_code == 400

    allowed = client_a.post(
        f"/api/children/{child_id}/events",
        json={"event_type": "contact", "category": "contact", "label": "User entry", "details": "User entered only.", "user_entered": True},
        headers=_headers(),
    )
    assert allowed.status_code == 200

    monkeypatch.setattr(api_module, "active_case_root", lambda: case_b)
    client_b = TestClient(api_module.app)
    assert client_b.get(f"/api/children/{child_id}", headers=_headers()).status_code == 404


def test_child_continuity_ui_contracts_and_navigation_expose_the_shipped_workbench() -> None:
    pages_dir = Path("app/web/pages")
    page = pages_dir / "child-continuity.tsx"
    text = page.read_text(encoding="utf-8")
    assert "Child-Centered Continuity and Logistics" in text
    assert "data-child-profile=\"visible\"" in text
    assert "data-health-care=\"visible\"" in text
    assert "data-child-focused-packet=\"visible\"" in text
    assert "/child-continuity" in Path("app/web/src/App.tsx").read_text(encoding="utf-8")
    assert UIViewInventory(pages_dir).validate()["status"] == "pass"
