from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.contracts.endpoint_inventory import EndpointInventory
from app.web.ui_contracts import UICompletionAuditor
from app.web.ui_inventory import UIViewInventory
from maine_family_law_llm import api as api_module


def _headers() -> dict[str, str]:
    return {"X-User-Role": "attorney", "X-Tenant-Id": "tenant-communications"}


def _client(monkeypatch, case_root: Path) -> TestClient:
    monkeypatch.setattr(api_module, "active_case_root", lambda: case_root)
    return TestClient(api_module.app)


def _payload() -> dict[str, object]:
    return {
        "messages": [
            {
                "message_id": "msg-1",
                "source_id": "email-1",
                "source_type": "email",
                "subject": "Weekend exchange",
                "sent_at": "2026-11-01T01:30:00",
                "timezone": "America/New_York",
                "from": "parent-a@example.test",
                "to": ["parent-b@example.test"],
                "body": "Can we switch Sunday pickup to Monday? I am proposing a one-time move.",
                "source_hash": "a" * 64,
                "source_span": {"source_id": "email-1", "source_hash": "a" * 64, "start": 0, "end": 74},
                "attachments": [{"name": "proposal.pdf", "sha256": "1" * 64, "size_bytes": 512, "content_type": "application/pdf"}],
            },
            {
                "message_id": "msg-2",
                "source_id": "email-2",
                "source_type": "email",
                "subject": "Re: Weekend exchange",
                "in_reply_to": "msg-1",
                "sent_at": "2026-11-01T01:40:00-04:00",
                "from": "parent-b@example.test",
                "to": ["parent-a@example.test"],
                "body": "Yes, Monday works for me. Confirmed.",
                "source_hash": "b" * 64,
                "source_span": {"source_id": "email-2", "source_hash": "b" * 64, "start": 0, "end": 49},
                "attachments": [],
            },
            {
                "message_id": "msg-3",
                "source_id": "sms-1",
                "source_type": "sms",
                "subject": "Weekend exchange",
                "sent_at": "2026-11-01T09:15:00",
                "from": "parent-c@example.test",
                "to": ["parent-d@example.test"],
                "body": "According to the order, Sunday remains the operative exchange.",
                "source_hash": "c" * 64,
                "source_span": {"source_id": "sms-1", "source_hash": "c" * 64, "start": 0, "end": 66},
            },
            {
                "message_id": "msg-4",
                "source_id": "sms-2",
                "source_type": "sms",
                "subject": "Weekend exchange",
                "sent_at": "2026-11-01T09:17:00",
                "from": "parent-c@example.test",
                "to": ["parent-d@example.test"],
                "body": "According to the order, Sunday remains the operative exchange.",
                "source_hash": "c" * 64,
                "source_span": {"source_id": "sms-2", "source_hash": "c" * 64, "start": 0, "end": 66},
            },
            {
                "message_id": "msg-5",
                "source_id": "school-1",
                "source_type": "school",
                "subject": "Attendance note",
                "sent_at": "2026-11-01T10:15:00",
                "from": "school@example.test",
                "to": ["parent-a@example.test"],
                "body": "Please see attached attendance letter.",
                "source_hash": "d" * 64,
                "source_span": {"source_id": "school-1", "source_hash": "d" * 64, "start": 0, "end": 39},
            },
            {
                "message_id": "msg-6",
                "source_id": "sms-3",
                "source_type": "sms",
                "subject": "Running late",
                "sent_at": "2026-11-01T12:00:00",
                "from": "parent-a@example.test",
                "to": ["parent-b@example.test"],
                "body": "I am running late, not refusing. I can arrive at 4:30.",
                "source_hash": "e" * 64,
                "source_span": {"source_id": "sms-3", "source_hash": "e" * 64, "start": 0, "end": 57},
            },
            {
                "message_id": "msg-7",
                "source_id": "email-3",
                "source_type": "email",
                "subject": "Court order",
                "sent_at": "2026-11-01T13:30:00",
                "from": "parent-a@example.test",
                "to": ["parent-b@example.test"],
                "body": "According to the court order, Sunday remains the exchange.",
                "source_hash": "f" * 64,
                "source_span": {"source_id": "email-3", "source_hash": "f" * 64, "start": 0, "end": 63},
            },
            {
                "message_id": "msg-8",
                "source_id": "sms-4",
                "source_type": "sms",
                "subject": "Court order",
                "sent_at": "2026-11-01T13:35:00",
                "from": "parent-b@example.test",
                "to": ["parent-a@example.test"],
                "body": "We can handle this informally this week but the order does not change.",
                "source_hash": "g" * 64,
                "source_span": {"source_id": "sms-4", "source_hash": "g" * 64, "start": 0, "end": 74},
            },
            {
                "message_id": "msg-9",
                "source_id": "call-1",
                "source_type": "call_log",
                "subject": "Missed exchange",
                "sent_at": "2026-11-01T14:00:00",
                "from": "parent-b@example.test",
                "to": ["parent-a@example.test"],
                "body": "Missed exchange today.",
                "source_hash": "h" * 64,
                "source_span": {"source_id": "call-1", "source_hash": "h" * 64, "start": 0, "end": 22},
            },
            {
                "message_id": "msg-10",
                "source_id": "sms-5",
                "source_type": "sms",
                "subject": "Missed exchange",
                "sent_at": "2026-11-01T14:05:00",
                "from": "parent-a@example.test",
                "to": ["parent-b@example.test"],
                "body": "I was stuck in traffic and will arrive at 4:15.",
                "source_hash": "i" * 64,
                "source_span": {"source_id": "sms-5", "source_hash": "i" * 64, "start": 0, "end": 51},
            },
            {
                "message_id": "msg-11",
                "source_id": "email-4",
                "source_type": "email",
                "subject": "Proposed change",
                "sent_at": "2026-11-01T15:00:00",
                "from": "parent-a@example.test",
                "to": ["parent-b@example.test"],
                "body": "Can we switch Friday to Saturday? If you don't reply by 6, I'm assuming you are not agreeing to the change.",
                "source_hash": "j" * 64,
                "source_span": {"source_id": "email-4", "source_hash": "j" * 64, "start": 0, "end": 107},
            },
            {
                "message_id": "msg-12",
                "source_id": "email-5",
                "source_type": "email",
                "subject": "Quoted exchange",
                "sent_at": "2026-11-01T16:00:00",
                "from": "parent-b@example.test",
                "to": ["parent-a@example.test"],
                "body": "On Friday, Parent A wrote:\n> Can we switch Friday to Saturday?\nYes, that works for me.",
                "source_hash": "k" * 64,
                "source_span": {"source_id": "email-5", "source_hash": "k" * 64, "start": 0, "end": 86},
            },
        ]
    }


