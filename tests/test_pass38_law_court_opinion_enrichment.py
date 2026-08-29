from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app as canonical_app
from app.api.routes import authority as authority_routes
from app.services.authority_product_service import ActiveAuthorityProduct, AuthorityProductService
from maine_family_law_llm import api as frozen_api


ROOT = Path(__file__).resolve().parents[1]
HEADERS = {"X-User-Role": "reviewer", "X-Tenant-Id": "tenant-opinion-enrichment"}


def _active_product(tmp_path: Path) -> ActiveAuthorityProduct:
    manifest_path = tmp_path / "authority_product_manifest.json"
    manifest = {
        "schema_version": "1.1",
        "build_id": "a" * 24,
        "build_fingerprint": "b" * 64,
        "source_snapshots": [
            {
                "source_id": "opinion-snapshot-2026-me-1",
                "relative_path": "authority_product/builds/a/sources/000001.pdf",
                "sha256": "c" * 64,
                "size": 100,
            }
        ],
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return ActiveAuthorityProduct(tmp_path, "a" * 24, manifest_path, manifest)


def _opinion_row(*, include_paragraphs: bool = True) -> dict:
    text = (
        "Fictional Parent v. Fictional Parent\n"
        "Docket: FAM-25-12\n"
        "Decided: May 1, 2026\n"
        "¶ 1 The Court considered 19-A M.R.S. § 1653 and 2025 ME 4.\n"
        "¶ 2 We vacate and remand because the order lacked required findings under M.R. Civ. P. 52.\n"
    )
    if not include_paragraphs:
        text = text.replace("¶ 1 ", "").replace("¶ 2 ", "")
    return {
        "record_id": "law-court-2026-me-1",
        "source_id": "opinion-snapshot-2026-me-1",
        "source_hash": "c" * 64,
        "source_class": "law_court_opinion_pdf",
        "authority_kind": "law_court_opinion",
        "jurisdiction": "maine",
        "citation": "2026 ME 1",
        "title": "Fictional Parent v. Fictional Parent",
        "decision_date": "May 1, 2026",
        "docket_number": "FAM-25-12",
        "court": "Maine Supreme Judicial Court sitting as the Law Court",
        "source_span": {"start_offset": 100, "end_offset": 100 + len(text)},
        "source_url_or_path": "https://www.courts.maine.gov/opinions/2026/2026-me-1.pdf",
        "text": text,
        "_parsed_relative_path": "opinions/opinions.jsonl",
        "_parsed_line_number": 1,
    }


def test_pass38_enriches_admitted_opinion_with_exact_paragraph_and_citation_spans(monkeypatch, tmp_path: Path) -> None:
    service = AuthorityProductService(data_root=tmp_path)
    monkeypatch.setattr(service, "_active_product", lambda *, verify_all: _active_product(tmp_path))
    monkeypatch.setattr(service, "_iter_active_parsed_rows", lambda _active: iter([_opinion_row()]))

    result = service.law_court_opinion_enrichment("law-court-2026-me-1")

    assert result["status"] == "enrichment_observed"
    assert result["review_required"] is True
    assert result["network_used"] is False
    assert result["current_law_determined"] is False
    assert result["treatment_determined"] is False
    opinion = result["opinion"]
    assert opinion["docket_number"] == "FAM-25-12"
    assert opinion["disposition"]["value"] in {"vacated", "remanded"}
    assert opinion["disposition"]["source_span"]["start_offset"] >= 100
    assert [row["paragraph"] for row in opinion["paragraph_map"]] == ["1", "2"]
    assert any(item["citation"]["normalized"] == "19-A M.R.S. § 1653" for item in opinion["cited_authorities"])
    assert opinion["neutral_case_summary"]["status"] == "exact_source_excerpt"
    assert opinion["neutral_case_summary"]["text"].startswith("¶ 1")


def test_pass38_missing_paragraph_map_fails_closed_as_review_required(monkeypatch, tmp_path: Path) -> None:
    service = AuthorityProductService(data_root=tmp_path)
    monkeypatch.setattr(service, "_active_product", lambda *, verify_all: _active_product(tmp_path))
    monkeypatch.setattr(service, "_iter_active_parsed_rows", lambda _active: iter([_opinion_row(include_paragraphs=False)]))

    result = service.law_court_opinion_enrichment("law-court-2026-me-1")

    assert result["status"] == "needs_review"
    assert "opinion_paragraph_map_unavailable" in result["blockers"]
    assert result["review_required"] is True


def test_pass38_replacement_glyph_paragraph_marker_remains_source_bound(monkeypatch, tmp_path: Path) -> None:
    service = AuthorityProductService(data_root=tmp_path)
    row = _opinion_row()
    row["text"] = row["text"].replace("¶ 1", "[\ufffd1]").replace("¶ 2", "[\ufffd2]")
    row["source_span"] = {"start_offset": 0, "end_offset": len(row["text"])}
    monkeypatch.setattr(service, "_active_product", lambda *, verify_all: _active_product(tmp_path))
    monkeypatch.setattr(service, "_iter_active_parsed_rows", lambda _active: iter([row]))

    result = service.law_court_opinion_enrichment("law-court-2026-me-1")

    paragraphs = result["opinion"]["paragraph_map"]
    assert [entry["paragraph"] for entry in paragraphs] == ["1", "2"]
    assert all(row["text"][entry["source_span"]["start_offset"]:entry["source_span"]["end_offset"]].strip().startswith("[\ufffd") for entry in paragraphs)


def test_pass38_prefers_direct_opinion_text_over_duplicate_empty_reference(monkeypatch, tmp_path: Path) -> None:
    service = AuthorityProductService(data_root=tmp_path)
    direct = _opinion_row()
    reference = dict(direct)
    reference.update({"text": "", "source_span": {"start_offset": 0, "end_offset": 0}, "authority_kind": "law_court_opinion_reference"})
    monkeypatch.setattr(service, "_active_product", lambda *, verify_all: _active_product(tmp_path))
    monkeypatch.setattr(service, "_iter_active_parsed_rows", lambda _active: iter([reference, direct]))

    opinion = service.law_court_opinion_enrichment("law-court-2026-me-1")
    span = service.get_source_span("law-court-2026-me-1", start_offset=0, end_offset=20)
    out_of_bounds = service.get_source_span("law-court-2026-me-1", start_offset=0, end_offset=10_000)

    assert opinion["status"] == "enrichment_observed"
    assert [row["paragraph"] for row in opinion["opinion"]["paragraph_map"]] == ["1", "2"]
    assert span["status"] == "pass"
    assert span["source_span_preview"] == direct["text"][:20]
    assert out_of_bounds["status"] == "blocked"
    assert out_of_bounds["blockers"] == ["source_span_outside_admitted_text"]


def test_pass38_canonical_route_requires_role_tenant_and_audits(monkeypatch) -> None:
    monkeypatch.setattr(
        authority_routes.AuthorityProductService,
        "law_court_opinion_enrichment",
        lambda _self, source_id: {
            "status": "enrichment_observed",
            "source_id": source_id,
            "opinion": {"citation": "2026 ME 1", "paragraph_map": []},
            "review_required": True,
            "network_used": False,
            "current_law_determined": False,
            "treatment_determined": False,
        },
    )
    client = TestClient(canonical_app)

    assert client.get("/api/authority/opinions/law-court-2026-me-1/enrichment").status_code == 403
    response = client.get("/api/authority/opinions/law-court-2026-me-1/enrichment", headers=HEADERS)

    assert response.status_code == 200
    assert response.headers["X-MFLL-RBAC"] == "enforced"
    assert response.headers["X-MFLL-Audit-Event-Id"]
    assert response.json()["audit_event"]["action"] == "law_court_opinion_enrichment"


def test_pass38_frozen_route_and_production_ui_are_registered(monkeypatch) -> None:
    monkeypatch.setattr(
        frozen_api.AuthorityProductService,
        "law_court_opinion_enrichment",
        lambda _self, source_id: {
            "status": "enrichment_observed",
            "source_id": source_id,
            "opinion": {"citation": "2026 ME 1", "paragraph_map": []},
            "review_required": True,
            "network_used": False,
            "current_law_determined": False,
            "treatment_determined": False,
        },
    )
    response = TestClient(frozen_api.app).get("/api/authority/opinions/law-court-2026-me-1/enrichment")

    assert response.status_code == 200
    assert response.json()["opinion"]["citation"] == "2026 ME 1"
    frozen_source = (ROOT / "src" / "maine_family_law_llm" / "api.py").read_text(encoding="utf-8")
    source_ui = (ROOT / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_bytes()
    mirrored_ui = (ROOT / "maine_family_law_llm" / "ui" / "workbench.js").read_bytes()
    assert '@app.get("/api/authority/opinions/{source_id}/enrichment")' in frozen_source
    assert b"installAuthorityOpinionEnrichment" in source_ui
    assert b"/api/authority/opinions/" in source_ui
    assert b"data-authority-opinion-source" in source_ui
    assert b"not treatment or outcome conclusions" in source_ui
    assert source_ui == mirrored_ui
