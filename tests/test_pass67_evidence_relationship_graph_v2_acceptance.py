from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from maine_family_law_llm import api as api_module


def _records() -> list[dict[str, object]]:
    return [
        {"evidence_id": "RECORD-A", "title": "Fictional record A", "source_hash": "a" * 64, "text": "Fictional A", "page_number": 1},
        {"evidence_id": "RECORD-B", "title": "Fictional record B", "source_hash": "b" * 64, "text": "Fictional B", "page_number": 2},
    ]


def _client(monkeypatch, case_root: Path) -> TestClient:
    monkeypatch.setattr(api_module, "active_case_root", lambda: case_root)
    monkeypatch.setattr(api_module, "load_case_search_records", lambda _root: _records())
    return TestClient(api_module.app)


def test_pass67_records_each_v2_relationship_with_exact_active_matter_provenance(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "fictional-matter"; root.mkdir(); client = _client(monkeypatch, root)
    for node_id, record_id in (("NODE_A", "RECORD-A"), ("NODE_B", "RECORD-B")):
        response = client.post("/api/evidence/fact-graph/nodes", json={"node_id": node_id, "node_kind": "record", "label": f"Fictional {node_id}", "source_record_id": record_id, "fact_state": "not_yet_reviewed"})
        assert response.status_code == 200
    relationships = ("temporal_before", "attachment_of", "reply_to", "duplicate_of", "contradicts", "derivative_of")
    for index, relationship in enumerate(relationships, start=1):
        response = client.post("/api/evidence/fact-graph/edges", json={"edge_id": f"EDGE_{index}", "source_node_id": "NODE_A", "target_node_id": "NODE_B", "relationship": relationship, "source_record_id": "RECORD-A", "fact_state": "disputed", "relationship_basis": "exact_source_span", "relationship_note": "Fictional reviewer note."})
        assert response.status_code == 200
        edge = response.json()["edge"]
        assert edge["relationship"] == relationship
        assert edge["source_hash"] == "a" * 64
        assert edge["relationship_basis"] == "exact_source_span"
        assert edge["review_required"] is True
    graph = client.get("/api/evidence/fact-graph").json()
    assert {edge["relationship"] for edge in graph["edges"]} >= set(relationships)
    source = client.get("/api/evidence/fact-graph/edges/EDGE_6/source")
    assert source.status_code == 200 and len(source.json()["source"]["source_token"]) == 64


def test_pass67_rejects_unknown_relationship_and_bad_active_matter_provenance(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "fictional-matter"; root.mkdir(); client = _client(monkeypatch, root)
    for node_id in ("NODE_A", "NODE_B"):
        assert client.post("/api/evidence/fact-graph/nodes", json={"node_id": node_id, "node_kind": "record", "label": node_id, "source_record_id": "RECORD-A"}).status_code == 200
    bad_type = client.post("/api/evidence/fact-graph/edges", json={"edge_id": "BAD_TYPE", "source_node_id": "NODE_A", "target_node_id": "NODE_B", "relationship": "proves", "source_record_id": "RECORD-A"})
    assert bad_type.status_code == 400 and bad_type.json()["detail"] == "fact_graph_relationship_invalid"
    foreign = client.post("/api/evidence/fact-graph/edges", json={"edge_id": "FOREIGN", "source_node_id": "NODE_A", "target_node_id": "NODE_B", "relationship": "reply_to", "source_record_id": "OUTSIDE"})
    assert foreign.status_code == 400 and foreign.json()["detail"] == "source_record_not_found_in_active_matter"


def test_pass67_ships_the_v2_relationship_control_in_mirrored_workbench_assets() -> None:
    src = Path("src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    mirror = Path("maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    assert src == mirror
    assert "Evidence relationship graph v2" in src
    for relationship in ("temporal_before", "attachment_of", "reply_to", "duplicate_of", "contradicts", "derivative_of"):
        assert relationship in src
    assert "/api/evidence/fact-graph/edges" in src
