from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.contracts import APICompletionPolicy, EndpointInventory, OpenAPICompletionAuditor
from app.api.main import app
from app.web.ui_contracts import UICompletionAuditor


def _registered_routes() -> set[tuple[str, str]]:
    registered = set()
    for route in app.routes:
        methods = getattr(route, "methods", set()) or set()
        path = getattr(route, "path", "")
        for method in methods:
            if method in {"GET", "POST"} and str(path).startswith("/api"):
                registered.add((method, str(path)))
    return registered


def test_pass39_openapi_documents_required_api_surface():
    inventory_report = EndpointInventory().compare_to_registered(_registered_routes())
    openapi_report = OpenAPICompletionAuditor().audit(app.openapi()).as_dict()
    policy = APICompletionPolicy().evidence().as_dict()

    assert inventory_report["status"] == "pass", inventory_report
    assert openapi_report["status"] == "pass", openapi_report
    assert policy["endpoint_count"] == 15
    assert policy["auth_rbac_enforced"] is True
    assert policy["audit_events_required"] is True


def test_pass39_protected_api_routes_require_role_and_tenant_and_emit_audit_headers():
    client = TestClient(app)

    denied = client.post("/api/query", json={"query": "custody"})
    assert denied.status_code == 403
    assert denied.headers["X-MFLL-RBAC"] == "enforced"
    assert denied.headers["X-MFLL-Audit-Event-Id"]

    allowed = client.post(
        "/api/query",
        json={"query": "custody"},
        headers={"X-User-Role": "attorney", "X-Tenant-Id": "tenant-test"},
    )
    body = allowed.json()
    assert allowed.status_code == 200
    assert allowed.headers["X-MFLL-RBAC"] == "enforced"
    assert allowed.headers["X-MFLL-Audit-Event-Id"]
    assert body["review_required"] is True
    assert body["rbac"]["enforced"] is True
    assert body["audit_event"]["audit_status"] == "emitted"
    assert body["source_cards"]
    assert body["drilldown"]["answer_to_claim_to_citation_to_source_text_to_verifier_result"] is True


def test_pass39_public_api_routes_remain_public_but_audited():
    client = TestClient(app)
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.headers["X-MFLL-RBAC"] == "public"
    assert response.headers["X-MFLL-Audit-Event-Id"]
    assert response.json()["status"] == "ok"


def test_pass40_web_views_have_source_review_blocker_and_drilldown_markers():
    report = UICompletionAuditor("app/web/pages").audit().as_dict()

    assert report["status"] == "pass", report
    assert report["required_view_count"] >= 14
    assert report["drilldown_chain_required"] == [
        "answer",
        "claim",
        "citation",
        "source_text",
        "verifier_result",
    ]
