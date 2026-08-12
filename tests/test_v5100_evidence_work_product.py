from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from legal.evidence import EvidenceWorkProductError, EvidenceWorkProductStore
from maine_family_law_llm import api as api_module


def _records() -> list[dict]:
    return [
        {
            "evidence_id": "ORDER-1",
            "title": "Final Order",
            "source_locator": r"C:\private\matter\Final Order.pdf#page=2",
            "source_type": "order",
            "source_hash": "a" * 64,
            "page_number": 2,
            "text": (
                "Order entered January 3, 2026. The parent shall pay $125 weekly child support. "
                "The court finds that contact shall occur every Saturday."
            ),
            "parser_status": "parsed_text",
        },
        {
            "evidence_id": "EMAIL-1",
            "title": "Email about payment",
            "source_locator": "/home/user/private/payment-email.txt",
            "source_type": "email",
            "source_hash": "b" * 64,
            "text": (
                "On January 10, 2026, the sender states that the parent did not pay $125 and refused to provide contact. "
                "The email requests enforcement of the order."
            ),
        },
        {
            "evidence_id": "RECEIPT-1",
            "title": "Payment receipt",
            "source_locator": "/private/receipt.txt",
            "source_type": "financial_document",
            "source_hash": "c" * 64,
            "text": "Payment was made on January 10, 2026. The parent paid $125 in full.",
        },
        {
            "evidence_id": "NOTICE-1",
            "title": "Service record",
            "source_locator": "/private/service.pdf",
            "source_type": "service_record",
            "source_hash": "d" * 64,
            "text": "The motion was served on January 12, 2026 and notice was received.",
        },
    ]


def test_builds_timeline_ledger_conflicts_exhibits_and_safe_packet(tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    result = EvidenceWorkProductStore(case).build(_records())
    assert result.status == "pass"
    packet = result.packet
    assert packet["summary"]["record_count"] == 4
    assert packet["summary"]["timeline_event_count"] >= 4
    assert packet["summary"]["enforcement_ledger_count"] >= 2
    assert packet["summary"]["exhibit_count"] == 4
    assert any(row["date_type"] == "order_date" for row in packet["timeline"])
    assert any(row["operative_order_language"] for row in packet["contempt_enforcement_ledger"])
    assert any(row.get("conflict_type") in {"opposing_record_language", "hard_field_mismatch"} for row in packet["contradictions"])
    assert all("private" not in row["safe_filename"].casefold() for row in packet["records"])
    serialized = json.dumps(packet)
    assert "C:\\private" not in serialized
    assert "/home/user/private" not in serialized
    assert packet["review_required"] is True
    assert packet["legal_conclusion"] == "not_determined"


def test_content_addressed_build_is_reused_and_tampering_fails_closed(tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    store = EvidenceWorkProductStore(case)
    first = store.build(_records())
    second = store.build(_records())
    assert second.build_id == first.build_id
    assert second.reused_existing_build is True
    assert store.verify(first.build_id)["status"] == "pass"

    packet_path = case / "19_EVIDENCE_WORK_PRODUCT" / "builds" / first.build_id / "evidence-work-product.json"
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    packet["summary"]["record_count"] = 999
    packet_path.write_text(json.dumps(packet), encoding="utf-8")
    report = store.verify(first.build_id)
    assert report["status"] == "blocked"
    assert "packet_content_hash_mismatch" in report["blockers"] or any("artifact_hash_mismatch" in item for item in report["blockers"])


def test_selected_scope_and_missing_record_checks(tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    result = EvidenceWorkProductStore(case).build(
        _records(), selected_evidence_ids=["EMAIL-1"], focus_terms=["enforcement"]
    )
    assert result.packet["summary"]["record_count"] == 1
    codes = {row["code"] for row in result.packet["missing_record_checklist"]}
    assert "operative_order_copy_not_confirmed" in codes
    assert "notice_or_service_record_not_confirmed" in codes


def test_refuses_symlinked_work_product_root(tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    target = tmp_path / "elsewhere"
    target.mkdir()
    try:
        (case / "19_EVIDENCE_WORK_PRODUCT").symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(EvidenceWorkProductError, match="symlinked"):
        EvidenceWorkProductStore(case).build(_records())


def test_api_build_status_verify_and_artifact_capability(monkeypatch, tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    monkeypatch.setattr(api_module, "active_case_root", lambda: case)
    monkeypatch.setattr(api_module, "load_case_search_records", lambda _case: _records())
    client = TestClient(api_module.app)

    denied = client.post("/api/evidence-work-product/build", json={"approved": False})
    assert denied.status_code == 409

    built = client.post(
        "/api/evidence-work-product/build",
        json={"approved": True, "include_all_records": True, "focus_terms": ["pay"]},
    )
    assert built.status_code == 200
    payload = built.json()
    assert payload["status"] == "pass"
    assert payload["packet"]["summary"]["record_count"] == 4
    assert payload["artifacts"]
    assert all("relative_path" not in row for row in payload["artifacts"])
    assert all(row["download_url"].startswith("/api/evidence-work-product/artifacts/") for row in payload["artifacts"])

    status = client.get("/api/evidence-work-product/status")
    assert status.status_code == 200
    assert status.json()["active_build"]["build_id"] == payload["build_id"]

    verified = client.get("/api/evidence-work-product/verify")
    assert verified.status_code == 200
    assert verified.json()["status"] == "pass"

    artifact = client.get(payload["artifacts"][0]["download_url"])
    assert artifact.status_code == 200
    assert artifact.headers["cache-control"].startswith("no-store")


def test_api_selected_record_requires_selection(monkeypatch, tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    monkeypatch.setattr(api_module, "active_case_root", lambda: case)
    monkeypatch.setattr(api_module, "load_case_search_records", lambda _case: _records())
    client = TestClient(api_module.app)
    response = client.post(
        "/api/evidence-work-product/build",
        json={"approved": True, "include_all_records": False, "selected_evidence_ids": []},
    )
    assert response.status_code == 400
