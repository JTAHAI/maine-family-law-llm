from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from legal.drafting.outline_workbench import OutlineWorkbenchStore
from maine_family_law_llm import api as api_module


def _records() -> list[dict[str, object]]:
    return [
        {
            "evidence_id": "RECORD-FICTION-001",
            "title": "Fictional school communication",
            "source_locator": "fictional-school-message.txt",
            "source_hash": "a" * 64,
            "text": "Fictional message for source-bound review.",
            "page_number": 1,
        }
    ]


def _payload() -> dict[str, object]:
    return {
        "outline_id": "outline_001",
        "issue_id": "issue_001",
        "issue_label": "Fictional parenting-time issue",
        "purpose": "Organize fictional sources before any prose.",
        "reviewer_safe_id": "reviewer_001",
        "selected_evidence": [{"record_id": "RECORD-FICTION-001", "source_hash": "a" * 64, "page_number": 1}],
        "selected_authority": [{
            "authority_id": "authority_001",
            "source_id": "fictional-official-source",
            "source_hash": "b" * 64,
            "citation": "19-A M.R.S. fictional fixture",
            "title": "Fictional official authority fixture",
            "exact_span": "Fictional exact source span.",
        }],
        "user_confirmed": True,
    }


def test_pass72_persists_encrypted_separate_source_lanes_before_prose(tmp_path: Path) -> None:
    root = tmp_path / "fictional-matter"
    root.mkdir()
    store = OutlineWorkbenchStore(root, encryption_key="fictional-test-key")
    outline = store.create_outline(_payload(), records=_records())
    assert outline["review_required"] is True
    assert outline["draft_prose_created"] is False
    assert outline["filing_ready"] is False
    assert outline["evidence"][0]["lane"] == "private_matter_record"
    assert outline["authority"][0]["lane"] == "official_authority"
    assert "Fictional parenting-time issue" not in store.path.read_text(encoding="utf-8")
    assert store.evidence_source("outline_001", "RECORD-FICTION-001")["source"]["source_hash"] == "a" * 64
    assert store.authority_source("outline_001", "authority_001")["source"]["source_hash"] == "b" * 64


def test_pass72_refuses_unconfirmed_or_cross_matter_evidence(tmp_path: Path) -> None:
    root = tmp_path / "fictional-matter"
    root.mkdir()
    store = OutlineWorkbenchStore(root, encryption_key="fictional-test-key")
    unconfirmed = _payload() | {"user_confirmed": False}
    try:
        store.create_outline(unconfirmed, records=_records())
    except Exception as exc:
        assert str(exc) == "outline_confirmation_required"
    else:
        raise AssertionError("outline confirmation must be explicit")
    foreign = _payload() | {"selected_evidence": [{"record_id": "FOREIGN-RECORD", "source_hash": "a" * 64}]}
    try:
        store.create_outline(foreign, records=_records())
    except Exception as exc:
        assert str(exc) == "evidence_source_not_in_active_matter"
    else:
        raise AssertionError("cross-matter evidence must fail closed")


def test_pass72_canonical_api_scopes_sources_and_exposes_review_status(monkeypatch, tmp_path: Path) -> None:
    matter_a = tmp_path / "fictional-matter-a"
    matter_b = tmp_path / "fictional-matter-b"
    matter_a.mkdir()
    matter_b.mkdir()
    active = {"root": matter_a}
    monkeypatch.setattr(api_module, "active_case_root", lambda: active["root"])
    monkeypatch.setattr(api_module, "load_case_search_records", lambda _root: _records())
    monkeypatch.setattr(
        api_module,
        "inspect_source",
        lambda _source_id: {
            "status": "pass",
            "source_card": {
                "source_id": "fictional-official-source",
                "source_hash": "b" * 64,
                "citation": "19-A M.R.S. fictional fixture",
                "title": "Fictional official authority fixture",
                "freshness_status": "fresh",
                "source_span_preview": "Fictional exact source span.",
            },
        },
    )
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-test-key")
    client = TestClient(api_module.app)
    candidates = client.get("/api/drafting/outline-evidence-candidates")
    assert candidates.status_code == 200 and candidates.json()["candidates"][0]["record_id"] == "RECORD-FICTION-001"
    authority_candidate = client.get("/api/drafting/outline-authority-candidate/fictional-official-source")
    assert authority_candidate.status_code == 200
    assert authority_candidate.json()["candidate"]["source_hash"] == "b" * 64
    created = client.post("/api/drafting/outlines", json=_payload())
    assert created.status_code == 200
    outline = created.json()["outline"]
    assert outline["review_required"] is True and outline["filing_ready"] is False
    evidence = client.get("/api/drafting/outlines/outline_001/evidence/RECORD-FICTION-001/source")
    assert evidence.status_code == 200
    assert evidence.json()["source"]["source_hash"] == "a" * 64
    assert len(evidence.json()["source"]["source_token"]) == 64
    authority = client.get("/api/drafting/outlines/outline_001/authority/authority_001/source")
    assert authority.status_code == 200 and authority.json()["source"]["citation"] == "19-A M.R.S. fictional fixture"
    active["root"] = matter_b
    assert client.get("/api/drafting/outlines/outline_001").status_code == 404


def test_pass72_ships_mirrored_production_ui_with_actual_source_actions() -> None:
    src = Path("src/maine_family_law_llm/ui/workbench.js")
    mirror = Path("maine_family_law_llm/ui/workbench.js")
    api_src = Path("src/maine_family_law_llm/api.py")
    api_mirror = Path("maine_family_law_llm/api.py")
    assert src.read_bytes() == mirror.read_bytes()
    assert api_src.read_bytes() == api_mirror.read_bytes()
    text = src.read_text(encoding="utf-8")
    assert "Source-bound draft outline" in text
    assert "/api/drafting/outline-evidence-candidates" in text
    assert "/api/drafting/outlines" in text
    assert "Open exact private record" in text and "Open official source" in text
