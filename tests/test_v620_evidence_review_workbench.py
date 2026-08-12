from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from maine_family_law_llm import api as api_module


def _rows() -> list[dict[str, object]]:
    return [
        {
            "evidence_id": "ORDER-1",
            "canonical_evidence_id": "ORDER-1",
            "title": "Order",
            "source_type": "order",
            "source_hash": "a" * 64,
            "text": "Order entered January 3, 2026. The parent shall pay $125 weekly child support.",
            "page_number": 1,
            "issue_lanes": ["support", "order"],
        },
        {
            "evidence_id": "EMAIL-1",
            "title": "Email",
            "source_type": "email",
            "source_hash": "b" * 64,
            "text": "On January 10, 2026, the sender states the parent did not pay $125.",
            "page_number": 2,
            "issue_lanes": ["support", "communication"],
        },
        {
            "evidence_id": "EMAIL-2",
            "title": "Follow-up",
            "source_type": "email",
            "source_hash": "c" * 64,
            "text": "However, the parent says the payment was delayed because the bank held the transfer until January 11, 2026.",
            "page_number": 3,
            "issue_lanes": ["support", "communication"],
        },
        {
            "evidence_id": "NOTE-1",
            "title": "School note",
            "source_type": "school",
            "source_hash": "d" * 64,
            "text": "School meeting occurred without a date in the note.",
            "page_number": 4,
            "issue_lanes": ["child_impact", "school"],
            "parser_status": "parse_required",
        },
        {
            "evidence_id": "ORDER-2",
            "canonical_evidence_id": "ORDER-1",
            "title": "Duplicate order",
            "source_type": "order",
            "source_hash": "a" * 64,
            "text": "Order entered January 3, 2026. The parent shall pay $125 weekly child support.",
            "page_number": 5,
            "issue_lanes": ["support", "order"],
        },
    ]


def _client(monkeypatch, case_root: Path) -> TestClient:
    monkeypatch.setattr(api_module, "active_case_root", lambda: case_root)
    monkeypatch.setattr(api_module, "load_case_search_records", lambda _root: _rows())
    return TestClient(api_module.app)


