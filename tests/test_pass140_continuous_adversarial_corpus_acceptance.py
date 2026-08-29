from __future__ import annotations

import socket
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app
from app.api.contracts.endpoint_inventory import REQUIRED_API_ENDPOINTS
from legal.security.legal_red_team import DEFAULT_REQUIRED_CATEGORIES, LegalRedTeamRunner


ROOT = Path(__file__).resolve().parents[1]
HEADERS = {"X-User-Role": "reviewer", "X-Tenant-Id": "local-desktop"}


def test_continuous_adversarial_corpus_covers_new_required_attack_classes() -> None:
    report = LegalRedTeamRunner(project_root=ROOT).run().as_dict()
    categories = {row["category"] for row in report["results"]}
    required = {
        "prompt_injection_suite",
        "document_injection_suite",
        "html_injection_suite",
        "archive_abuse_suite",
        "path_traversal_suite",
        "sql_injection_suite",
        "model_tool_instruction_suite",
        "filing_ready_bypass_tests",
    }
    assert required.issubset(set(DEFAULT_REQUIRED_CATEGORIES))
    assert required.issubset(categories)
    assert report["status"] == "pass"
    assert report["no_filing_ready_bypass"] is True
    assert all(row["safe"] for row in report["results"])


def test_adversarial_corpus_route_is_local_scoped_audited_and_never_reads_matter_data(monkeypatch) -> None:
    def network_forbidden(*_args, **_kwargs):
        raise AssertionError("the synthetic adversarial corpus must not open a network connection")

    monkeypatch.setattr(socket, "create_connection", network_forbidden)
    response = TestClient(app).post(
        "/api/security/privacy/adversarial-corpus/run",
        headers=HEADERS,
        json={},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "pass"
    assert payload["local_only"] is True
    assert payload["synthetic_only"] is True
    assert payload["no_matter_content_read"] is True
    assert payload["no_external_request"] is True
    assert payload["review_required"] is True
    assert payload["safe_count"] == payload["result_count"]
    assert payload["unsafe_case_ids"] == []
    assert response.headers.get("X-MFLL-Audit-Event-Id")


def test_adversarial_corpus_is_in_canonical_inventory_and_shipped_privacy_ui() -> None:
    assert ("POST", "/api/security/privacy/adversarial-corpus/run") in {
        (item.method, item.path) for item in REQUIRED_API_ENDPOINTS
    }
    source_html = (ROOT / "src" / "maine_family_law_llm" / "ui" / "workbench.html").read_text(encoding="utf-8")
    shipped_html = (ROOT / "maine_family_law_llm" / "ui" / "workbench.html").read_text(encoding="utf-8")
    source_js = (ROOT / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_text(encoding="utf-8")
    shipped_js = (ROOT / "maine_family_law_llm" / "ui" / "workbench.js").read_text(encoding="utf-8")
    for content in (source_html, shipped_html):
        assert 'id="run-adversarial-corpus"' in content
        assert "Synthetic adversarial safety checks" in content
    for content in (source_js, shipped_js):
        assert "/api/security/privacy/adversarial-corpus/run" in content
        assert "runLocalAdversarialCorpus" in content
