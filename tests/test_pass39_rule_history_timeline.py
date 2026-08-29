from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app as canonical_app
from app.api.routes import authority as authority_routes
from app.services.authority_product_service import ActiveAuthorityProduct, AuthorityProductService
from legal.connectors.maine_rules import parse_rules_text
from maine_family_law_llm import api as frozen_api


ROOT = Path(__file__).resolve().parents[1]
HEADERS = {"X-User-Role": "reviewer", "X-Tenant-Id": "tenant-rule-history"}


def _active_product(tmp_path: Path) -> ActiveAuthorityProduct:
    manifest_path = tmp_path / "authority_product_manifest.json"
    manifest = {
        "schema_version": "1.1",
        "build_id": "a" * 24,
        "build_fingerprint": "b" * 64,
        "source_snapshots": [
            {
                "source_id": "rules-snapshot",
                "relative_path": "authority_product/builds/a/sources/000001.pdf",
                "sha256": "c" * 64,
                "size": 100,
            }
        ],
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return ActiveAuthorityProduct(tmp_path, "a" * 24, manifest_path, manifest)


def _rule_row(*, include_history: bool = True) -> dict:
    text = "M.R. Civ. P. 52\nEffective: June 1, 2026\nAmended: May 1, 2026\n"
    return {
        "record_id": "mrcivp-52",
        "source_id": "rules-snapshot",
        "source_hash": "c" * 64,
        "source_class": "court_rule_pdf",
        "authority_kind": "court_rule_reference",
        "citation": "M.R. Civ. P. 52",
        "title": "Rule 52",
        "rule_set": "Maine Rules of Civil Procedure",
        "rule_number": "52",
        "effective_date": "June 1, 2026" if include_history else None,
        "amendment_history": [{"event": "amended", "date": "May 1, 2026"}] if include_history else [],
        "source_span": {"start_offset": 20, "end_offset": 20 + len(text)},
        "source_url_or_path": "https://www.courts.maine.gov/rules/mr-civ-p-2026.pdf",
        "text": text,
    }


def test_pass39_parser_extracts_explicit_effective_and_amendment_metadata() -> None:
    rules, audit = parse_rules_text(
        "MAINE RULES OF CIVIL PROCEDURE\nEffective: June 1, 2026\nAmended: May 1, 2026\nRule 52 Findings",
        source_id="rules",
        url="https://www.courts.maine.gov/rules/mr-civ-p-2026.pdf",
    )

    assert rules[0].effective_date == "June 1, 2026"
    assert rules[0].amendment_history == [{"event": "amended", "date": "May 1, 2026"}]
    assert audit.metadata["effective_date"] == "June 1, 2026"
    assert audit.metadata["amendment_event_count"] == 1


def test_pass39_timeline_exposes_exact_admitted_date_spans_without_as_of_conclusion(monkeypatch, tmp_path: Path) -> None:
    service = AuthorityProductService(data_root=tmp_path)
    monkeypatch.setattr(service, "_active_product", lambda *, verify_all: _active_product(tmp_path))
    monkeypatch.setattr(service, "_iter_active_parsed_rows", lambda _active: iter([_rule_row()]))

    result = service.rule_history_timeline("M.R. Civ. P. 52")

    assert result["status"] == "timeline_observed"
    assert result["review_required"] is True
    assert result["network_used"] is False
    assert result["as_of_determined"] is False
    row = result["timeline"][0]
    assert [event["event"] for event in row["events"]] == ["effective", "amended"]
    assert all(event["source_span"]["start_offset"] >= 20 for event in row["events"])
    assert row["official_url"].startswith("https://www.courts.maine.gov/")


def test_pass39_missing_explicit_history_fails_closed(monkeypatch, tmp_path: Path) -> None:
    service = AuthorityProductService(data_root=tmp_path)
    monkeypatch.setattr(service, "_active_product", lambda *, verify_all: _active_product(tmp_path))
    monkeypatch.setattr(service, "_iter_active_parsed_rows", lambda _active: iter([_rule_row(include_history=False)]))

    result = service.rule_history_timeline("52")

    assert result["status"] == "needs_review"
    assert "rule_effective_or_amendment_history_unavailable:mrcivp-52" in result["blockers"]


def test_pass39_canonical_route_requires_role_tenant_and_audits(monkeypatch) -> None:
    monkeypatch.setattr(
        authority_routes.AuthorityProductService,
        "rule_history_timeline",
        lambda _self, query: {
            "status": "timeline_observed",
            "query": query,
            "timeline": [],
            "review_required": True,
            "network_used": False,
            "as_of_determined": False,
        },
    )
    client = TestClient(canonical_app)

    assert client.get("/api/authority/rules/history?query=M.R.%20Civ.%20P.%2052").status_code == 403
    response = client.get("/api/authority/rules/history?query=M.R.%20Civ.%20P.%2052", headers=HEADERS)

    assert response.status_code == 200
    assert response.headers["X-MFLL-RBAC"] == "enforced"
    assert response.headers["X-MFLL-Audit-Event-Id"]
    assert response.json()["audit_event"]["action"] == "rule_history_timeline_inspection"


def test_pass39_frozen_route_and_production_ui_are_registered(monkeypatch) -> None:
    monkeypatch.setattr(
        frozen_api.AuthorityProductService,
        "rule_history_timeline",
        lambda _self, query: {
            "status": "timeline_observed",
            "query": query,
            "timeline": [],
            "review_required": True,
            "network_used": False,
            "as_of_determined": False,
        },
    )
    response = TestClient(frozen_api.app).get("/api/authority/rules/history?query=M.R.%20Civ.%20P.%2052")

    assert response.status_code == 200
    assert response.json()["query"] == "M.R. Civ. P. 52"
    frozen_source = (ROOT / "src" / "maine_family_law_llm" / "api.py").read_text(encoding="utf-8")
    source_ui = (ROOT / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_bytes()
    mirrored_ui = (ROOT / "maine_family_law_llm" / "ui" / "workbench.js").read_bytes()
    assert '@app.get("/api/authority/rules/history")' in frozen_source
    assert b"installAuthorityRuleHistoryTimeline" in source_ui
    assert b"/api/authority/rules/history" in source_ui
    assert b"data-authority-rule-history-source" in source_ui
    assert b"does not determine which version applies" in source_ui
    assert source_ui == mirrored_ui
