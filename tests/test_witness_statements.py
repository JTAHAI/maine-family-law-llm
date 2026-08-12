from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from legal.matter.witness_statements import WitnessStatementStore
from maine_family_law_llm import api as api_module
from maine_family_law_llm.local_workbench_ui import (
    read_workbench_asset,
    render_local_workbench_html,
)


def _store(tmp_path: Path) -> WitnessStatementStore:
    case = tmp_path / "synthetic-case"
    case.mkdir()
    store = WitnessStatementStore(case, encryption_key="synthetic-test-passphrase")
    store.add_people(
        {"people": [{"person_id": "person_001", "role": "witness", "user_confirmed": True}]}
    )
    return store


def test_statement_comparison_preserves_exact_quote_context_and_no_character_judgment(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    store.add_statements(
        {
            "statements": [
                {
                    "statement_id": "statement_001",
                    "speaker_id": "person_001",
                    "statement_type": "testimony",
                    "exact_text": "The synthetic event occurred on Monday.",
                    "event_date": "2026-01-05",
                    "context_before": "Question context.",
                    "question": "What happened?",
                    "answer": "The synthetic event occurred on Monday.",
                    "source_ref": {"record_id": "source_001"},
                },
                {
                    "statement_id": "statement_002",
                    "speaker_id": "person_001",
                    "statement_type": "prior_statement",
                    "exact_text": "The synthetic event occurred on Tuesday.",
                    "event_date": "2026-01-06",
                    "context_before": "Earlier context.",
                    "ocr_or_translation_warning": True,
                    "source_ref": {"record_id": "source_002"},
                },
            ]
        }
    )
    comparison = store.compare("statement_001", "statement_002")
    assert comparison["comparison_status"] == "date_conflict"
    assert comparison["left"]["exact_text"] == "The synthetic event occurred on Monday."
    assert comparison["right"]["ocr_or_translation_warning"] is True
    assert comparison["credibility"] == "not_determined"
    assert comparison["deception"] == "not_determined"
    outline = store.outline({"statement_ids": ["statement_001"]})
    assert outline["attorney_reviewer_work_product"] is True
    assert "fabricating facts" in outline["prohibited"]


def test_statement_api_is_retained_but_workspace_is_not_publicly_navigable(monkeypatch, tmp_path: Path) -> None:
    case = tmp_path / "synthetic-case"
    case.mkdir()
    monkeypatch.setattr(api_module, "active_case_root", lambda: case)
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "synthetic-test-passphrase")
    client = TestClient(api_module.app)
    assert (
        client.post(
            "/api/statements/people",
            json={"people": [{"person_id": "person_api_001", "user_confirmed": True}]},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/statements",
            json={
                "statements": [
                    {
                        "statement_id": "statement_api_001",
                        "speaker_id": "person_api_001",
                        "exact_text": "Synthetic exact quote.",
                        "source_ref": {"record_id": "source_api_001"},
                    }
                ]
            },
        ).status_code
        == 200
    )
    inventory = client.get("/api/statements/inventory").json()
    assert inventory["credibility_score"] == "not_available"
    assert len(client.get("/api/statements/receipt").json()["receipt_hash"]) == 64
    html, script = render_local_workbench_html(), read_workbench_asset("workbench.js")
    assert 'id="statements-workspace-overlay"' in html
    assert "Side-by-side comparison" in html and "Clarification outline" in html
    assert "open_statements_workspace" not in script
