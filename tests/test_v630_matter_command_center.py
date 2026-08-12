from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from maine_family_law_llm import api as api_module


def _records() -> list[dict[str, object]]:
    return [
        {
            "evidence_id": "ORDER-1",
            "title": "Temporary Order",
            "source_type": "order",
            "source_hash": "a" * 64,
            "text": "Order entered January 3, 2026. The parent shall pay $125 weekly child support.",
            "page_number": 1,
            "issue_lanes": ["support", "order"],
            "privacy_status": "review_required",
        },
        {
            "evidence_id": "EMAIL-1",
            "title": "Payment email",
            "source_type": "email",
            "source_hash": "b" * 64,
            "text": "On January 10, 2026 the sender says the parent did not pay $125.",
            "page_number": 2,
            "issue_lanes": ["support", "communication"],
            "privacy_status": "review_required",
        },
    ]


def _client(monkeypatch, case_root: Path, records: list[dict[str, object]]) -> TestClient:
    monkeypatch.setattr(api_module, "active_case_root", lambda: case_root)
    monkeypatch.setattr(api_module, "load_case_search_records", lambda _root: records)
    return TestClient(api_module.app)


def test_v630_matter_command_center_snapshot_packet_compare_and_stale_detection(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "matter"
    case_root.mkdir()
    client = _client(monkeypatch, case_root, _records())

    snapshot = client.post(
        "/api/matters/M-100/review-snapshot",
        json={"approved": True, "variant": "metadata_only"},
    )
    assert snapshot.status_code == 200
    snapshot_payload = snapshot.json()
    assert snapshot_payload["review_required"] is True
    assert snapshot_payload["coverage"]["record_count"] == 2
    assert snapshot_payload["included_records"]
    assert all("text" not in row for row in snapshot_payload["included_records"])

    packet = client.post(
        "/api/matters/M-100/evidence-packet",
        json={"approved": True, "variant": "metadata_only", "snapshot_id": snapshot_payload["snapshot_id"]},
    )
    assert packet.status_code == 200
    packet_payload = packet.json()
    assert packet_payload["review_required"] is True
    assert packet_payload["receipt"]["receipt_sha256"]
    assert packet_payload["work_product_result"]["packet"]["review_required"] is True
    assert all("text" not in row for row in packet_payload["work_product_result"]["packet"]["records"])

    fetched = client.get(f"/api/evidence-packets/{packet_payload['packet_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["packet_sha256"] == packet_payload["packet_sha256"]

    receipt = client.get(f"/api/evidence-packets/{packet_payload['packet_id']}/receipt")
    assert receipt.status_code == 200
    assert receipt.json()["packet_id"] == packet_payload["packet_id"]

    reviewed = client.post(
        f"/api/evidence-packets/{packet_payload['packet_id']}/review",
        json={
            "approved": True,
            "reviewer_name": "Reviewer One",
            "reviewer_role": "attorney",
            "review_status": "approve_review",
            "note": "Looks complete.",
        },
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["review_status"] == "approve_review"

    second_packet = client.post(
        "/api/matters/M-100/evidence-packet",
        json={"approved": True, "variant": "metadata_only"},
    )
    assert second_packet.status_code == 200
    compare = client.post(
        f"/api/evidence-packets/{packet_payload['packet_id']}/compare",
        json={"right_packet_id": second_packet.json()["packet_id"]},
    )
    assert compare.status_code == 200
    assert compare.json()["same_record_scope"] is True

    list_response = client.get("/api/matters/M-100/evidence-packets")
    assert list_response.status_code == 200
    assert list_response.json()["count"] >= 1

    mutated_client = _client(
        monkeypatch,
        case_root,
        [
            *_records(),
            {
                "evidence_id": "NOTE-1",
                "title": "New note",
                "source_type": "note",
                "source_hash": "c" * 64,
                "text": "A new record appeared after the snapshot was frozen.",
                "page_number": 3,
                "issue_lanes": ["support"],
                "privacy_status": "review_required",
            },
        ],
    )
    command_center = mutated_client.get("/api/matters/M-100/command-center")
    assert command_center.status_code == 200
    command_center_payload = command_center.json()
    assert command_center_payload["stale_snapshot_detected"] is True
    assert "matter_snapshot_scope_changed" in command_center_payload["stale_reasons"]
    assert json.dumps(command_center_payload)


def test_v630_command_center_page_and_navigation_exist() -> None:
    app_shell = Path("app/web/src/App.tsx").read_text(encoding="utf-8")
    page = Path("app/web/pages/command-center.tsx").read_text(encoding="utf-8")
    assert "/command-center" in app_shell
    assert "Full-Record Coverage and Exportable Evidence Packet" in page
    assert "data-command-center=\"visible\"" in page
    assert "data-full-record-coverage=\"visible\"" in page
    assert "data-exportable-packet=\"visible\"" in page
