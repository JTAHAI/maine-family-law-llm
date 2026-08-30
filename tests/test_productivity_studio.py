from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main import app as enterprise_app
from app.api.production import ACCEPTED_FEATURE_IDS, app as production_app
from legal.productivity import ProductivitySuiteError, ProductivitySuiteStore
from maine_family_law_llm import api as api_module
from maine_family_law_llm.local_workbench_ui import read_workbench_asset
from maine_family_law_llm.production_ui import production_ui_manifest


HEADERS = {"X-User-Role": "reviewer", "X-Tenant-Id": "tenant-productivity"}
HASH_A = hashlib.sha256(b"record-a").hexdigest()
HASH_B = hashlib.sha256(b"record-b").hexdigest()


@pytest.fixture()
def matter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    root = tmp_path / "fictional-matter"
    root.mkdir()
    (root / "fictional-record.txt").write_text("Only fictional demonstration data.", encoding="utf-8")
    monkeypatch.setattr(api_module, "active_case_root", lambda: root)
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "productivity-suite-test-key")
    monkeypatch.setenv("MFL_BACKUP_ROOT", str(tmp_path / "encrypted-backups"))
    return root


def _post(client: TestClient, path: str, payload: dict) -> dict:
    response = client.post(path, json=payload, headers=HEADERS)
    assert response.status_code == 200, (path, response.text)
    assert response.headers["x-mfll-audit-event-id"]
    data = response.json()
    assert data["review_required"] is True
    assert data["rbac"]["tenant_scoped"] is True
    return data