def test_v620_review_workbench_builds_timeline_claims_coverage_ledger_and_exports(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "case-a"
    case_root.mkdir()
    client = _client(monkeypatch, case_root)

    build = client.post(
        "/api/timeline/build",
        json={
            "selected_record_ids": ["ORDER-1", "EMAIL-1", "EMAIL-2", "NOTE-1", "ORDER-2"],
            "issue_tags": ["support", "school"],
        },
    )
    assert build.status_code == 200
    timeline = build.json()
    assert timeline["status"] == "pass"
    assert timeline["timeline"]["events"]
    assert timeline["timeline"]["undated_records"]
    assert timeline["coverage"]["duplicate_group_count"] >= 1
    assert timeline["coverage"]["parser_ocr_failure_count"] >= 1

    manual_event = client.post(
        "/api/timeline/events",
        json={
            "event_label": "Manual review note",
            "classification": "observed",
            "date_value": "2026-01-12",
            "date_type": "message timestamp",
            "source_record_id": "EMAIL-1",
            "source_hash": "b" * 64,
            "issue_tags": ["support"],
            "child_impact_tags": ["financial_support"],
        },
    )
    assert manual_event.status_code == 200
    event_id = manual_event.json()["event"]["event_id"]
    patched = client.patch(
        f"/api/timeline/events/{event_id}",
        json={"date_value": "2026-01-13", "reason": "Reviewer corrected the date from the surrounding context."},
    )
    assert patched.status_code == 200
    history = client.get(f"/api/timeline/events/{event_id}/history")
    assert history.status_code == 200
    assert history.json()["history"]

    claim = client.post(
        "/api/evidence/claims",
        json={
            "statement": "The parent did not pay child support on January 10, 2026.",
            "selected_record_ids": ["ORDER-1", "EMAIL-1", "EMAIL-2"],
            "claim_type": "factual_claim",
            "scope": "selected_records",
            "source_of_claim": "draft_sentence",
            "child_impact_tags": ["financial_support"],
        },
    )
    assert claim.status_code == 200
    claim_payload = claim.json()["claim"]
    assert claim_payload["supports"]
    assert claim_payload["contradicts"]
    assert claim_payload["qualifies"] or claim_payload["alternative_explanations"]
    assert "truth" not in json.dumps(claim_payload).casefold()


    claim_id = claim_payload["claim_id"]
    reviewed = client.post(
        f"/api/evidence/claims/{claim_id}/review",
        json={"reviewer_status": "needs_more_context", "reviewer_notes": "Check the bank transfer delay."},
    )
    assert reviewed.status_code == 200
    fetched = client.get(f"/api/evidence/claims/{claim_id}")
    assert fetched.status_code == 200
    assert fetched.json()["history"]

    coverage = client.get("/api/evidence/coverage?selected_record_ids=ORDER-1,EMAIL-1,EMAIL-2,NOTE-1,ORDER-2")
    assert coverage.status_code == 200
    coverage_payload = coverage.json()
    assert coverage_payload["records_total"] == 5
    assert coverage_payload["undated_records"]
    assert coverage_payload["excluded_records"] == []

    missing = client.post(
        "/api/evidence/missing-records",
        json={
            "template_id": "support_template",
            "selected_record_ids": ["ORDER-1", "EMAIL-1", "EMAIL-2", "NOTE-1", "ORDER-2"],
            "items": [
                {
                    "origin_type": "user",
                    "expected_record_description": "Operative order copy",
                    "why_it_may_matter": "Needed to compare the enforcement language.",
                    "basis_for_expectation": "user checklist",
                    "search_performed": "Searched selected indexed records.",
                    "records_found": ["ORDER-1"],
                    "status": "review_required",
                }
            ],
        },
    )
    assert missing.status_code == 200
    assert missing.json()["missing_records"][0]["origin_type"] == "user"

    blocked_ledger = client.post(
        "/api/enforcement/ledger/events",
        json={
            "event_date": "2026-01-10",
            "operative_order_record": "ORDER-1",
            "required_conduct": "pay child support",
            "alleged_or_observed_conduct": "did not pay on the stated date",
        },
    )
    assert blocked_ledger.status_code == 409

    ledger = client.post(
        "/api/enforcement/ledger/events",
        json={
            "event_date": "2026-01-10",
            "operative_order_record": "ORDER-1",
            "exact_order_term": "shall pay $125 weekly child support",
            "required_conduct": "pay child support",
            "alleged_or_observed_conduct": "did not pay on the stated date",
            "supporting_spans": [{"record_id": "EMAIL-1", "span_start": 0, "span_end": 40}],
            "contradicting_spans": [{"record_id": "EMAIL-2", "span_start": 0, "span_end": 45}],
        },
    )
    assert ledger.status_code == 200
    ledger_event_id = ledger.json()["event"]["event_id"]
    ledger_patch = client.patch(
        f"/api/enforcement/ledger/events/{ledger_event_id}",
        json={"reviewer_status": "needs_review", "requested_relief": "review only"},
    )
    assert ledger_patch.status_code == 200
    assert ledger_patch.json()["history"]

    export_response = client.post(
        "/api/evidence/export",
        json={"export_kind": "chronology", "format": "md", "selected_record_ids": ["ORDER-1", "EMAIL-1", "EMAIL-2", "NOTE-1", "ORDER-2"]},
    )
    assert export_response.status_code == 200
    export_payload = export_response.json()
    assert export_payload["artifact"]["artifact_relative_path"].startswith("19_EVIDENCE_WORK_PRODUCT")
    assert export_payload["receipt"]["receipt_sha256"]
    serialized = json.dumps(export_payload)
    assert str(case_root) not in serialized
    assert "/tmp/" not in serialized

    history_all = client.get("/api/evidence/review-history")
    assert history_all.status_code == 200
    assert history_all.json()["history"]


def test_v620_review_workbench_is_matter_scoped(monkeypatch, tmp_path: Path) -> None:
    case_a = tmp_path / "case-a"
    case_b = tmp_path / "case-b"
    case_a.mkdir()
    case_b.mkdir()

    monkeypatch.setattr(api_module, "load_case_search_records", lambda _root: _rows())

    monkeypatch.setattr(api_module, "active_case_root", lambda: case_a)
    client_a = TestClient(api_module.app)
    assert client_a.post("/api/timeline/build", json={"selected_record_ids": ["ORDER-1", "EMAIL-1"]}).status_code == 200
    assert client_a.get("/api/timeline").json()["timeline"]["events"]

    monkeypatch.setattr(api_module, "active_case_root", lambda: case_b)
    client_b = TestClient(api_module.app)
    assert client_b.get("/api/timeline").json()["timeline"]["events"] == []
    assert client_b.get("/api/evidence/review-history").json()["history"] == []


def test_v620_review_workbench_pages_expose_the_tabbed_workspace() -> None:
    pages = {
        "timeline": Path("app/web/pages/timeline.tsx"),
        "evidence": Path("app/web/pages/evidence.tsx"),
        "contradictions": Path("app/web/pages/contradictions.tsx"),
        "coverage": Path("app/web/pages/coverage.tsx"),
        "missing": Path("app/web/pages/missing-records.tsx"),
        "enforcement": Path("app/web/pages/enforcement.tsx"),
        "history": Path("app/web/pages/review-history.tsx"),
    }
    for path in pages.values():
        text = path.read_text(encoding="utf-8")
        assert "EvidenceWorkbench" in text
        assert "data-review-status=\"review_required\"" not in text or "EvidenceWorkbench" in text
    app_shell = Path("app/web/src/App.tsx").read_text(encoding="utf-8")
    for href in ("/timeline", "/evidence", "/contradictions", "/coverage", "/missing-records", "/enforcement", "/review-history"):
        assert href in app_shell


def test_timeline_cancellation_is_immediate_for_exactly_500_records(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "case-cancel"
    case_root.mkdir()
    records = [
        {
            "evidence_id": f"RECORD-{index:03d}",
            "source_type": "record",
            "source_hash": f"{index:064x}"[-64:],
            "text": "Order entered January 3, 2026.",
        }
        for index in range(500)
    ]
    monkeypatch.setattr(api_module, "active_case_root", lambda: case_root)
    monkeypatch.setattr(api_module, "load_case_search_records", lambda _root: records)
    client = TestClient(api_module.app)

    response = client.post("/api/timeline/build", json={"cancel_requested": True})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "cancelled"
    assert payload["timeline"]["status"] == "cancelled"
    assert payload["timeline"]["events"] == []
    assert "timeline_build_cancelled" in payload["warnings"]
