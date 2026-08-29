from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from maine_family_law_llm import api as api_module


def _records() -> list[dict[str, object]]:
    return [
        {"evidence_id": "ORDER-ONE", "title": "Fictional order", "source_type": "order", "source_hash": "a" * 64, "text": "Fictional order text.", "page_number": 1},
        {"evidence_id": "EMAIL-ONE", "title": "Fictional email", "source_type": "email", "source_hash": "b" * 64, "text": "Fictional email text.", "page_number": 2},
    ]


def _client(monkeypatch, case_root: Path, rows: list[dict[str, object]] | None = None) -> TestClient:
    monkeypatch.setattr(api_module, "active_case_root", lambda: case_root)
    monkeypatch.setattr(api_module, "load_case_search_records", lambda _root: rows or _records())
    return TestClient(api_module.app)


def test_fact_graph_links_source_bound_disputed_nodes_and_edges(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "fictional-matter"; case_root.mkdir(); client = _client(monkeypatch, case_root)
    first = client.post("/api/evidence/fact-graph/nodes", json={"node_id": "ORDER", "node_kind": "order", "label": "Fictional order", "fact_state": "observed", "source_record_id": "ORDER-ONE"})
    second = client.post("/api/evidence/fact-graph/nodes", json={"node_id": "ASSERTION", "node_kind": "assertion", "label": "Fictional assertion", "fact_state": "disputed", "source_record_id": "EMAIL-ONE"})
    assert first.status_code == second.status_code == 200
    edge = client.post("/api/evidence/fact-graph/edges", json={"edge_id": "EDGE", "source_node_id": "ORDER", "target_node_id": "ASSERTION", "relationship": "contradicts", "fact_state": "disputed", "source_record_id": "EMAIL-ONE"})
    assert edge.status_code == 200 and edge.json()["edge"]["review_required"] is True
    graph = client.get("/api/evidence/fact-graph")
    assert graph.status_code == 200 and graph.json()["state_counts"]["disputed"] == 2
    source = client.get("/api/evidence/fact-graph/edges/EDGE/source")
    assert source.status_code == 200 and len(source.json()["source"]["source_token"]) == 64


def test_fact_graph_fails_closed_for_foreign_source_and_missing_edge_node(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "fictional-matter"; case_root.mkdir(); client = _client(monkeypatch, case_root)
    foreign = client.post("/api/evidence/fact-graph/nodes", json={"node_id": "FOREIGN", "node_kind": "event", "label": "Fictional event", "source_record_id": "OTHER-MATTER"})
    assert foreign.status_code == 400 and foreign.json()["detail"] == "source_record_not_found_in_active_matter"
    missing = client.post("/api/evidence/fact-graph/edges", json={"edge_id": "EDGE", "source_node_id": "A", "target_node_id": "B", "relationship": "supports", "source_record_id": "EMAIL-ONE"})
    assert missing.status_code == 400 and missing.json()["detail"] == "fact_graph_edge_node_not_found"


def test_fact_graph_ui_is_in_both_shipped_workbench_copies() -> None:
    root = Path(__file__).resolve().parents[1]
    src_ui = (root / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_text(encoding="utf-8")
    mirror_ui = (root / "maine_family_law_llm" / "ui" / "workbench.js").read_text(encoding="utf-8")
    assert src_ui == mirror_ui
    assert "installFactGraphControl" in src_ui and "/api/evidence/fact-graph" in src_ui and "Disputed" in src_ui
