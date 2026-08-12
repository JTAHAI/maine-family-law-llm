from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from maine_family_law_llm import api as api_module


def test_retrieval_workbench_api_searches_active_private_index(monkeypatch, tmp_path: Path):
    case = tmp_path / "case"
    index = case / "04_INDEXES"
    index.mkdir(parents=True)
    (index / "private_search_index.json").write_text(
        json.dumps([
            {
                "evidence_id": "record-school",
                "title": "School email",
                "snippet": "The child changed schools on January 3, 2026.",
                "page_number": 1,
                "source_hash": "a" * 64,
            }
        ]),
        encoding="utf-8",
    )
    monkeypatch.setattr(api_module, "active_case_root", lambda: case)
    client = TestClient(api_module.app)

    status = client.get("/api/retrieval-workbench/status")
    assert status.status_code == 200
    assert status.json()["private_record_count"] == 1
    assert status.json()["automatic_network_calls"] is False

    result = client.post(
        "/api/retrieval-workbench/search",
        json={"query": "changed schools", "include_private_records": True, "include_authority": False, "top_k": 5},
    )
    assert result.status_code == 200
    payload = result.json()
    assert payload["status"] == "pass"
    assert payload["results"][0]["source_id"] == "record-school"
    assert payload["diagnostics"]["network_used"] is False


def test_retrieval_workbench_evaluation_fails_closed_without_external_roots(monkeypatch, tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    monkeypatch.setattr(api_module, "active_case_root", lambda: case)
    monkeypatch.delenv("MFL_EVAL_ROOT", raising=False)
    monkeypatch.delenv("MFL_AUTHORITY_DATA_ROOT", raising=False)
    client = TestClient(api_module.app)
    response = client.post("/api/retrieval-workbench/evaluate", json={"min_attorney_rows": 1, "top_k": 20})
    assert response.status_code == 409
    assert response.json()["detail"] == "eval_root_not_configured"


def test_retrieval_workbench_ui_and_mirrors_are_present():
    html = Path("maine_family_law_llm/ui/workbench.html").read_text(encoding="utf-8")
    js = Path("maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    css = Path("maine_family_law_llm/ui/workbench.css").read_text(encoding="utf-8")
    assert 'id="record-inspector-retrieval-workbench"' in html
    assert 'id="retrieval-workbench-modal"' in html
    assert "/api/retrieval-workbench/search" in js
    assert "renderRetrievalEvaluation" in js
    assert ".retrieval-workbench-modal" in css
    assert Path("src/maine_family_law_llm/ui/workbench.html").read_text(encoding="utf-8") == html
    assert Path("src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8") == js
    assert Path("src/maine_family_law_llm/ui/workbench.css").read_text(encoding="utf-8") == css
