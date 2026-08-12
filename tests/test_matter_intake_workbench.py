from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from legal.matter.intake_workbench import IntakeWorkbenchError, MatterIntakeStore
from maine_family_law_llm import api as api_module
from maine_family_law_llm.local_workbench_ui import (
    read_workbench_asset,
    render_local_workbench_html,
)


def _create(store: MatterIntakeStore, matter_id: str = "matter_demo") -> dict:
    return store.create(
        {
            "matter_id": matter_id,
            "matter_type_candidates": ["parental_rights_responsibilities"],
            "requested_workflow": "organize neutral questions for reviewer",
        }
    )


def test_unknown_and_disputed_answers_are_preserved_and_history_is_hash_bound(
    tmp_path: Path,
) -> None:
    case = tmp_path / "synthetic-case"
    case.mkdir()
    store = MatterIntakeStore(case, encryption_key="synthetic-test-passphrase")
    _create(store)
    updated = store.classify(
        "matter_demo",
        {
            "answers": {
                "service_status": {"state": "unknown", "value": "", "source_refs": []},
                "contact_schedule": {
                    "state": "disputed",
                    "value": "The accounts differ.",
                    "source_refs": [{"record_id": "email_001"}],
                },
            }
        },
    )
    assert updated["questionnaire"]["service_status"]["state"] == "unknown"
    assert updated["questionnaire"]["contact_schedule"]["state"] == "disputed"
    assert updated["questionnaire"]["contact_schedule"]["review_required"] is True
    assert len(updated["history"]) == 2
    receipt = store.receipt("matter_demo")
    assert len(receipt["intake_hash"]) == 64
    assert len(receipt["receipt_hash"]) == 64
    encrypted = case / "20_MATTER_INTAKE" / "matter_demo" / "intake.json.enc"
    assert encrypted.exists()
    assert "The accounts differ" not in encrypted.read_text(encoding="utf-8")


def test_posture_and_issue_tree_require_provenance_and_refuse_outcome_language(
    tmp_path: Path,
) -> None:
    case = tmp_path / "synthetic-case"
    case.mkdir()
    store = MatterIntakeStore(case, encryption_key="synthetic-test-passphrase")
    _create(store)
    result = store.posture(
        "matter_demo",
        {
            "state": "hearing_scheduled",
            "entry_status": "known",
            "source_refs": [{"record_id": "notice_001", "page": 1}],
        },
    )
    assert result["procedural_posture"]["source_refs"][0]["record_id"] == "notice_001"
    tree = store.issue_tree(
        "matter_demo",
        {
            "issues": [
                {
                    "issue_id": "issue_schedule",
                    "issue_label": "Schedule question",
                    "posture": "hearing_scheduled",
                    "user_stated_concern": "The schedule needs reviewer clarification.",
                    "factual_claims": [],
                    "supporting_records": [{"record_id": "notice_001"}],
                    "contradicting_records": [],
                    "applicable_authority_candidates": [],
                    "missing_facts": ["current schedule"],
                    "missing_records": [],
                    "forms": [],
                    "deadlines_requiring_review": [],
                    "reviewer_notes": "",
                    "status": "review_required",
                }
            ]
        },
    )
    assert tree["issue_tree"][0]["supporting_records"][0]["record_id"] == "notice_001"
    try:
        store.issue_tree(
            "matter_demo",
            {
                "issues": [
                    {
                        "issue_id": "issue_bad",
                        "issue_label": "Who wins",
                        "user_stated_concern": "",
                        "factual_claims": [],
                        "supporting_records": [],
                        "contradicting_records": [],
                        "applicable_authority_candidates": [],
                        "missing_facts": [],
                        "missing_records": [],
                        "forms": [],
                        "deadlines_requiring_review": [],
                    }
                ]
            },
        )
    except IntakeWorkbenchError as exc:
        assert exc.code == "outcome_or_fitness_language_refused"
    else:  # pragma: no cover
        raise AssertionError("outcome language must be refused")


def test_coverage_flags_missing_order_and_cross_matter_access_is_denied(tmp_path: Path) -> None:
    case_a = tmp_path / "synthetic-a"
    case_a.mkdir()
    case_b = tmp_path / "synthetic-b"
    case_b.mkdir()
    first = MatterIntakeStore(case_a, encryption_key="synthetic-test-passphrase")
    _create(first)
    first.posture("matter_demo", {"state": "final_order_entered", "source_refs": []})
    coverage = first.coverage(
        "matter_demo",
        [
            {
                "evidence_id": "email_001",
                "title": "Synthetic email",
                "source_type": "email",
                "source_hash": "a" * 64,
                "parser_status": "parsed_text",
            }
        ],
    )
    assert "operative_order_missing" in coverage["missing_record_checklist"]
    second = MatterIntakeStore(case_b, encryption_key="synthetic-test-passphrase")
    try:
        second.get("matter_demo")
    except IntakeWorkbenchError as exc:
        assert exc.status_code == 404
    else:  # pragma: no cover
        raise AssertionError("cross-matter access must be denied")


def test_api_contract_uses_active_matter_and_never_returns_a_raw_path(
    monkeypatch, tmp_path: Path
) -> None:
    case = tmp_path / "synthetic-case"
    case.mkdir()
    monkeypatch.setattr(api_module, "active_case_root", lambda: case)
    monkeypatch.setattr(
        api_module,
        "load_case_search_records",
        lambda _: [
            {
                "evidence_id": "order_001",
                "title": "Synthetic order",
                "source_type": "order",
                "source_hash": "b" * 64,
                "parser_status": "parsed_text",
            }
        ],
    )
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "synthetic-test-passphrase")
    client = TestClient(api_module.app)
    created = client.post(
        "/api/intake/matters",
        json={"matter_id": "matter_api", "matter_type_candidates": ["research_only"]},
    )
    assert created.status_code == 200
    posture = client.post(
        "/api/intake/matters/matter_api/posture", json={"state": "unknown", "source_refs": []}
    )
    assert posture.status_code == 200
    coverage = client.get("/api/intake/matters/matter_api/coverage")
    assert coverage.status_code == 200
    serialized = json.dumps(coverage.json())
    assert str(case) not in serialized
    receipt = client.get("/api/intake/matters/matter_api/receipt")
    assert receipt.status_code == 200
    assert receipt.json()["review_required"] is True


def test_experimental_intake_markup_is_retained_but_not_publicly_navigable() -> None:
    html = render_local_workbench_html()
    script = read_workbench_asset("workbench.js")
    for label in (
        "Purpose and privacy",
        "Matter type",
        "People and child-safe identities",
        "Court and procedural posture",
        "Orders and hearings",
        "Record scope",
        "Issues and disputed facts",
        "Missing records",
        "Privacy and sharing",
        "Review summary",
        "Intake receipt",
    ):
        assert label in html
    assert 'id="matter-intake-overlay"' in html
    assert "open_matter_intake" not in script
    assert "/api/intake/matters/" in script
    assert "predict an outcome" in html