def test_productivity_studio_ten_capabilities_execute_through_canonical_api(matter: Path) -> None:
    with TestClient(enterprise_app) as client:
        assert client.get("/api/productivity").status_code == 403
        initial = client.get("/api/productivity", headers=HEADERS)
        assert initial.status_code == 200
        assert len(initial.json()["capabilities"]) == 10

        inbox = _post(client, "/api/productivity/inbox/configurations", {
            "inbox_id": "matter_inbox", "label": "Fictional inbox", "watch_token": "local_inbox",
            "allowed_extensions": ["pdf", "docx"],
        })
        assert inbox["automatic_import"] is False
        first_scan = _post(client, "/api/productivity/inbox/matter_inbox/scan", {"candidates": [{
            "record_id": "record_001", "display_name": "Fictional order", "extension": "pdf",
            "sha256": HASH_A, "size": 8,
        }]})
        assert first_scan["new_count"] == 1
        second_scan = _post(client, "/api/productivity/inbox/matter_inbox/scan", {"candidates": [{
            "record_id": "record_002", "display_name": "Exact duplicate", "extension": "pdf",
            "sha256": HASH_A, "size": 8,
        }]})
        assert second_scan["duplicate_count"] == 1

        recipe = _post(client, "/api/productivity/recipes", {
            "recipe_id": "weekly_review", "label": "Weekly review",
            "steps": ["inventory_records", "privacy_scan", "review_blockers"],
        })
        assert recipe["requires_confirmation"] is True
        blocked = client.post("/api/productivity/recipes/weekly_review/run", json={}, headers=HEADERS)
        assert blocked.status_code == 409
        run = _post(client, "/api/productivity/recipes/weekly_review/run", {"confirmed": True})
        assert run["status"] == "completed_review_required"
        assert run["results"][0]["record_count"] >= 1
        assert run["results"][1]["private_text_returned"] is False

        calendar = _post(client, "/api/productivity/calendar/exports", {
            "export_id": "review_dates", "events": [{
                "event_id": "review_event", "date_time": "2026-09-01T09:00:00Z",
                "summary": "Fictional review date", "source_ref": {"record_id": "record_001"},
            }],
        })
        assert calendar["calendar_account_write"] is False
        ics = matter / calendar["artifact"]["relative_path"]
        assert ics.read_bytes().startswith(b"BEGIN:VCALENDAR\r\n")
        assert b"DTSTART:20260901T090000Z\r\n" in ics.read_bytes()

        hardware = _post(client, "/api/productivity/hardware/optimize", {
            "task": "research", "requested_context_tokens": 999_999,
        })
        assert hardware["automatic_download"] is False
        assert hardware["context_tokens"] <= hardware["profile"]["recommended_context_limit"]

        pin = _post(client, "/api/productivity/pinboard/items", {
            "item_id": "pin_001", "title": "Exact source", "lane": "private_record",
            "source_ref": {"source_id": "record_001", "source_hash": HASH_A,
                           "exact_span": "Exact fictional source text.", "locator": "page 1", "freshness": "source-bound"},
        })
        source = client.get(f"/api/productivity/sources/{pin['item_id']}", headers=HEADERS)
        assert source.status_code == 200
        assert source.json()["item"]["source_ref"]["exact_span"] == "Exact fictional source text."

        working_text = "The fictional private value is Fictional private value."
        exact_private = "Fictional private value"
        redaction = _post(client, "/api/productivity/redaction/projects", {
            "project_id": "redact_001", "record_id": "record_001",
            "source_hash": hashlib.sha256(working_text.encode()).hexdigest(),
            "candidates": [{"candidate_id": "candidate_001", "category": "private_identifier",
                            "exact_text_hash": hashlib.sha256(exact_private.encode()).hexdigest(), "locator": "page 1"}],
        })
        assert redaction["original_immutable"] is True
        assert redaction["derivative_created"] is False
        assert redaction["privacy_review_complete"] is False
        derivative = _post(client, "/api/productivity/redaction/projects/redact_001/finalize", {
            "confirmed": True, "working_text": working_text,
            "replacements": [{"candidate_id": "candidate_001", "exact_text": exact_private, "replacement": "[REDACTED]"}],
        })
        assert derivative["privacy_review_complete"] is True
        assert derivative["filing_ready"] is False
        derivative_path = matter / "45_PRODUCTIVITY_STUDIO" / "artifacts" / "redaction" / "redact_001.txt"
        assert derivative_path.read_text(encoding="utf-8") == "The fictional private value is [REDACTED]."

        actions = _post(client, "/api/productivity/next-actions/refresh", {"blockers": [{
            "action_id": "verify_claim", "priority": 1, "title": "Verify claim",
            "reason": "Exact support is missing.", "corrective_action": "Attach an exact source.",
        }]})
        assert actions["actions"][0]["status"] == "open_review_required"
        assert actions["legal_priority_determination"] is False

        courtroom = _post(client, "/api/productivity/courtroom/sessions", {
            "session_id": "hearing_session", "cards": [{
                "card_id": "hearing_card", "title": "Exact source",
                "display_text": "Exact fictional exhibit text.",
                "source_ref": {"source_id": "record_001", "source_hash": HASH_A,
                               "exact_span": "Exact fictional exhibit text."},
            }],
        })
        assert courtroom["private_notes_hidden"] is True
        assert courtroom["keyboard_navigation"] is True

        schedule = _post(client, "/api/productivity/backups/schedules", {
            "schedule_id": "daily_backup", "interval_hours": 24, "retention_count": 2, "enabled": True,
        })
        assert schedule["run_when_app_active"] is True
        backup = _post(client, "/api/productivity/backups/run", {"schedule_id": "daily_backup"})
        assert backup["verified"] is True
        verify = client.get(f"/api/productivity/backups/{backup['backup_id']}/verify", headers=HEADERS)
        assert verify.status_code == 200
        assert verify.json()["status"] == "pass"
        restored = _post(client, f"/api/productivity/backups/{backup['backup_id']}/restore", {"confirmed": True})
        assert restored["live_matter_overwritten"] is False
        assert restored["status"] == "restored_to_separate_recovery_directory"

        imported = _post(client, "/api/hearing-media/import", {"media": [{
            "media_id": "hearing_audio", "title": "Fictional audio", "filename": "hearing.wav",
            "media_kind": "audio", "source_hash": HASH_A, "confidentiality": "private_record",
        }]})
        assert imported["no_original_modified"] is True
        transcript = _post(client, "/api/hearing-media/media/hearing_audio/transcribe", {
            "transcript_text": "[00:00:01] Speaker: Fictional testimony.",
        })
        assert transcript["transcript"]["segment_count"] == 1

        summary = client.get("/api/productivity", headers=HEADERS).json()
        assert summary["counts"] == {
            "inbox_configurations": 1, "inbox_receipts": 2, "recipes": 1, "recipe_runs": 1,
            "calendar_exports": 1, "hardware_plans": 1, "pinboard_items": 1,
            "redaction_projects": 1, "next_actions": 1, "courtroom_sessions": 1,
            "backup_schedules": 1, "backups": 1,
        }


