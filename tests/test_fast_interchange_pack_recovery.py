"""Fault/restart coverage. All packs/signatures are fictional, not legal models."""

# Imported pytest fixtures are intentionally named by test parameters.
# ruff: noqa: F811

import hashlib
import json

import pytest
from test_fast_interchange_model_packs import (  # noqa: F401
    admitted,
    bound_host,
    pack_store,
    structural_pack,
    upload,
)

from app.api import model_packs
from app.services import model_pack_service as module
from app.services.model_pack_service import (
    CHUNK_BYTES,
    ModelPackError,
    ModelPackService,
    chunk_chain,
    load_active_pack,
    verification_lease,
)
from legal.fast_interchange.admission import canonical


def prepared(pack, path=None):
    row = upload(pack, path)
    return pack["store"].inspect(row["job_id"], scope=pack["scope"], audit=pack["audit"])


def activate(pack, row):
    return pack["store"].activate(
        row["job_id"], scope=pack["scope"], audit=pack["audit"], pack_id=row["pack_id"]
    )


def restart(pack):
    return ModelPackService(pack["store"].root, pack["fixture"]["authority"])


def resume(pack, row, *, store=None, scope=None, **changes):
    return (store or pack["store"]).resume(
        row["job_id"],
        scope=scope or pack["scope"],
        audit=pack["audit"],
        **{"expected_bytes": row["received_bytes"], "prefix_chain": row["prefix_chain"], **changes},
    )


def test_restart_resume_requires_exact_prefix_and_explicit_session_rebind(pack_store):
    pack = pack_store
    row = upload(pack)
    other = {**pack["scope"], "client_session_id": "c" * 48}
    store = restart(pack)
    with pytest.raises(ModelPackError, match="job_unavailable"):
        store.status(row["job_id"], scope=other)
    inventory = store.inventory(scope=other)
    assert not inventory["jobs"] and inventory["recoverable_jobs"][0]["job_id"] == row["job_id"]
    result = resume(pack, row, store=store, scope=other)
    assert result["status"] == "uploading" and result["review_required"]
    with pytest.raises(ModelPackError, match="job_unavailable"):
        pack["store"].status(row["job_id"], scope=pack["scope"])
    verified = store.inspect(row["job_id"], scope=other, audit=pack["audit"])
    assert verified["status"] == "ready_to_activate"
    assert not (store.root / "active.json").exists()


@pytest.mark.parametrize("field", ["tenant_id", "matter_id", "role"])
def test_recovery_never_bypasses_matter_tenant_or_role(pack_store, field):
    row = upload(pack_store)
    scope = {**pack_store["scope"], field: "other"}
    assert not pack_store["store"].inventory(scope=scope)["recoverable_jobs"]
    with pytest.raises(ModelPackError):
        resume(pack_store, row, scope=scope)


@pytest.mark.parametrize("fault", ["offset", "chain", "disk", "truncated"])
def test_resume_rejects_changed_original_or_staging(pack_store, fault):
    row = upload(pack_store)
    original = pack_store["path"].read_bytes()
    path = pack_store["store"].root / "uploads" / row["job_id"] / "incoming.zip"
    changes = {}
    if fault == "offset":
        changes["expected_bytes"] = row["received_bytes"] - 1
    elif fault == "chain":
        changes["prefix_chain"] = "0" * 64
    else:
        path.write_bytes(original[:-1] + (b"!" if fault == "disk" else b""))
    with pytest.raises(ModelPackError, match="resume_"):
        resume(pack_store, row, **changes)
    assert pack_store["path"].read_bytes() == original
    assert not (pack_store["store"].root / "active.json").exists()


