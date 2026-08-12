from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.production import app, capability_inventory


def test_production_inventory_is_route_derived_and_truthful() -> None:
    inventory = capability_inventory()
    assert inventory["production_entrypoint"] == "app.api.production:app"
    assert inventory["production_route_count"] > inventory["local_route_count"]
    assert inventory["enterprise_only_route_count"] > 100
    assert inventory["ui"]["shadow_tsx_is_production"] is False


def test_gateway_preserves_local_ui_and_chat_routes() -> None:
    client = TestClient(app)
    home = client.get("/")
    assert home.status_code == 200
    assert "Maine" in home.text

    capabilities = client.get("/api/runtime/capabilities")
    assert capabilities.status_code == 200
    assert capabilities.json()["production_route_count"] > 300


def test_gateway_exposes_enterprise_only_routes_with_enterprise_security() -> None:
    client = TestClient(app)
    denied = client.get("/api/hardware/profile")
    assert denied.status_code == 403

    admitted = client.get(
        "/api/hardware/profile",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "local-desktop"},
    )
    assert admitted.status_code == 200
    assert "X-MFLL-Audit-Event-Id" in admitted.headers


def test_merged_openapi_contains_local_and_enterprise_paths() -> None:
    paths = app.openapi()["paths"]
    assert "/api/chat" in paths
    assert "/api/hardware/profile" in paths
    assert "/api/evals/queue/build" in paths
