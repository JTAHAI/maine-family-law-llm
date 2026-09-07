"""Fictional HTTP boundary regressions; not installed-app certification."""

import asyncio
import base64
import json

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api import security
from app.api.local_gateway import LocalGatewayProtection
from app.api.production import app, capability_inventory


@pytest.mark.parametrize(
    "path", ["/api/runtime/capabilities", "/api/hardware/profile", "/api/citations/verify"]
)
@pytest.mark.parametrize(
    "headers",
    [
        {"Host": "hostile.example"},
        {"Origin": "https://hostile.example"},
        {"Origin": "http://127.0.0.1:9999"},
        {"Sec-Fetch-Site": "cross-site"},
    ],
)
def test_common_boundary_denies_all_dispatch_lanes(path, headers):
    response = TestClient(app).get(path, headers=headers)
    assert response.status_code == 403
    assert response.headers["X-MFLL-Audit-Event-Id"]
    assert response.headers["Cache-Control"].startswith("no-store")


@pytest.mark.parametrize(
    "path",
    [
        "/api/citations/verify",
        "/api/research",
        "/api/query",
        "/api/runtime/jobs",
        "/api/runtime/jobs/job-fictional",
        "/api/runtime/jobs/recover-expired",
    ],
)
def test_unsafe_contract_routes_are_disabled_even_for_admin(path, monkeypatch):
    monkeypatch.setenv("MFL_ENABLE_EXPERIMENTAL_SLICES", "1")
    client = TestClient(app)
    for suffix in ("", "/"):
        response = client.post(
            path + suffix,
            json={"text": "2099 ME 999"},
            headers={"X-User-Role": "admin", "X-Tenant-Id": "local-desktop"},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "legacy_contract_not_in_release_scope"
    assert path not in app.openapi()["paths"]


def test_production_source_inventory_preserves_useful_routes():
    paths = app.openapi()["paths"]
    assert "/api/chat" in paths
    assert "/api/runtime/capabilities" in paths
    assert capability_inventory()["release_scope"]["store_feature_claim_eligible"] is False


def test_contract_inventory_distinguishes_disabled_routes_from_missing_ones():
    from app.api.contracts import EndpointInventory, EndpointSpec

    inventory = EndpointInventory(
        (
            EndpointSpec("POST", "/api/query", "disabled demo"),
            EndpointSpec("GET", "/health", "health"),
            EndpointSpec("POST", "/required", "required mutation"),
        )
    )
    missing_method = inventory.compare_to_registered({("GET", "/health")}, surface="production")
    assert missing_method["status"] == "fail"
    assert missing_method["missing"] == [{"method": "POST", "path": "/required"}]
    registered = {("GET", "/health"), ("POST", "/required")}
    safe = inventory.compare_to_registered(registered, surface="production")
    assert safe["status"] == "pass"
    assert safe["disabled"][0]["path"] == "/api/query"
    exposed = inventory.compare_to_registered(
        registered | {("POST", "/api/query")}, surface="production"
    )
    assert exposed["status"] == "fail"
    assert exposed["forbidden_registered"] == [{"method": "POST", "path": "/api/query"}]


def test_production_openapi_audit_rejects_reintroduced_authority_demo():
    from copy import deepcopy

    from app.api.contracts import OpenAPICompletionAuditor

    schema = deepcopy(app.openapi())
    auditor = OpenAPICompletionAuditor()
    assert auditor.audit(schema, surface="production").status == "pass"
    schema["paths"]["/api/query"] = {
        "post": {"operationId": "legacyQuery", "responses": {"200": {"description": "demo"}}}
    }
    result = auditor.audit(schema, surface="production")
    assert result.status == "fail"
    assert {"path": "/api/query", "reason": "disabled_route_exposed"} in result.undocumented


def test_bounded_chunked_body_and_duplicate_headers():
    async def check(chunks, headers, expected):
        invoked = False

        async def target(scope, receive, send):
            nonlocal invoked
            invoked = True

        gateway = LocalGatewayProtection(target, max_body_bytes=5)
        sent = []

        async def receive():
            return chunks.pop(0)

        async def send(message):
            sent.append(message)

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/hardware/profile",
            "client": ("127.0.0.1", 1234),
            "headers": headers,
        }
        await gateway(scope, receive, send)
        assert not invoked
        assert sent[0]["status"] == expected

    asyncio.run(
        check(
            [
                {"type": "http.request", "body": b"123", "more_body": True},
                {"type": "http.request", "body": b"456", "more_body": False},
            ],
            [(b"host", b"localhost")],
            413,
        )
    )
    asyncio.run(check([], [(b"host", b"localhost"), (b"host", b"evil")], 400))


def test_body_replayed_once_and_disconnect_preserved():
    async def run():
        incoming = [
            {"type": "http.request", "body": b"{}", "more_body": False},
            {"type": "http.disconnect"},
        ]

        async def receive():
            return incoming.pop(0)

        async def send(message):
            pass

        async def target(scope, receive, send):
            assert (await receive())["body"] == b"{}"
            assert (await receive())["type"] == "http.disconnect"

        await LocalGatewayProtection(target)(
            {
                "type": "http",
                "method": "POST",
                "path": "/ask/stream",
                "headers": [(b"host", b"localhost"), (b"content-length", b"2")],
            },
            receive,
            send,
        )

    asyncio.run(run())


def test_process_secret_is_not_a_public_project_path(monkeypatch):
    monkeypatch.delenv("MFL_SESSION_SIGNING_SECRET", raising=False)
    before = security._session_secret()
    monkeypatch.setenv("MFL_PROJECT_ROOT", "D:/fictional/public/project")
    assert security._session_secret() == before
    assert len(before) == 32


@pytest.mark.parametrize("value", [[], None, "string", {"signature": "é"}])
def test_malformed_capabilities_deny_instead_of_server_error(value):
    token = base64.urlsafe_b64encode(json.dumps(value).encode()).decode()
    with pytest.raises(HTTPException) as exc:
        security.validate_session_capability(
            token,
            expected_user_role="reviewer",
            expected_tenant_id="fictional",
            expected_matter_id="fictional",
            expected_action="review",
        )
    assert exc.value.status_code == 403


def test_restart_and_replay_deny_old_approvals(monkeypatch):
    monkeypatch.delenv("MFL_SESSION_SIGNING_SECRET", raising=False)
    params = dict(
        user_role="reviewer", tenant_id="fictional", matter_id="fictional", action="review"
    )
    capability = security.mint_session_capability(**params)
    expected = {"expected_" + key: value for key, value in params.items()}
    security.validate_session_capability(capability.token, **expected)
    with pytest.raises(HTTPException):
        security.validate_session_capability(capability.token, **expected)
    monkeypatch.setattr(security, "_PROCESS_SESSION_SECRET", b"x" * 32)
    with pytest.raises(HTTPException):
        security.validate_session_capability(capability.token, **expected, consume=False)