def test_communications_workbench_import_threads_completeness_and_export(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "matter"
    case_root.mkdir()
    client = _client(monkeypatch, case_root)

    imported = client.post("/api/communications/import", json=_payload(), headers=_headers())
    assert imported.status_code == 200
    payload = imported.json()
    assert payload["review_required"] is True
    assert payload["message_count"] == 12
    assert payload["thread_count"] >= 2
    assert payload["no_parent_ranking"] is True
    assert payload["no_abuse_conclusion"] is True
    assert payload["no_sentiment_or_fitness_inference"] is True

    summary = client.get("/api/communications", headers=_headers())
    assert summary.status_code == 200
    summary_payload = summary.json()
    assert summary_payload["message_count"] == 12
    assert summary_payload["completeness"]["status"] == "review_required"
    assert summary_payload["completeness"]["missing_attachments"]
    assert summary_payload["completeness"]["timezone_unknown"]
    assert summary_payload["completeness"]["duplicate_groups"]

    threads = client.get("/api/communications/threads", headers=_headers()).json()["threads"]
    ambiguous = next(thread for thread in threads if thread["thread_reason"] == "subject_normalization" and thread["message_count"] > 1)
    assert ambiguous["confidence"] < 1
    assert ambiguous["alternatives"]
    assert all("source_hash" in message for message in ambiguous["messages"])

    messages = client.get("/api/communications/messages", headers=_headers()).json()["messages"]
    assert any(message["quoted_block_count"] > 0 for message in messages)
    assert any(message["attachment_missing"] for message in messages)
    assert any(message["timezone_status"] in {"unknown", "ambiguous"} for message in messages)

    schedule = client.get("/api/communications/schedule", headers=_headers()).json()["schedule_history"]
    kinds = {row["status"] for row in schedule}
    assert {"proposal_only", "confirmed", "delay_not_refusal", "order_controlling", "informal_change_only", "silence_not_agreement"} & kinds

    parenting_time = client.get("/api/communications/parenting-time", headers=_headers()).json()["parenting_time_events"]
    assert any(event["kind"] == "alleged_missed_exchange" for event in parenting_time)
    assert any(event["kind"] == "court_order" for event in parenting_time)

    agreements = client.get("/api/communications/agreements", headers=_headers()).json()["agreements"]
    assert agreements

    claims = client.get("/api/communications/claims", headers=_headers()).json()["claims"]
    assert claims
    assert all("fitness" not in json.dumps(row).lower() for row in claims)
    assert all("abuse" not in json.dumps(row).lower() for row in claims)
    assert all("sentiment" not in json.dumps(row).lower() for row in claims)

    completeness = client.get("/api/communications/completeness", headers=_headers()).json()["completeness"]
    assert completeness["no_parent_ranking"] is True
    assert completeness["no_abuse_conclusion"] is True

    review_history = client.get("/api/communications/review-history", headers=_headers()).json()["history"]
    assert review_history

    export = client.post("/api/communications/exports", json={"format": "json"}, headers=_headers())
    assert export.status_code == 200
    export_payload = export.json()
    assert export_payload["receipt"]["export_sha256"]
    assert export_payload["receipt"]["bundle_sha256"]
    export_dir = case_root / "22_COMMUNICATIONS_PARENTING_TIME_WORKBENCH" / "exports" / export_payload["export_id"]
    assert (export_dir / "communications-workbench-export.json").exists()
    assert (export_dir / "communications-workbench-export.txt").exists()
    assert (export_dir / "communications-workbench-receipt.json").exists()
    assert export_payload["artifacts"][0]["sha256"]

    raw_state = (case_root / "22_COMMUNICATIONS_PARENTING_TIME_WORKBENCH" / "communications-workbench.json.enc").read_text(encoding="utf-8")
    assert "switch Friday to Saturday" not in raw_state
    assert "parent-a@example.test" not in raw_state


def test_communications_workbench_rejects_credentials_and_stays_case_scoped(monkeypatch, tmp_path: Path) -> None:
    case_a = tmp_path / "case-a"
    case_b = tmp_path / "case-b"
    case_a.mkdir()
    case_b.mkdir()

    client_a = _client(monkeypatch, case_a)
    blocked = client_a.post("/api/communications/import", json={"messages": [{"message_id": "bad-1", "credentials": {"token": "secret"}}]}, headers=_headers())
    assert blocked.status_code == 400
    assert blocked.json()["detail"]["error"] == "credentials_not_supported"

    imported = client_a.post("/api/communications/import", json=_payload(), headers=_headers())
    assert imported.status_code == 200

    monkeypatch.setattr(api_module, "active_case_root", lambda: case_b)
    client_b = TestClient(api_module.app)
    empty = client_b.get("/api/communications", headers=_headers())
    assert empty.status_code == 200
    assert empty.json()["message_count"] == 0


def test_communications_ui_inventory_and_route_contracts_include_the_shipped_workbench() -> None:
    pages_dir = Path("app/web/pages")
    ui_inventory = UIViewInventory(pages_dir).validate()
    assert ui_inventory["status"] == "pass"
    assert "communications-parenting-time.tsx" in {view["file"] for view in ui_inventory["views"]}
    ui_audit = UICompletionAuditor("app/web/pages").audit().as_dict()
    assert ui_audit["status"] == "pass"

    page = (pages_dir / "communications-parenting-time.tsx").read_text(encoding="utf-8")
    assert "data-communications-workbench=\"visible\"" in page
    assert "data-thread-reconstruction=\"visible\"" in page
    assert "data-schedule-history=\"visible\"" in page
    assert "data-parenting-time-review=\"visible\"" in page
    assert "data-agreement-mapping=\"visible\"" in page
    assert "data-completeness=\"visible\"" in page
    assert "data-export-receipt=\"visible\"" in page
    assert "data-privacy-review=\"visible\"" in page
    assert "data-review-history=\"visible\"" in page

    app_shell = Path("app/web/src/App.tsx").read_text(encoding="utf-8")
    assert "/communications" in app_shell
    assert "Communications & Parenting-Time" in app_shell

    endpoint_inventory = EndpointInventory().as_dict()["endpoints"]
    expected_paths = {
        "/api/communications",
        "/api/communications/import",
        "/api/communications/messages",
        "/api/communications/threads",
        "/api/communications/schedule",
        "/api/communications/parenting-time",
        "/api/communications/agreements",
        "/api/communications/claims",
        "/api/communications/completeness",
        "/api/communications/review-history",
        "/api/communications/exports",
    }
    inventory_paths = {item["path"] for item in endpoint_inventory}
    assert expected_paths <= inventory_paths
