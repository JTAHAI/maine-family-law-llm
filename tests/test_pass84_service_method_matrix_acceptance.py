from pathlib import Path

from fastapi.testclient import TestClient

from legal.matter.service_method_matrix import ServiceMethodMatrixStore
from maine_family_law_llm import api as api_module


def _records():
    return [{
        "evidence_id": "SERVICE-PROOF-001",
        "title": "Fictional return of service",
        "source_locator": "fictional-service-proof.pdf",
        "source_hash": "a" * 64,
        "page_number": 3,
        "text": "Fictional proof text only.",
    }]


def _authority():
    return {
        "authority_id": "authority_001",
        "source_id": "fictional-official-source",
        "source_hash": "b" * 64,
        "citation": "Fictional Maine service authority fixture",
        "title": "Fictional official service authority",
        "exact_span": "Fictional exact authority span.",
        "freshness_status": "fresh",
    }


def _payload():
    return {
        "matrix_id": "service_matrix_001",
        "reviewer_safe_id": "reviewer_001",
        "selected_method": "mail_service",
        "proof": {"record_id": "SERVICE-PROOF-001", "source_hash": "a" * 64, "page_number": 3},
        "authority_source_id": "fictional-official-source",
        "exceptions": ["Recipient identity requires review."],
        "unresolved_facts": ["Mailing date has not been independently confirmed."],
        "user_confirmed": True,
    }


def test_pass84_encrypted_matrix_keeps_method_proof_authority_and_unknowns_separate(tmp_path: Path):
    root = tmp_path / "fictional-matter"; root.mkdir()
    store = ServiceMethodMatrixStore(root, encryption_key="fictional-test-key")
    matrix = store.create(_payload(), records=_records(), authority=_authority())
    assert matrix["review_required"] is True and matrix["filing_ready"] is False
    assert matrix["service_effectiveness"] == "not_determined"
    assert matrix["proof"]["lane"] == "private_matter_record"
    assert matrix["authority"]["lane"] == "official_authority"
    assert "Fictional return of service" not in store.path.read_text(encoding="utf-8")
    assert store.source("service_matrix_001", "private_matter_record")["source"]["source_hash"] == "a" * 64
    assert store.source("service_matrix_001", "official_authority")["source"]["source_hash"] == "b" * 64


def test_pass84_refuses_unconfirmed_foreign_and_unknown_method(tmp_path: Path):
    root = tmp_path / "fictional-matter"; root.mkdir()
    store = ServiceMethodMatrixStore(root, encryption_key="fictional-test-key")
    try:
        store.create(_payload() | {"user_confirmed": False}, records=_records(), authority=_authority())
    except Exception as exc:
        assert str(exc) == "service_method_matrix_confirmation_required"
    else:
        raise AssertionError("explicit reviewer confirmation is required")
    foreign = _payload(); foreign["proof"] = {"record_id": "FOREIGN", "source_hash": "a" * 64}
    try:
        store.create(foreign, records=_records(), authority=_authority())
    except Exception as exc:
        assert str(exc) == "service_proof_not_in_active_matter"
    else:
        raise AssertionError("foreign proof must fail closed")
    try:
        store.create(_payload() | {"selected_method": "invented_service"}, records=_records(), authority=_authority())
    except Exception as exc:
        assert str(exc) == "service_method_invalid"
    else:
        raise AssertionError("unknown method must fail closed")
    invalid_page = _payload(); invalid_page["proof"] = {"record_id": "SERVICE-PROOF-001", "source_hash": "a" * 64, "page_number": "not-a-page"}
    try:
        store.create(invalid_page, records=_records(), authority=_authority())
    except Exception as exc:
        assert str(exc) == "service_proof_page_invalid"
    else:
        raise AssertionError("malformed proof metadata must fail closed")


def test_pass84_canonical_api_resolves_authority_and_scopes_sources(monkeypatch, tmp_path: Path):
    matter_a, matter_b = tmp_path / "matter-a", tmp_path / "matter-b"; matter_a.mkdir(); matter_b.mkdir()
    active = {"root": matter_a}
    monkeypatch.setattr(api_module, "active_case_root", lambda: active["root"])
    monkeypatch.setattr(api_module, "load_case_search_records", lambda _root: _records())
    monkeypatch.setattr(api_module, "inspect_source", lambda _source: {"status": "pass", "source_card": {**_authority(), "source_span_preview": "Fictional exact authority span."}})
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-test-key")
    client = TestClient(api_module.app)
    created = client.post("/api/service-method-matrices", json=_payload())
    assert created.status_code == 200
    matrix = created.json()["matrix"]
    proof = client.get("/api/service-method-matrices/service_matrix_001/private_matter_record/source")
    assert proof.status_code == 200 and len(proof.json()["source"]["source_token"]) == 64
    official = client.get("/api/service-method-matrices/service_matrix_001/official_authority/source")
    assert official.status_code == 200 and official.json()["source"]["citation"] == "Fictional Maine service authority fixture"
    assert matrix["service_effectiveness"] == "not_determined"
    active["root"] = matter_b
    assert client.get("/api/service-method-matrices/service_matrix_001").status_code == 404


def test_pass84_production_assets_are_mirrored_and_operable():
    assert Path("src/maine_family_law_llm/api.py").read_bytes() == Path("maine_family_law_llm/api.py").read_bytes()
    assert Path("src/maine_family_law_llm/ui/workbench.js").read_bytes() == Path("maine_family_law_llm/ui/workbench.js").read_bytes()
    text = Path("src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    assert "Service-method rules matrix" in text
    assert "/api/service-method-matrices" in text
    assert "Open proof record" in text and "Open official source" in text