def test_productivity_state_is_encrypted_and_cross_matter_copy_fails_closed(matter: Path, tmp_path: Path) -> None:
    store = ProductivitySuiteStore(matter)
    store.add_pinboard_item({
        "item_id": "private_pin", "title": "Private fictional marker",
        "source_ref": {"source_id": "record_001", "exact_span": "SECRET-FICTIONAL-SPAN"},
    })
    encrypted = store.state_path.read_bytes()
    assert b"SECRET-FICTIONAL-SPAN" not in encrypted
    assert b"Private fictional marker" not in encrypted

    second = tmp_path / "second-matter"
    second.mkdir()
    copied = second / store.root.name
    shutil.copytree(store.root, copied)
    with pytest.raises(ProductivitySuiteError) as exc:
        ProductivitySuiteStore(second).summary()
    assert exc.value.code == "cross_matter_access_denied"


def test_productivity_routes_fail_closed_with_an_actionable_error_when_no_matter_is_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing matter must never turn a normal UI click into an unhandled 500."""

    monkeypatch.setattr(api_module, "active_case_root", lambda: None)
    with TestClient(enterprise_app) as client:
        for response in (
            client.get("/api/productivity", headers=HEADERS),
            client.post(
                "/api/productivity/recipes",
                json={"recipe_id": "fictional_recipe", "label": "Fictional", "steps": ["inventory_records"]},
                headers=HEADERS,
            ),
            client.get("/api/productivity/backups/fictional_backup/verify", headers=HEADERS),
        ):
            assert response.status_code == 409, response.text
            assert response.json() == {
                "detail": {
                    "error": "active_case_unavailable",
                    "message": "Select an active matter before opening Productivity Studio.",
                }
            }


def test_productivity_routes_commands_and_shipped_ui_are_reachable() -> None:
    expected_features = {
        "capability_45_smart_matter_inbox", "capability_46_saved_workflow_recipes",
        "capability_47_local_media_transcription", "capability_48_calendar_interoperability",
        "capability_49_hardware_optimizer", "capability_50_research_pinboard",
        "capability_51_redaction_studio", "capability_52_matter_next_actions",
        "capability_53_courtroom_presentation", "capability_54_encrypted_automatic_backup",
    }
    assert expected_features <= set(ACCEPTED_FEATURE_IDS)
    javascript = read_workbench_asset("workbench.js")
    html = read_workbench_asset("workbench.html")
    for command in (
        "open_smart_matter_inbox", "open_workflow_recipes", "open_media_transcription",
        "open_calendar_interop", "open_hardware_optimizer", "open_research_pinboard",
        "open_redaction_studio", "open_matter_next_actions", "open_courtroom_presentation",
        "open_encrypted_backup",
    ):
        assert command in javascript
    assert html.count("data-productivity-panel=") == 10
    assert "productivity-studio-overlay" in html
    assert "Review required" in html
    assert "calendar_account_write" in javascript
    assert "private_notes_hidden" in javascript

    manifest = production_ui_manifest()
    assert manifest["status"] == "pass"
    assert "workbench.js" in manifest["assets"]

    route_pairs = {(method, route.path) for route in production_app.routes for method in (getattr(route, "methods", None) or [])}
    for pair in {
        ("GET", "/api/productivity"),
        ("POST", "/api/productivity/inbox/configurations"),
        ("POST", "/api/productivity/backups/{backup_id}/restore"),
        ("POST", "/api/productivity/redaction/projects/{project_id}/finalize"),
        ("POST", "/api/hearing-media/media/{media_id}/transcribe"),
    }:
        assert pair in route_pairs
