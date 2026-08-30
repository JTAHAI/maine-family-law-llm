from pathlib import Path

from fastapi.testclient import TestClient

from legal.drafting.argument_matrix import ArgumentMatrixStore
from maine_family_law_llm import api as api_module


def _records():
    return [{
        "evidence_id": "RECORD-FICTION-001",
        "title": "Fictional school communication",
        "source_locator": "fictional-school-message.txt",
        "source_hash": "a" * 64,
        "text": "Fictional message for source-bound reviewer comparison.",
        "page_number": 1,
    }]


def _authority():
    return {
        "authority_id": "authority_001",
        "source_id": "fictional-official-source",
        "source_hash": "b" * 64,
        "citation": "Fictional Maine authority fixture",
        "title": "Fictional official authority fixture",
        "exact_span": "Fictional exact official source span.",
        "freshness_status": "fresh",
    }


def _payload():
    evidence = {"record_id": "RECORD-FICTION-001", "source_hash": "a" * 64, "page_number": 1}
    return {
        "matrix_id": "position_matrix_001",
        "issue_label": "Fictional parenting-time issue",
        "reviewer_safe_id": "reviewer_001",
        "positions": [
            {
                "position_id": "position_a",
                "label": "Fictional position A",
                "statement": "Fictional reviewer-entered position A statement.",
                "supporting_evidence": [evidence],
                "supporting_authority": [_authority()],
                "weaknesses": ["Context needs reviewer inspection."],
                "missing_proof": [],
            },
            {
                "position_id": "position_b",
                "label": "Fictional position B",
                "statement": "Fictional reviewer-entered position B statement.",
                "supporting_evidence": [evidence],
                "supporting_authority": [_authority()],
                "weaknesses": [],
                "missing_proof": ["Fictional missing attachment."],
            },
        ],
        "user_confirmed": True,
    }


def test_pass79_encrypted_matrix_keeps_positions_and_lanes_separate(tmp_path: Path):
    root = tmp_path / "fictional-matter"
    root.mkdir()
    store = ArgumentMatrixStore(root, encryption_key="fictional-test-key")
    matrix = store.create(_payload(), records=_records())
    assert matrix["review_required"] is True
    assert matrix["filing_ready"] is False
    assert matrix["outcome_prediction"] is False
    assert matrix["positions"][0]["supporting_evidence"][0]["lane"] == "private_matter_record"
    assert matrix["positions"][0]["supporting_authority"][0]["lane"] == "official_authority"
    assert "Fictional reviewer-entered" not in store.path.read_text(encoding="utf-8")
    assert store.source("position_matrix_001", "position_a", "private_matter_record", "RECORD-FICTION-001")["source"]["source_hash"] == "a" * 64
    assert store.source("position_matrix_001", "position_a", "official_authority", "authority_001")["source"]["source_hash"] == "b" * 64


def test_pass79_refuses_unconfirmed_and_foreign_matter_evidence(tmp_path: Path):
    root = tmp_path / "fictional-matter"
    root.mkdir()
    store = ArgumentMatrixStore(root, encryption_key="fictional-test-key")
    try:
        store.create(_payload() | {"user_confirmed": False}, records=_records())
    except Exception as exc:
        assert str(exc) == "argument_matrix_confirmation_required"
    else:
        raise AssertionError("explicit confirmation is required")
    foreign = _payload()
    foreign["positions"][0]["supporting_evidence"] = [{"record_id": "FOREIGN-RECORD", "source_hash": "a" * 64}]
    try:
        store.create(foreign, records=_records())
    except Exception as exc:
        assert str(exc) == "argument_matrix_evidence_not_in_active_matter"
    else:
        raise AssertionError("a foreign record must fail closed")


def test_pass79_canonical_api_resolves_sources_and_scopes_the_matter(monkeypatch, tmp_path: Path):
    matter_a, matter_b = tmp_path / "matter-a", tmp_path / "matter-b"
    matter_a.mkdir()
    matter_b.mkdir()
    active = {"root": matter_a}
    monkeypatch.setattr(api_module, "active_case_root", lambda: active["root"])
    monkeypatch.setattr(api_module, "load_case_search_records", lambda _root: _records())
    monkeypatch.setattr(
        api_module,
        "inspect_source",
        lambda _source_id: {"status": "pass", "source_card": {**_authority(), "source_span_preview": "Fictional exact official source span."}},
    )
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-test-key")
    client = TestClient(api_module.app)
    tampered = _payload()
    tampered["positions"][0]["supporting_authority"][0]["source_hash"] = "c" * 64
    assert client.post("/api/drafting/argument-matrices", json=tampered).status_code == 409
    created = client.post("/api/drafting/argument-matrices", json=_payload())
    assert created.status_code == 200
    matrix = created.json()["matrix"]
    assert matrix["review_required"] is True and matrix["outcome_prediction"] is False
    private = client.get("/api/drafting/argument-matrices/position_matrix_001/positions/position_a/private_matter_record/RECORD-FICTION-001/source")
    assert private.status_code == 200 and len(private.json()["source"]["source_token"]) == 64
    authority_id = matrix["positions"][0]["supporting_authority"][0]["authority_id"]
    official = client.get(f"/api/drafting/argument-matrices/position_matrix_001/positions/position_a/official_authority/{authority_id}/source")
    assert official.status_code == 200 and official.json()["source"]["citation"] == "Fictional Maine authority fixture"
    active["root"] = matter_b
    assert client.get("/api/drafting/argument-matrices/position_matrix_001").status_code == 404


def test_pass79_mirrored_production_ui_exposes_actions():
    assert Path("src/maine_family_law_llm/api.py").read_bytes() == Path("maine_family_law_llm/api.py").read_bytes()
    assert Path("src/maine_family_law_llm/ui/workbench.js").read_bytes() == Path("maine_family_law_llm/ui/workbench.js").read_bytes()
    text = Path("src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    assert "Argument / counterargument matrix" in text
    assert "Create source-bound matrix" in text
    assert "/api/drafting/argument-matrices" in text
    assert "Open private record" in text and "Open official source" in text
    assert "argument-matrix-pinpoint-choice" in text
    assert "The matrix will not select legal language for you." in text