def test_committed_chunk_retry_and_torn_tail_recovery(pack_store):
    pack, block = pack_store, b"fictional" * (CHUNK_BYTES // 9) + b"x" * (CHUNK_BYTES % 9)
    store, scope = pack["store"], pack["scope"]
    row = store.begin(scope=scope, total_bytes=CHUNK_BYTES + 4, audit=pack["audit"])
    row = store.chunk(row["job_id"], scope=scope, offset=0, data=block)
    assert row == store.chunk(row["job_id"], scope=scope, offset=0, data=block)
    path = store.root / "uploads" / row["job_id"] / "incoming.zip"
    with path.open("ab") as handle:
        handle.write(b"torn")
    resume(pack, row, store=restart(pack))
    assert path.read_bytes() == block
    result = store.chunk(row["job_id"], scope=scope, offset=CHUNK_BYTES, data=b"last")
    assert result["prefix_chain"] == chunk_chain(row["prefix_chain"], CHUNK_BYTES, b"last")
    assert path.stat().st_size == CHUNK_BYTES + 4


def test_live_verification_lease_blocks_takeover_and_discard(pack_store):
    pack = pack_store
    row = upload(pack)
    state = pack["store"]._load()
    state["jobs"][row["job_id"]]["status"] = "verifying"
    pack["store"]._save(state)
    store = restart(pack)
    with verification_lease(store.root):
        assert store.status(row["job_id"], scope=pack["scope"])["status"] == "verifying"
        with pytest.raises(ModelPackError, match="verification_busy"):
            resume(pack, row, store=store)
        with pytest.raises(ModelPackError, match="busy"):
            store.discard(row["job_id"], scope=pack["scope"], audit=pack["audit"])
    assert store.status(row["job_id"], scope=pack["scope"])["status"] == "interrupted"
    assert resume(pack, row, store=store)["status"] == "uploading"


@pytest.mark.parametrize("phase", ["trust", "pointer", "completion_audit", "state_commit"])
def test_activation_crash_is_fail_closed_and_replays_forward(pack_store, monkeypatch, phase):
    pack = pack_store
    row = prepared(pack)
    store = pack["store"]
    with monkeypatch.context() as patch:
        if phase == "trust":
            original = store.authority.verify

            def failed_trust(*args, **kwargs):
                original(*args, **kwargs)
                raise OSError("fictional interruption after trust write")

            patch.setattr(store.authority, "verify", failed_trust)
        elif phase == "pointer":
            original = module.atomic_write_bytes

            def failed_pointer(path, *args, **kwargs):
                result = original(path, *args, **kwargs)
                if path.name == "active.json":
                    raise OSError("fictional interruption after pointer write")
                return result

            patch.setattr(module, "atomic_write_bytes", failed_pointer)
        elif phase == "state_commit":
            original = store._save

            def failed_state(state):
                if not state["transaction"]:
                    raise OSError("fictional interruption before state commit")
                original(state)

            patch.setattr(store, "_save", failed_state)
        else:
            original = pack["audit"]

            def failed_audit(action, identity):
                if action == "model_pack_activation_completed":
                    raise OSError("fictional completion audit failure")
                original(action, identity)

            patch.setitem(pack, "audit", failed_audit)
        with pytest.raises(OSError):
            activate(pack, row)
    reopened = restart(pack)
    inventory = reopened.inventory(scope=pack["scope"])
    assert inventory["status"] == "blocked"
    transaction = inventory["transaction"]
    assert transaction["pack_id"] == row["pack_id"]
    with pytest.raises(ModelPackError, match="transaction_recovery_required"):
        load_active_pack(reopened.root, pack["fixture"]["authority"])
    with pytest.raises(ModelPackError, match="transaction_recovery_required"):
        reopened.begin(scope=pack["scope"], total_bytes=10, audit=pack["audit"])
    highwater = pack["fixture"]["authority"].state_path.read_bytes()
    result = reopened.recover(
        scope={**pack["scope"], "client_session_id": "c" * 48},
        audit=pack["audit"],
        transaction_id=transaction["id"],
    )
    assert result["status"] == "activate_completed" and result["review_required"]
    assert highwater == pack["fixture"]["authority"].state_path.read_bytes()
    assert load_active_pack(reopened.root, pack["fixture"]["authority"])
    assert not reopened.inventory(scope=pack["scope"])["transaction"]
    with pytest.raises(ModelPackError, match="transaction_unavailable"):
        reopened.recover(scope=pack["scope"], audit=pack["audit"], transaction_id=transaction["id"])


def pending_activation(pack, monkeypatch):
    row = prepared(pack)
    with monkeypatch.context() as patch:
        original = module.atomic_write_bytes

        def fail(path, *args, **kwargs):
            if path.name == "active.json":
                raise OSError("fictional pointer failure")
            return original(path, *args, **kwargs)

        patch.setattr(module, "atomic_write_bytes", fail)
        with pytest.raises(OSError):
            activate(pack, row)
    return pack["store"].inventory(scope=pack["scope"])["transaction"]


def test_revoked_pending_activation_can_only_fail_closed_or_deactivate(pack_store, monkeypatch):
    pack = pack_store
    transaction = pending_activation(pack, monkeypatch)
    fixture = pack["fixture"]
    highwater = fixture["authority"].state_path.read_bytes()
    fixture["trust"]["revoked_key_ids"] = [fixture["envelope"]["key_id"]]
    fixture["trust_path"].write_bytes(canonical(fixture["trust"]))
    with pytest.raises(Exception, match="admission_invalid"):
        pack["store"].recover(
            scope=pack["scope"], audit=pack["audit"], transaction_id=transaction["id"]
        )
    for scope in ({**pack["scope"], "tenant_id": "other"}, {**pack["scope"], "matter_id": "other"}):
        with pytest.raises(ModelPackError, match="transaction_unavailable"):
            pack["store"].recover(
                scope=scope, audit=pack["audit"], transaction_id=transaction["id"], deactivate=True
            )
    result = pack["store"].recover(
        scope=pack["scope"], audit=pack["audit"], transaction_id=transaction["id"], deactivate=True
    )
    assert result["status"] == "deactivated"
    assert fixture["authority"].state_path.read_bytes() == highwater
    with pytest.raises(ModelPackError, match="no_active_pack"):
        load_active_pack(pack["store"].root, fixture["authority"])
    assert pack["store"].begin(scope=pack["scope"], total_bytes=10, audit=pack["audit"])


def test_previous_activation_cannot_downgrade_and_active_dependencies_cannot_move(
    pack_store, tmp_path
):
    pack = pack_store
    first = prepared(pack)
    activate(pack, first)
    path, _ = structural_pack(pack["fixture"], tmp_path / "fictional-next.zip", sequence=2)
    second = prepared(pack, path)
    activate(pack, second)
    highwater = pack["fixture"]["authority"].state_path.read_bytes()
    with pytest.raises(Exception, match="admission_invalid") as failure:
        pack["store"].reactivate_previous(
            scope=pack["scope"],
            audit=pack["audit"],
            pack_id=first["pack_id"],
            expected_active=second["pack_id"],
        )
    assert "catalog_rollback" in str(failure.value.__cause__)
    for row in (first, second):
        with pytest.raises(ModelPackError, match="still_referenced"):
            pack["store"].remove(scope=pack["scope"], audit=pack["audit"], pack_id=row["pack_id"])
    assert highwater == pack["fixture"]["authority"].state_path.read_bytes()
    assert pack["store"].inventory(scope=pack["scope"])["active_pack_id"] == second["pack_id"]


@pytest.mark.parametrize("crash", [False, True])
def test_recoverable_remove_restore_and_explicit_reactivation(pack_store, monkeypatch, crash):
    pack = pack_store
    row = prepared(pack)
    store, scope, audit, pack_id = pack["store"], pack["scope"], pack["audit"], row["pack_id"]
    with pytest.raises(ModelPackError, match="still_referenced"):
        store.remove(scope=scope, audit=audit, pack_id=pack_id)
    store.cancel(row["job_id"], scope=scope, audit=audit)
    original_sha = hashlib.sha256(pack["path"].read_bytes()).hexdigest()
    with monkeypatch.context() as patch:
        if crash:
            original = store._save

            def fail(state):
                if not state["transaction"]:
                    raise OSError("fictional move commit interruption")
                original(state)

            patch.setattr(store, "_save", fail)
            with pytest.raises(OSError):
                store.remove(scope=scope, audit=audit, pack_id=pack_id)
        else:
            result = store.remove(scope=scope, audit=audit, pack_id=pack_id)
            assert not result["disk_space_reclaimed"]
    store = restart(pack)
    if crash:
        transaction = store.inventory(scope=scope)["transaction"]
        store.recover(scope=scope, audit=audit, transaction_id=transaction["id"])
    inventory = store.inventory(scope=scope)
    assert inventory["removed"][0]["pack_id"] == pack_id and not inventory["installed"]
    assert not (store.root / "packs" / pack_id).exists()
    result = store.restore(scope=scope, audit=audit, pack_id=pack_id)
    assert result["status"] == "restore_completed" and not result["requires_worker_restart"]
    assert not store.inventory(scope=scope)["active_pack_id"]
    store.activate_installed(scope=scope, audit=audit, pack_id=pack_id, expected_active="")
    assert load_active_pack(store.root, pack["fixture"]["authority"])
    assert hashlib.sha256(pack["path"].read_bytes()).hexdigest() == original_sha
    assert str(store.root) not in json.dumps(inventory)


def test_installed_pack_activation_requires_fresh_consent_and_scope(pack_store):
    pack = pack_store
    row = prepared(pack)
    for action in ("remove", "restore", "activate_installed"):
        kwargs = {"expected_active": ""} if action == "activate_installed" else {}
        with pytest.raises(ModelPackError, match="unavailable"):
            getattr(pack["store"], action)(
                scope={**pack["scope"], "matter_id": "other"},
                audit=pack["audit"],
                pack_id=row["pack_id"],
                **kwargs,
            )
    with pytest.raises(ModelPackError, match="consent_changed"):
        pack["store"].activate_installed(
            scope=pack["scope"],
            audit=pack["audit"],
            pack_id=row["pack_id"],
            expected_active="f" * 64,
        )


def test_lifecycle_routes_enforce_consent_scope_and_review_status(
    pack_store, bound_host, monkeypatch
):
    pack, host = pack_store, bound_host
    monkeypatch.setattr(model_packs, "configured_service", lambda root: pack["store"])
    client, matter = host["client"], host["body"]["matter_id"]
    headers = {**host["headers"], "X-User-Role": "admin"}
    body = {"matter_id": matter, "user_confirmed": True}
    row = client.post(
        "/api/model-packs/imports",
        json={**body, "total_bytes": pack["path"].stat().st_size},
        headers=headers,
    ).json()
    route = "/api/model-packs/imports/" + row["job_id"]
    row = client.post(
        route + "/chunks",
        params={"matter_id": matter, "offset": 0},
        content=pack["path"].read_bytes(),
        headers=headers,
    ).json()
    resume_body = {
        **body,
        "expected_bytes": row["received_bytes"],
        "prefix_chain": row["prefix_chain"],
    }
    routes = {
        route + "/resume": resume_body,
        "/api/model-packs/recovery": {**body, "transaction_id": "c" * 32, "action": "finish"},
        "/api/model-packs/installed/" + "a" * 64 + "/activate": {**body, "expected_active": ""},
        "/api/model-packs/installed/" + "a" * 64 + "/remove": body,
        "/api/model-packs/removed/" + "a" * 64 + "/restore": body,
    }
    for url, payload in routes.items():
        assert client.post(url, json=payload, headers=host["headers"]).status_code == 403
        assert (
            client.post(url, json={**payload, "user_confirmed": False}, headers=headers).status_code
            == 422
        )
        assert (
            client.post(url, json={**payload, "matter_id": "wrong"}, headers=headers).status_code
            == 409
        )
        assert (
            client.post(url, json={**payload, "unexpected": True}, headers=headers).status_code
            == 422
        )
    assert client.post(route + "/resume", json=resume_body, headers=headers).json()[
        "review_required"
    ]
    result = client.post(route + "/inspect", json={"matter_id": matter}, headers=headers).json()
    assert result["status"] == "ready_to_activate"
    client.post(route + "/cancel", json={"matter_id": matter}, headers=headers)
    pack_id = result["pack_id"]
    for url in (
        f"/api/model-packs/installed/{pack_id}/remove",
        f"/api/model-packs/removed/{pack_id}/restore",
    ):
        result = client.post(url, json=body, headers=headers)
        assert result.status_code == 200, result.text
        assert result.json()["review_required"] and result.json()["original_preserved"]
    result = client.post(
        f"/api/model-packs/installed/{pack_id}/activate",
        json={**body, "expected_active": ""},
        headers=headers,
    )
    assert result.status_code == 200, result.text
    assert result.json()["review_required"] and result.json()["requires_worker_restart"]
    assert (host["root"] / "40_RUNTIME/local-agent/audit.json.enc").is_file()


@pytest.mark.parametrize("was_activated", [False, True])
def test_completed_import_can_be_reverified_after_browser_restart(pack_store, was_activated):
    pack = pack_store
    row = prepared(pack)
    if was_activated:
        activate(pack, row)
    other = {**pack["scope"], "client_session_id": "c" * 48}
    store = restart(pack)
    recovered = store.inventory(scope=other)["recoverable_jobs"]
    assert recovered[0]["job_id"] == row["job_id"]
    resume(pack, recovered[0], store=store, scope=other)
    assert (
        store.inspect(row["job_id"], scope=other, audit=pack["audit"])["status"]
        == "ready_to_activate"
    )
    assert store.inventory(scope=other)["active_pack_id"] == (
        row["pack_id"] if was_activated else ""
    )


@pytest.mark.parametrize("kind", ["remove", "restore"])
def test_interrupted_storage_move_can_return_to_original_state(pack_store, monkeypatch, kind):
    pack = pack_store
    row = prepared(pack)
    store, scope, audit = pack["store"], pack["scope"], pack["audit"]
    store.cancel(row["job_id"], scope=scope, audit=audit)
    if kind == "restore":
        store.remove(scope=scope, audit=audit, pack_id=row["pack_id"])
    before = store._load()
    with monkeypatch.context() as patch:
        original = store._save

        def fail(state):
            if not state["transaction"]:
                raise OSError("fictional final storage-state write failure")
            original(state)

        patch.setattr(store, "_save", fail)
        with pytest.raises(OSError):
            getattr(store, kind)(scope=scope, audit=audit, pack_id=row["pack_id"])
    # Revocation cannot trap a failed storage-only change forever; reversal
    # loads no model and leaves every admission safeguard intact.
    fixture = pack["fixture"]
    fixture["trust"]["revoked_key_ids"] = [fixture["envelope"]["key_id"]]
    fixture["trust_path"].write_bytes(canonical(fixture["trust"]))
    reopened = restart(pack)
    transaction = reopened.inventory(scope=scope)["transaction"]
    result = reopened.recover(
        scope=scope, audit=audit, transaction_id=transaction["id"], abandon=True
    )
    assert result["status"] == "storage_change_abandoned"
    after = reopened._load()
    assert after["installed"] == before["installed"] and after["removed"] == before["removed"]
    assert (store.root / "packs" / row["pack_id"]).exists() == (kind == "remove")
    assert not after["transaction"]


def test_cancel_verification_from_another_service_instance(pack_store, monkeypatch):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    pack = pack_store
    row = upload(pack)
    entered, resume_work = threading.Event(), threading.Event()
    original = module._bounded_zip

    def pause(path):
        entered.set()
        assert resume_work.wait(10)
        return original(path)

    monkeypatch.setattr(module, "_bounded_zip", pause)
    with ThreadPoolExecutor(1) as pool:
        pending = pool.submit(
            pack["store"].inspect, row["job_id"], scope=pack["scope"], audit=pack["audit"]
        )
        assert entered.wait(10)
        canceled = restart(pack).cancel(row["job_id"], scope=pack["scope"], audit=pack["audit"])
        assert canceled["status"] == "canceling"
        resume_work.set()
        with pytest.raises(ModelPackError, match="canceled"):
            pending.result(20)
    assert pack["store"].status(row["job_id"], scope=pack["scope"])["status"] == "canceled"
