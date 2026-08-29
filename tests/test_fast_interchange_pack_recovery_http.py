"""Positive canonical HTTP recovery journeys with synthetic signed artifacts."""

# Imported pytest fixtures are intentionally named by test parameters.
# ruff: noqa: F811

import pytest
from test_fast_interchange_model_packs import admitted, bound_host, pack_store  # noqa: F401

from app.api import model_packs
from app.services import model_pack_service as module
from legal.fast_interchange.admission import canonical


@pytest.mark.parametrize("action", ["finish", "deactivate", "abandon"])
def test_interrupted_transaction_recovers_through_canonical_http(
    pack_store,
    bound_host,
    monkeypatch,
    action,  # noqa: F811
):
    pack, host = pack_store, bound_host
    store, client = pack["store"], host["client"]
    monkeypatch.setattr(model_packs, "configured_service", lambda root: store)
    headers = {**host["headers"], "X-User-Role": "admin"}
    body = {"matter_id": host["body"]["matter_id"], "user_confirmed": True}
    row = client.post(
        "/api/model-packs/imports",
        json={**body, "total_bytes": pack["path"].stat().st_size},
        headers=headers,
    ).json()
    route = "/api/model-packs/imports/" + row["job_id"]
    result = client.post(
        route + "/chunks",
        params={"matter_id": body["matter_id"], "offset": 0},
        content=pack["path"].read_bytes(),
        headers=headers,
    )
    assert result.status_code == 200, result.text
    row = client.post(
        route + "/inspect", json={"matter_id": body["matter_id"]}, headers=headers
    ).json()
    pack_id = row["pack_id"]
    with monkeypatch.context() as patch:
        if action == "abandon":
            client.post(route + "/cancel", json={"matter_id": body["matter_id"]}, headers=headers)
            original = store._save

            def fail(state):
                if not state["transaction"]:
                    raise OSError("synthetic storage-commit failure")
                original(state)

            patch.setattr(store, "_save", fail)
            result = client.post(
                f"/api/model-packs/installed/{pack_id}/remove", json=body, headers=headers
            )
        else:
            original = module.atomic_write_bytes

            def fail(path, *args, **kwargs):
                if path.name == "active.json":
                    raise OSError("synthetic pointer failure")
                return original(path, *args, **kwargs)

            patch.setattr(module, "atomic_write_bytes", fail)
            result = client.post(
                route + "/activate", json={**body, "pack_id": pack_id}, headers=headers
            )
        assert result.status_code == 409
        assert str(store.root) not in result.text
    inventory = client.get(
        "/api/model-packs", params={"matter_id": body["matter_id"]}, headers=headers
    ).json()
    assert inventory["status"] == "blocked"
    transaction = inventory["transaction"]
    if action == "deactivate":
        fixture = pack["fixture"]
        fixture["trust"]["revoked_key_ids"] = [fixture["envelope"]["key_id"]]
        fixture["trust_path"].write_bytes(canonical(fixture["trust"]))
    recovery = {**body, "transaction_id": transaction["id"], "action": action}
    assert (
        client.post("/api/model-packs/recovery", json=recovery, headers=host["headers"]).status_code
        == 403
    )
    result = client.post("/api/model-packs/recovery", json=recovery, headers=headers)
    assert result.status_code == 200, result.text
    assert result.json()["review_required"] and result.json()["original_preserved"]
    inventory = client.get(
        "/api/model-packs", params={"matter_id": body["matter_id"]}, headers=headers
    ).json()
    assert inventory["transaction"] is None
    assert inventory["active_pack_id"] == (pack_id if action == "finish" else "")
    assert (store.root / "packs" / pack_id).exists()
    assert (host["root"] / "40_RUNTIME/local-agent/audit.json.enc").is_file()
