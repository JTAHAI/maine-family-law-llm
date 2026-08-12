from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.matter.order_intelligence import OrderIntelligenceStore
from maine_family_law_llm import api as api_module
from maine_family_law_llm.local_workbench_ui import (
    read_workbench_asset,
    render_local_workbench_html,
)


def _store(tmp_path: Path) -> OrderIntelligenceStore:
    case = tmp_path / "synthetic-case"
    case.mkdir()
    return OrderIntelligenceStore(case, encryption_key="synthetic-test-passphrase")


def _orders(store: OrderIntelligenceStore) -> dict:
    return store.add_orders(
        {
            "orders": [
                {
                    "order_id": "order_temp",
                    "source_ref": {
                        "record_id": "order_source_1",
                        "source_hash": "a" * 64,
                        "page": 1,
                    },
                    "order_type": "temporary_order",
                    "status_candidate": "temporary_candidate",
                    "terms": [
                        {
                            "term_id": "term_contact_temp",
                            "subject": "contact_schedule",
                            "exact_language": "Contact occurs every Saturday.",
                            "source_ref": {"record_id": "order_source_1", "page": 1},
                        }
                    ],
                },
                {
                    "order_id": "order_final",
                    "source_ref": {
                        "record_id": "order_source_2",
                        "source_hash": "b" * 64,
                        "page": 2,
                    },
                    "order_type": "order",
                    "status_candidate": "final_candidate",
                    "terms": [
                        {
                            "term_id": "term_contact_final",
                            "subject": "contact_schedule",
                            "exact_language": "Contact occurs every other Sunday, except holidays.",
                            "source_ref": {"record_id": "order_source_2", "page": 2},
                        }
                    ],
                },
            ]
        }
    )


def test_orders_terms_graph_and_diff_remain_review_required(tmp_path: Path) -> None:
    store = _store(tmp_path)
    inventory = _orders(store)
    assert len(inventory["orders"]) == 2
    graph = store.graph(
        {
            "edges": [
                {
                    "source_order_id": "order_final",
                    "target_order_id": "order_temp",
                    "relationship": "replaces",
                    "exact_language": "This order replaces the temporary order.",
                    "source_ref": {"record_id": "order_source_2", "page": 2},
                }
            ]
        }
    )
    assert graph["edges"][0]["relationship"] == "replaces"
    diff = store.compare("term_contact_temp", "term_contact_final")
    assert diff["review_required"] is True
    assert any(item["kind"] != "equal" for item in diff["semantic_diff"])
    assert "does not determine legal effect" in diff["limitations"][0]


def test_no_silent_operative_determination_and_ledger_never_decides_contempt(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    _orders(store)
    reviewed = store.review_candidate(
        {"term_id": "term_contact_final", "confirmed": False, "note": "Needs document review."}
    )
    term = next(
        item for item in reviewed["orders"][1]["terms"] if item["term_id"] == "term_contact_final"
    )
    assert term["operative_candidate_review"]["status"] == "review_required"
    ledger = store.ledger(
        {
            "entries": [
                {
                    "term_id": "term_contact_final",
                    "person_or_role": "parent_a",
                    "conduct": "Contact schedule",
                    "compliance_status": "alleged",
                    "related_evidence": [],
                    "contradictory_records": [],
                }
            ]
        }
    )
    assert ledger["entries"][0]["contempt_or_willfulness"] == "not_determined"


def test_graph_requires_evidence_or_reviewer_and_receipt_is_hash_bound(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _orders(store)
    try:
        store.graph(
            {
                "edges": [
                    {
                        "source_order_id": "order_final",
                        "target_order_id": "order_temp",
                        "relationship": "replaces",
                    }
                ]
            }
        )
    except IntakeWorkbenchError as exc:
        assert exc.code == "edge_language_or_reviewer_required"
    else:  # pragma: no cover
        raise AssertionError("unsupported graph edge must be rejected")
    receipt = store.receipt()
    assert len(receipt["orders_hash"]) == 64
    assert len(receipt["receipt_hash"]) == 64


def test_order_api_is_scoped_to_active_matter(monkeypatch, tmp_path: Path) -> None:
    case = tmp_path / "synthetic-case"
    case.mkdir()
    monkeypatch.setattr(api_module, "active_case_root", lambda: case)
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "synthetic-test-passphrase")
    client = TestClient(api_module.app)
    created = client.post(
        "/api/orders",
        json={
            "orders": [
                {
                    "order_id": "order_api",
                    "source_ref": {"record_id": "order_source_1"},
                    "terms": [
                        {
                            "term_id": "term_api",
                            "subject": "other",
                            "exact_language": "Synthetic term.",
                            "source_ref": {"record_id": "order_source_1"},
                        }
                    ],
                }
            ]
        },
    )
    assert created.status_code == 200
    assert client.get("/api/orders/terms").status_code == 200
    assert client.get("/api/orders/receipt").json()["review_required"] is True


def test_experimental_orders_markup_is_retained_but_not_publicly_navigable() -> None:
    html = render_local_workbench_html()
    script = read_workbench_asset("workbench.js")
    assert 'id="orders-workspace-overlay"' in html
    for label in ("Order inventory", "Supersession graph", "Term explorer", "Obligation ledger"):
        assert label in html
    assert "open_orders_workspace" not in script
    assert "never decides what order governs" in html
