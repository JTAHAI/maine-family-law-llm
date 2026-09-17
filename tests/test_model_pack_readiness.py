"""Canonical signed-import readiness; structural fixtures are NOT model inference."""

# Imported fixtures are deliberately reused, not copied model runtimes.
# ruff: noqa: F811
import json

from test_fast_interchange_model_packs import admitted, bound_host, pack_store  # noqa: F401

from app.api import model_packs
from app.services.local_agent_context_service import LocalAgentAuditStore
from legal.fast_interchange.admission import canonical


def test_canonical_import_readiness_revocation_and_scope(pack_store, bound_host, monkeypatch):
    store, host = pack_store["store"], bound_host
    monkeypatch.setattr(model_packs, "configured_service", lambda root: store)
    client = host["client"]
    headers = {**host["headers"], "X-User-Role": "admin"}
    matter = {"matter_id": host["body"]["matter_id"]}

    def inventory():
        response = client.get("/api/model-packs", params=matter, headers=headers)
        assert response.status_code == 200, response.text
        assert str(store.root) not in response.text
        assert str(host["root"]) not in response.text
        result = response.json()
        assert result["review_required"]
        assert result["readiness"]["runtime_verified"] is False
        assert result["readiness"]["hardware_verified"] is False
        return result

    assert inventory()["readiness"]["status"] == "no_active_pack"
    payload = {**matter, "user_confirmed": True, "total_bytes": pack_store["path"].stat().st_size}
    assert (
        client.post("/api/model-packs/imports", json=payload, headers=host["headers"]).status_code
        == 403
    )
    response = client.post("/api/model-packs/imports", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    route = "/api/model-packs/imports/" + response.json()["job_id"]
    response = client.post(
        route + "/chunks",
        params={**matter, "offset": 0},
        content=pack_store["path"].read_bytes(),
        headers=headers,
    )
    assert response.status_code == 200, response.text
    response = client.post(route + "/inspect", json=matter, headers=headers)
    assert response.status_code == 200, response.text
    prepared = response.json()
    assert prepared["status"] == "ready_to_activate"
    assert all(row["evaluation_basis"] == "synthetic" for row in prepared["summary"]["models"])
    assert inventory()["readiness"]["status"] == "no_active_pack"
    for wrong_headers, wrong_matter in (
        ({**headers, "X-Tenant-Id": "fictional-other"}, matter),
        (headers, {"matter_id": "fictional-other"}),
    ):
        result = client.get(route, params=wrong_matter, headers=wrong_headers)
        assert result.status_code in {403, 404, 409}
        assert prepared["pack_id"] not in result.text
    response = client.post(
        route + "/activate",
        json={**matter, "pack_id": prepared["pack_id"], "user_confirmed": True},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    active = inventory()
    assert active["readiness"]["status"] == "development_only"
    assert len(active["models"]) == 2
    fixture = pack_store["fixture"]
    fixture["trust"]["revoked_key_ids"] = [fixture["envelope"]["key_id"]]
    fixture["trust_path"].write_bytes(canonical(fixture["trust"]))
    blocked = inventory()
    assert blocked["readiness"]["status"] == "admission_blocked"
    assert blocked["models"] == []
    assert (store.root / "packs" / prepared["pack_id"]).exists()
    audit = LocalAgentAuditStore(host["root"], encryption_key="f" * 32)
    raw = audit.path.read_bytes()
    assert b"fictional-tenant" not in raw
    assert host["text"].encode() not in raw
    events = audit.encryptor.decrypt_json(json.loads(raw))["events"]
    assert "model_pack_verified" in [event["action"] for event in events]
    assert not host["worker"].prompts  # Import/activation never imply inference.
