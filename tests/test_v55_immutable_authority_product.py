from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from legal.production import AuthorityProductPublisher, AuthorityProductVerifier
from legal.documents.workspace import create_document
from legal.retrieval.index_builder import RetrievalIndexBuilder
from legal.verifiers import SourceAuthorityIndex, extract_citations


def _write_json(path: Path, payload) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture_data_root(tmp_path: Path) -> Path:
    root = tmp_path / "external-authority-data"
    official = root / "official_authority_store"
    snapshot = official / "snapshots" / "title19a.html"
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text("<h1>Title 19-A</h1><p>Section 1653 best interest.</p>", encoding="utf-8")

    _write_json(
        official / "source_manifest.json",
        [
            {
                "source_id": "maine-title-19a",
                "source_class": "statute_title_index",
                "jurisdiction": "maine",
                "retrieved_at": "2026-07-27T12:00:00+00:00",
                "hash": _sha(snapshot),
                "parser_status": "parsed",
                "freshness_status": "fresh",
                "data_class": "official_public_authority",
                "source_url_or_path": "https://legislature.maine.gov/statutes/19-a/",
                "snapshot_path": "snapshots/title19a.html",
                "parser_audit": {"status": "parsed"},
            }
        ],
    )

    parsed_row = root / "parsed_authority_store" / "statutes" / "statute_sections.jsonl"
    parsed_row.parent.mkdir(parents=True, exist_ok=True)
    parsed_row.write_text(
        json.dumps(
            {
                "record_id": "statute-19a-1653",
                "source_id": "maine-title-19a",
                "source_hash": _sha(snapshot),
                "source_class": "statute_section",
                "authority_kind": "statute_section",
                "jurisdiction": "maine",
                "freshness_status": "fresh",
                "parser_status": "parsed",
                "source_span": {"start_offset": 0, "end_offset": 20},
                "title": "Best interest of child",
                "citation": "19-A M.R.S. § 1653",
                "text": "Best interest factors.",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_json(
        root / "parsed_authority_store" / "parsed_authority_manifest.json",
        {
            "record_counts": {"statutes": 1, "rules": 0, "forms": 0, "opinions": 0},
            "output_files": {"statutes/statute_sections.jsonl": str(parsed_row)},
        },
    )

    citation_index = _write_json(
        root / "authority_layer" / "citation_index.json",
        [
            {
                "authority_status": "verified_official_maine",
                "candidate_count": 1,
                "candidate_rank": 1,
                "kind": "maine_statute",
                "normalized_citation": "19-A M.R.S. § 1653",
                "source_id": "statute-19a-1653",
                "metadata": {
                    "source_span": {"start_offset": 0, "end_offset": 20},
                    "pinpoint": "19-A M.R.S. § 1653",
                    "pinpoint_type": "statute_section",
                },
            }
        ],
    )
    source_cards = root / "authority_layer" / "source_cards.jsonl"
    source_cards.parent.mkdir(parents=True, exist_ok=True)
    source_cards.write_text(
        json.dumps(
            {
                "source_id": "statute-19a-1653",
                "hash": _sha(snapshot),
                "title": "Best interest of child",
                "citation": "19-A M.R.S. § 1653",
                "source_class": "statute_section",
                "authority_kind": "statute_section",
                "jurisdiction": "maine",
                "freshness_status": "fresh",
                "source_span": {"start_offset": 0, "end_offset": 20},
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    authority_graph = _write_json(root / "authority_layer" / "authority_graph.json", {})
    _write_json(
        root / "authority_layer" / "authority_layer_report.json",
        {
            "status": "pass",
            "outputs": {
                "citation_index": str(citation_index),
                "authority_graph": str(authority_graph),
                "source_cards": str(source_cards),
            },
        },
    )

    retrieval_docs = root / "embedding_store" / "hybrid" / "retrieval_documents.jsonl"
    retrieval_docs.parent.mkdir(parents=True, exist_ok=True)
    retrieval_docs.write_text("{}\n", encoding="utf-8")
    exact_lookup = _write_json(
        root / "embedding_store" / "hybrid" / "exact_citation_lookup.json",
        {"19-A M.R.S. § 1653": "statute-19a-1653"},
    )
    _write_json(
        root / "embedding_store" / "retrieval_index_manifest.json",
        {
            "status": "pass",
            "document_count": 1,
            "outputs": {
                "hybrid_documents": str(retrieval_docs),
                "exact_citation_lookup": str(exact_lookup),
            },
        },
    )
    _write_json(
        root / "source_update_report.json",
        {"status": "pass", "freshness_counts": {"fresh": 1, "stale": 0, "unknown": 0}},
    )
    return root


def test_publish_and_verify_immutable_authority_generation(tmp_path: Path) -> None:
    data_root = _fixture_data_root(tmp_path)
    publisher = AuthorityProductPublisher(data_root=data_root, repo_root=Path.cwd())

    first = publisher.publish(product_version="5.5.0")
    second = publisher.publish(product_version="5.5.0")

    assert first.status == "pass"
    assert first.build_id and len(first.build_id) == 24
    assert first.build_id == second.build_id
    assert Path(first.build_manifest_path).is_file()
    active = json.loads((data_root / "authority_product" / "ACTIVE_BUILD.json").read_text(encoding="utf-8"))
    assert active["build_id"] == first.build_id
    verified = AuthorityProductVerifier(data_root=data_root).verify()
    assert verified.status == "pass"
    assert verified.source_count == 1
    assert verified.artifact_count >= 6


def test_active_product_reports_exact_source_bound_drafting_coverage(tmp_path: Path, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from app.services import AuthorityLibraryService
    from app.services.authority_product_service import AuthorityProductService
    from maine_family_law_llm import api as desktop_api

    data_root = _fixture_data_root(tmp_path)
    assert AuthorityProductPublisher(data_root=data_root).publish(product_version="8.0.0").status == "pass"

    coverage = AuthorityProductService(data_root=data_root).direct_authority_coverage()
    assert coverage["status"] == "pass"
    assert coverage["counts_by_kind"]["statute_section"] == 1
    assert coverage["direct_exact_source_count"] == 1
    assert coverage["source_provided_pinpoint_count"] == 1
    assert coverage["source_bound_drafting_available"] is True
    assert coverage["current_law_determined"] is False

    choices = AuthorityProductService(data_root=data_root).drafting_source_candidates(
        "statute-19a-1653"
    )
    assert choices["status"] == "pass"
    assert len(choices["candidates"]) == 1
    assert choices["candidates"][0]["exact_span"] == "Best interest factor"
    assert choices["candidates"][0]["pinpoint"] == "19-A M.R.S. § 1653"

    monkeypatch.setenv("MAINE_FAMILY_LAW_DATA_ROOT", str(data_root))
    resolved = TestClient(desktop_api.app).get(
        "/api/drafting/outline-authority-candidate/statute-19a-1653"
    )
    assert resolved.status_code == 200
    assert resolved.json()["candidate"]["authority_id"] == choices["candidates"][0]["authority_id"]
    assert resolved.json()["candidate"]["exact_span"] == "Best interest factor"

    status = AuthorityLibraryService(data_root=data_root).status()
    assert status["direct_authority"] == coverage
    assert status["source_bound_drafting_available"] is True


def test_multiple_exact_pinpoints_require_a_reviewer_selection_before_citation_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The server never silently selects among multiple admitted source spans."""
    from fastapi.testclient import TestClient

    from maine_family_law_llm import api as desktop_api

    data_root = _fixture_data_root(tmp_path)
    _write_json(
        data_root / "authority_layer" / "citation_index.json",
        [
            {
                "authority_status": "verified_official_maine",
                "candidate_count": 2,
                "candidate_rank": 1,
                "kind": "maine_statute",
                "normalized_citation": "19-A M.R.S. § 1653",
                "source_id": "statute-19a-1653",
                "metadata": {
                    "source_span": {"start_offset": 0, "end_offset": 4},
                    "pinpoint": "19-A M.R.S. § 1653(A)",
                },
            },
            {
                "authority_status": "verified_official_maine",
                "candidate_count": 2,
                "candidate_rank": 2,
                "kind": "maine_statute",
                "normalized_citation": "19-A M.R.S. § 1653",
                "source_id": "statute-19a-1653",
                "metadata": {
                    "source_span": {"start_offset": 5, "end_offset": 13},
                    "pinpoint": "19-A M.R.S. § 1653(B)",
                },
            },
        ],
    )
    assert AuthorityProductPublisher(data_root=data_root).publish(product_version="8.0.0").status == "pass"
    matter = tmp_path / "fictional-matter"; matter.mkdir()
    monkeypatch.setenv("MAINE_FAMILY_LAW_DATA_ROOT", str(data_root))
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "fictional-test-key")
    monkeypatch.setattr(desktop_api, "active_case_root", lambda: matter)
    document = create_document(
        matter,
        title="Fictional citation draft",
        content="Fictional draft statement for review.",
        document_type="draft",
    )
    client = TestClient(desktop_api.app)
    resolved = client.get("/api/drafting/outline-authority-candidate/statute-19a-1653")
    assert resolved.status_code == 200
    payload = resolved.json()
    assert payload["candidate"]["pinpoint"] == ""
    assert len(payload["pinpoint_candidates"]) == 2
    base = {
        "reviewer_safe_id": "reviewer_001",
        "selected_text": "Fictional draft statement for review.",
        "authority": {"source_id": "statute-19a-1653"},
        "user_confirmed": True,
    }
    required = client.post(
        f"/api/drafting/documents/{document['document_id']}/citation-insertions", json=base
    )
    assert required.status_code == 409
    assert required.json()["detail"] == "citation_insertion_authority_selection_required"
    selected = dict(payload["pinpoint_candidates"][1])
    created = client.post(
        f"/api/drafting/documents/{document['document_id']}/citation-insertions",
        json=base | {"authority": {"source_id": "statute-19a-1653", "authority_id": selected["authority_id"]}},
    )
    assert created.status_code == 200
    assert created.json()["receipt"]["authority"]["pinpoint"] == selected["pinpoint"]
    assert created.json()["receipt"]["review_required"] is True


def test_active_generation_is_independent_of_mutable_workspace(tmp_path: Path) -> None:
    data_root = _fixture_data_root(tmp_path)
    published = AuthorityProductPublisher(data_root=data_root).publish(product_version="5.5.0")
    assert published.status == "pass"

    parsed = data_root / "parsed_authority_store" / "statutes" / "statute_sections.jsonl"
    parsed.write_text(parsed.read_text(encoding="utf-8") + "{}\n", encoding="utf-8")
    snapshot = data_root / "official_authority_store" / "snapshots" / "title19a.html"
    snapshot.write_text("mutable ingestion workspace changed", encoding="utf-8")

    verified = AuthorityProductVerifier(data_root=data_root).verify()
    assert verified.status == "pass"
    manifest = json.loads(Path(published.build_manifest_path).read_text(encoding="utf-8"))
    assert all("authority_product/builds/" in row["relative_path"] for row in manifest["source_snapshots"])
    assert all("authority_product/builds/" in row["relative_path"] for row in manifest["artifacts"])


def test_gap_review_and_drilldown_bind_to_verified_generation(tmp_path: Path, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from app.api.main import app as canonical_app
    from app.services import AuthorityLibraryService
    from app.services.authority_product_service import AuthorityProductService
    from maine_family_law_llm import api as desktop_api

    data_root = _fixture_data_root(tmp_path)
    published = AuthorityProductPublisher(data_root=data_root).publish(product_version="8.0.0")
    assert published.status == "pass"
    service = AuthorityProductService(data_root=data_root)
    initial = service.authority_gap_review()
    assert initial["record_count"] == 1
    assert initial["sources"][0]["source_id"] == "statute-19a-1653"

    library = AuthorityLibraryService(data_root=data_root)
    admitted_inventory = library.list_sources()
    assert admitted_inventory["status"] == "pass"
    assert admitted_inventory["build_id"] == published.build_id
    assert [row["source_id"] for row in admitted_inventory["sources"]] == ["maine-title-19a"]
    assert library.get_source("statute-19a-1653")["source_text"] == "Best interest factors."
    assert library.get_source_span("statute-19a-1653")["preview"] == "Best interest factor"

    mutable = data_root / "parsed_authority_store" / "statutes" / "statute_sections.jsonl"
    mutable.write_text('{"record_id":"UNADMITTED-CANARY","freshness_status":"fresh"}\n')
    assert service.authority_gap_review() == initial
    assert service.authority_gap_source("UNADMITTED-CANARY", build_id=published.build_id)["status"] == "not_found"
    assert [row["source_id"] for row in library.list_sources()["sources"]] == ["maine-title-19a"]
    assert library.get_source("UNADMITTED-CANARY")["status"] == "not_found"
    assert library.get_source_span("UNADMITTED-CANARY")["status"] == "not_found"
    assert service.authority_gap_source("statute-19a-1653", build_id="0" * 24)["status"] == "blocked"

    monkeypatch.setenv("MAINE_FAMILY_LAW_DATA_ROOT", str(data_root))
    path = f"/api/authority/gaps/sources/statute-19a-1653?build_id={published.build_id}"
    headers = {"X-User-Role": "reviewer", "X-Tenant-Id": "fictional-gap-tenant"}
    assert TestClient(canonical_app).get(path).status_code == 403
    for host in (canonical_app, desktop_api.app):
        result = TestClient(host).get(path, headers=headers)
        assert result.status_code == 200
        payload = result.json()
        assert payload["source_text"] == "Best interest factors."
        assert payload["source_span_preview"] == "Best interest factor"
        assert payload["review_required"] is True
        assert payload["build_id"] == published.build_id
        assert str(data_root) not in result.text
        if host is canonical_app:
            assert payload["audit_event"]["action"] == "authority_gap_source_review"

        inventory = TestClient(host).get("/api/authority/sources", headers=headers)
        assert inventory.status_code == 200
        assert [row["source_id"] for row in inventory.json()["sources"]] == ["maine-title-19a"]
        assert TestClient(host).get("/api/authority/sources/UNADMITTED-CANARY", headers=headers).json()["status"] == "not_found"

    manifest = json.loads(Path(published.build_manifest_path).read_text())
    artifact = next(row for row in manifest["artifacts"] if "parsed_collection:" in row["role"])
    (data_root / artifact["relative_path"]).write_text("{}\n")
    with pytest.raises(ValueError, match="mismatch"):
        service.authority_gap_review()
    assert TestClient(desktop_api.app).get(path).json()["status"] == "blocked"


def test_authority_generation_fails_closed_after_materialized_artifact_tamper(tmp_path: Path) -> None:
    data_root = _fixture_data_root(tmp_path)
    published = AuthorityProductPublisher(data_root=data_root).publish(product_version="5.5.0")
    assert published.status == "pass"

    manifest = json.loads(Path(published.build_manifest_path).read_text(encoding="utf-8"))
    artifact = data_root / manifest["artifacts"][0]["relative_path"]
    artifact.write_bytes(artifact.read_bytes() + b"tamper")

    verified = AuthorityProductVerifier(data_root=data_root).verify()
    assert verified.status == "blocked"
    assert "authority_product_hash_mismatch" in verified.blockers


def test_authority_generation_rejects_symlinked_snapshot(tmp_path: Path) -> None:
    data_root = _fixture_data_root(tmp_path)
    snapshot = data_root / "official_authority_store" / "snapshots" / "title19a.html"
    replacement = tmp_path / "replacement.html"
    replacement.write_text(snapshot.read_text(encoding="utf-8"), encoding="utf-8")
    snapshot.unlink()
    try:
        snapshot.symlink_to(replacement)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")

    report = AuthorityProductPublisher(data_root=data_root).publish(product_version="5.5.0")
    assert report.status == "blocked"
    assert "authority_snapshot_invalid" in report.blockers


def test_common_maine_citation_variants_normalize_to_one_key() -> None:
    variants = [
        "19-A M.R.S. § 1653(3)(A)",
        "19-A MRSA §1653(3)(A)",
        "19-A MRS § 1653(3)(A)",
        "Title 19-A, § 1653(3)(A)",
    ]
    normalized = {extract_citations(text)[0].normalized for text in variants}
    assert normalized == {"19-A M.R.S. § 1653(3)(A)"}
    case = extract_citations("2026 ME 12, ¶ 14")[0]
    assert case.normalized == "2026 ME 12"
    assert case.pinpoint == "¶ 14"


def test_citation_index_retains_and_ranks_multiple_candidates() -> None:
    citation = extract_citations("Title 19-A § 1653")[0]
    index = SourceAuthorityIndex()
    index.add(
        kind=citation.kind,
        normalized_citation=citation.normalized,
        source_id="index-reference",
        authority_status="verified_official_maine",
        metadata={"source_class": "statute_title_index", "freshness_status": "fresh"},
    )
    index.add(
        kind=citation.kind,
        normalized_citation=citation.normalized,
        source_id="direct-section",
        authority_status="verified_official_maine",
        metadata={"source_class": "statute_section", "freshness_status": "fresh"},
    )

    result = index.resolve(citation)
    assert result.status == "found"
    assert result.source_id == "direct-section"
    assert [candidate["source_id"] for candidate in result.candidates] == ["direct-section", "index-reference"]
    assert result.metadata["candidate_count"] == 2


def test_retrieval_index_writes_candidate_lookup_and_hash_manifest(tmp_path: Path) -> None:
    data_root = tmp_path / "external"
    parsed = data_root / "parsed_authority_store" / "statutes" / "statute_sections.jsonl"
    parsed.parent.mkdir(parents=True)
    rows = [
        {
            "record_id": source_id,
            "source_id": source_id,
            "source_hash": f"hash-{source_id}",
            "source_class": source_class,
            "authority_kind": "statute_section" if source_class == "statute_section" else "statute_section_reference",
            "jurisdiction": "maine",
            "freshness_status": "fresh",
            "parser_status": "parsed",
            "source_span": {"start_offset": 0, "end_offset": 20},
            "title": title,
            "citation": "19-A M.R.S. § 1653",
            "text": "Best interest factors.",
        }
        for source_id, source_class, title in (
            ("index", "statute_title_index", "Index reference"),
            ("direct", "statute_section", "Direct section"),
        )
    ]
    parsed.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")

    report = RetrievalIndexBuilder(data_root=data_root).build()
    assert report.status == "pass"
    lookup = json.loads((data_root / "embedding_store" / "hybrid" / "exact_citation_lookup.json").read_text())
    candidates = json.loads((data_root / "embedding_store" / "hybrid" / "exact_citation_candidates.json").read_text())
    assert isinstance(lookup["19-A M.R.S. § 1653"], list)
    assert candidates["Title 19-A § 1653"] == ["direct", "index"]
    manifest = json.loads((data_root / "embedding_store" / "retrieval_index_manifest.json").read_text())
    assert manifest["artifact_hash_algorithm"] == "sha256"
    assert any(key.replace("\\", "/") == "hybrid/exact_citation_candidates.json" for key in manifest["artifact_hashes"])


def test_authority_product_service_exposes_verified_status_citations_and_source(tmp_path: Path) -> None:
    from app.services import AuthorityProductService

    data_root = _fixture_data_root(tmp_path)
    # Replace fixture source cards and citation index with one useful admitted source.
    citation_rows = [
        {
            "kind": "maine_statute",
            "normalized_citation": "19-A M.R.S. § 1653",
            "source_id": "statute-19a-1653",
            "authority_status": "verified_official_maine",
            "metadata": {"source_class": "statute_section", "freshness_status": "fresh"},
        }
    ]
    _write_json(data_root / "authority_layer" / "citation_index.json", citation_rows)
    (data_root / "authority_layer" / "source_cards.jsonl").write_text(
        json.dumps(
            {
                "source_id": "statute-19a-1653",
                "title": "Best interest of child",
                "citation": "19-A M.R.S. § 1653",
                "source_url_or_path": "https://legislature.maine.gov/statutes/19-a/title19-Asec1653.html",
                "snapshot_path": "/private/local/path.html",
                "freshness_status": "fresh",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (data_root / "embedding_store" / "hybrid" / "retrieval_documents.jsonl").write_text(
        json.dumps({"source_id": "statute-19a-1653", "text": "Best interest factors."}) + "\n",
        encoding="utf-8",
    )
    published = AuthorityProductPublisher(data_root=data_root).publish(product_version="5.5.0")
    assert published.status == "pass"

    service = AuthorityProductService(data_root=data_root)
    status = service.status()
    assert status["active"] is True
    assert status["build_id"] == published.build_id
    resolution = service.resolve_citations("Title 19-A § 1653")
    assert resolution["resolutions"][0]["source_id"] == "statute-19a-1653"
    source = service.get_source("statute-19a-1653")
    assert source["source_text"] == "Best interest factors."
    assert "snapshot_path" not in source["source_card"]
    inventory = service.list_sources()
    assert [row["source_id"] for row in inventory["sources"]] == ["statute-19a-1653"]
    assert service.get_source_span("statute-19a-1653", start_offset=0, end_offset=13)["source_span_preview"] == "Best interest"

    # A staged canary must never appear through active-build source helpers.
    (data_root / "parsed_authority_store" / "statutes" / "statute_sections.jsonl").write_text(
        '{"record_id":"UNADMITTED-CANARY","text":"mutable only"}\n', encoding="utf-8"
    )
    assert [row["source_id"] for row in service.list_sources()["sources"]] == ["statute-19a-1653"]
    assert service.get_source_span("UNADMITTED-CANARY", start_offset=0, end_offset=10)["status"] == "not_found"


def test_failed_materialization_does_not_replace_active_pointer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_root = _fixture_data_root(tmp_path)
    publisher = AuthorityProductPublisher(data_root=data_root)
    first = publisher.publish(product_version="5.5.0")
    assert first.status == "pass"
    pointer_before = (data_root / "authority_product" / "ACTIVE_BUILD.json").read_bytes()

    # Change a control artifact so publication targets a new generation.
    report_path = data_root / "source_update_report.json"
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    payload["generation_note"] = "new candidate"
    _write_json(report_path, payload)

    def fail_copy(*args, **kwargs):
        raise ValueError("simulated materialization failure")

    monkeypatch.setattr(AuthorityProductPublisher, "_copy_verified", staticmethod(fail_copy))
    failed = publisher.publish(product_version="5.5.0")
    assert failed.status == "blocked"
    assert "authority_build_materialization_failed" in failed.blockers
    assert (data_root / "authority_product" / "ACTIVE_BUILD.json").read_bytes() == pointer_before
    assert AuthorityProductVerifier(data_root=data_root).verify().status == "pass"
