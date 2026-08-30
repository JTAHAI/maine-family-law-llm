"""Offline import tests with ephemeral signatures and nonlegal structural tensors."""

import hashlib
import json
import socket
import stat
import struct
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import pytest
from test_fast_interchange_artifact_registry import admitted  # noqa: F401
from test_fast_interchange_host_source_binding import bound_host  # noqa: F401

from app.api import model_packs
from app.services.model_pack_service import (
    CHUNK_BYTES,
    ModelPackError,
    ModelPackService,
    _bounded_zip,
    load_active_pack,
)
from legal.fast_interchange.admission import canonical, digest


def structural_pack(fixture, path, *, sequence=1, mutate=None):
    original = fixture["registry"]
    releases, artifacts = deepcopy(original.release_document), deepcopy(original.artifact_document)
    tensor = canonical({"fictional": {"dtype": "F32", "shape": [1], "data_offsets": [0, 4]}})
    tensor = struct.pack("<Q", len(tensor)) + tensor + bytes(4)
    files = {
        "base/model.safetensors": tensor,
        "base/config.json": canonical(
            {
                "model_type": "qwen2",
                "hidden_size": 8,
                "intermediate_size": 16,
                "num_hidden_layers": 1,
                "vocab_size": 4,
                "num_attention_heads": 2,
            }
        ),
        "base/tokenizer.json": canonical(
            {"model": {"type": "WordLevel", "vocab": {"fictional": 0}}}
        ),
    }

    def descriptor(name):
        return {
            "path": name,
            "sha256": hashlib.sha256(files[name]).hexdigest(),
            "bytes": len(files[name]),
        }

    for binding, release in zip(artifacts["bindings"], releases["releases"], strict=True):
        directory = binding["adapter_dir"]
        files[f"{directory}/adapter_model.safetensors"] = tensor
        files[f"{directory}/adapter_config.json"] = canonical(
            {"peft_type": "LORA", "task_type": "CAUSAL_LM", "r": 2}
        )
        for name, paths in {
            "base_inventory": ["base/config.json", "base/model.safetensors"],
            "tokenizer_inventory": ["base/tokenizer.json"],
            "adapter_inventory": [f"{directory}/adapter_model.safetensors"],
        }.items():
            binding[name] = {"files": [descriptor(name) for name in sorted(paths)]}
            release[name + "_sha256"] = digest(binding[name])
        binding["adapter_config"] = descriptor(f"{directory}/adapter_config.json")
        release["adapter_config_sha256"] = binding["adapter_config"]["sha256"]
    payload = deepcopy(fixture["payload"])
    payload.update(
        sequence=sequence,
        release_registry_sha256=digest(releases),
        artifact_registry_sha256=digest(artifacts),
    )
    docs = {
        "releases.json": releases,
        "artifacts.json": artifacts,
        "admission.json": fixture["sign"](payload),
    }
    entries = {**files, **{name: canonical(value) for name, value in docs.items()}}
    if mutate:
        mutate(entries)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, raw in entries.items():
            archive.writestr(name, raw)
    return path, docs


@pytest.fixture
def pack_store(admitted, tmp_path):  # noqa: F811
    scope = {
        "matter_id": "fictional-matter",
        "tenant_id": "fictional-tenant",
        "role": "admin",
        "client_session_id": "b" * 48,
    }
    events = []
    store = ModelPackService(tmp_path / "external-packs", admitted["authority"])
    path, docs = structural_pack(admitted, tmp_path / "fictional.model-pack.zip")
    return {
        "store": store,
        "scope": scope,
        "audit": lambda action, identity: events.append((action, identity)),
        "events": events,
        "path": path,
        "docs": docs,
        "fixture": admitted,
    }


def upload(pack, path=None):
    path = path or pack["path"]
    store, scope, audit = (pack[key] for key in ("store", "scope", "audit"))
    total_bytes = path.stat().st_size
    row = store.begin(scope=scope, total_bytes=total_bytes, audit=audit)
    offset = 0
    with path.open("rb") as handle:
        # These structural packs are tiny. Do not allocate a full transfer block
        # for a short file or perform another allocation merely to detect EOF.
        while offset < total_bytes:
            block = handle.read(min(CHUNK_BYTES, total_bytes - offset))
            if not block:
                raise AssertionError("Fictional model pack was truncated during upload")
            row = store.chunk(row["job_id"], scope=scope, offset=offset, data=block)
            offset += len(block)
    return row


def test_complete_offline_import_separate_activation_and_restart(pack_store, monkeypatch):
    pack = pack_store
    attempts = []

    def refuse(*args, **kwargs):
        attempts.append(True)
        raise AssertionError("offline import attempted network")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    row = upload(pack)
    store, scope, audit = (pack[key] for key in ("store", "scope", "audit"))
    prepared = store.inspect(row["job_id"], scope=scope, audit=audit)
    assert prepared["status"] == "ready_to_activate"
    assert prepared["summary"]["shared_base_copies"] == 1
    assert len(prepared["summary"]["models"]) == 2
    assert not (store.root / "active.json").exists()
    result = store.activate(row["job_id"], scope=scope, audit=audit, pack_id=prepared["pack_id"])
    assert result["status"] == "activated" and result["review_required"]
    reopened = ModelPackService(store.root, pack["fixture"]["authority"])
    inventory = reopened.inventory(scope=scope)
    assert len(inventory["models"]) == 2
    registry = load_active_pack(store.root, pack["fixture"]["authority"])
    for release in registry.releases.values():
        assert registry.select(release.model_id, allow_test_only=False) == release
        registry.bindings[release.release_id].verify(registry.root)
    assert not attempts
    raw = (store.root / "pack-state.json.enc").read_bytes()
    assert b"fictional-matter" not in raw and b"fictional-tenant" not in raw
    assert [event[0] for event in pack["events"]] == [
        "model_pack_import_started",
        "model_pack_verification_started",
        "model_pack_verified",
        "model_pack_activation_authorized",
        "model_pack_activation_completed",
    ]
    assert str(store.root) not in json.dumps(result)
    store.discard(row["job_id"], scope=scope, audit=audit)
    assert registry.root.exists() and pack["path"].exists()


@pytest.mark.parametrize("field", ["matter_id", "tenant_id", "role", "client_session_id"])
def test_import_jobs_cannot_cross_scope(pack_store, field):
    pack = pack_store
    row = upload(pack)
    scope = {**pack["scope"], field: "different"}
    with pytest.raises(ModelPackError, match="job_unavailable"):
        pack["store"].status(row["job_id"], scope=scope)
    with pytest.raises(ModelPackError, match="job_unavailable"):
        pack["store"].cancel(row["job_id"], scope=scope, audit=pack["audit"])


@pytest.mark.parametrize(
    "fault",
    [
        "signature",
        "extra",
        "missing",
        "hash",
        "metadata_duplicate",
        "traversal",
        "executable",
        "case_collision",
        "compressed",
        "symlink",
    ],
)
def test_malicious_pack_fails_without_activation(pack_store, tmp_path, fault):
    pack = pack_store

    def mutate(entries):
        if fault == "signature":
            doc = json.loads(entries["admission.json"])
            doc["payload"]["sequence"] += 1
            entries["admission.json"] = canonical(doc)
        elif fault == "extra":
            entries["unlisted.json"] = b"{}"
        elif fault == "missing":
            entries.pop("base/tokenizer.json")
        elif fault == "hash":
            raw = entries["base/model.safetensors"]
            entries["base/model.safetensors"] = raw[:-1] + b"x"
        elif fault == "metadata_duplicate":
            entries["admission.json"] = b'{"payload":{},"payload":{}}'
        elif fault == "traversal":
            entries["../outside.json"] = b"{}"
        elif fault == "executable":
            entries["base/execute.py"] = b"raise RuntimeError('never execute')"
        elif fault == "case_collision":
            entries["BASE/tokenizer.json"] = entries["base/tokenizer.json"]

    path, _ = structural_pack(pack["fixture"], tmp_path / "bad.zip", mutate=mutate)
    if fault in {"compressed", "symlink"}:
        with zipfile.ZipFile(path, "a", compression=zipfile.ZIP_DEFLATED) as archive:
            info = zipfile.ZipInfo("bad-entry")
            if fault == "symlink":
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
            else:
                info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, b"fake-target")
    row = upload(pack, path)
    with pytest.raises(ModelPackError):
        pack["store"].inspect(row["job_id"], scope=pack["scope"], audit=pack["audit"])
    assert not (pack["store"].root / "active.json").exists()
    assert pack["store"].status(row["job_id"], scope=pack["scope"])["status"] == "failed"


def test_cancel_upload_offset_replay_and_discard_preserves_original(pack_store):
    pack = pack_store
    row = upload(pack)
    with pytest.raises(ModelPackError, match="offset_mismatch"):
        pack["store"].chunk(row["job_id"], scope=pack["scope"], offset=0, data=b"replay")
    pack["store"].cancel(row["job_id"], scope=pack["scope"], audit=pack["audit"])
    with pytest.raises(ModelPackError, match="upload_incomplete"):
        pack["store"].inspect(row["job_id"], scope=pack["scope"], audit=pack["audit"])
    result = pack["store"].discard(row["job_id"], scope=pack["scope"], audit=pack["audit"])
    assert result["original_preserved"] and pack["path"].exists()


def test_cancel_actual_verification_and_restart_is_not_auto_activation(pack_store, monkeypatch):
    pack = pack_store
    row = upload(pack)
    entered, continue_work = threading.Event(), threading.Event()
    original = pack["store"].authority.verify

    def delayed(*args, **kwargs):
        entered.set()
        assert continue_work.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(pack["store"].authority, "verify", delayed)
    monkeypatch.setattr(pack["store"].authority, "inspection_only", lambda: pack["store"].authority)
    with ThreadPoolExecutor(1) as pool:
        pending = pool.submit(
            pack["store"].inspect, row["job_id"], scope=pack["scope"], audit=pack["audit"]
        )
        assert entered.wait(5)
        assert (
            pack["store"].cancel(row["job_id"], scope=pack["scope"], audit=pack["audit"])["status"]
            == "canceling"
        )
        continue_work.set()
        with pytest.raises(ModelPackError, match="canceled"):
            pending.result(8)
    assert pack["store"].status(row["job_id"], scope=pack["scope"])["status"] == "canceled"
    assert not (pack["store"].root / "active.json").exists()


def test_revocation_after_inspection_blocks_activation(pack_store):
    pack = pack_store
    row = upload(pack)
    result = pack["store"].inspect(row["job_id"], scope=pack["scope"], audit=pack["audit"])
    fixture = pack["fixture"]
    fixture["trust"]["revoked_key_ids"] = [fixture["envelope"]["key_id"]]
    fixture["trust_path"].write_bytes(canonical(fixture["trust"]))
    with pytest.raises(Exception, match="admission_invalid"):
        pack["store"].activate(
            row["job_id"], scope=pack["scope"], audit=pack["audit"], pack_id=result["pack_id"]
        )
    assert not (pack["store"].root / "active.json").exists()


def test_archive_central_directory_is_bounded_before_zipfile(tmp_path, monkeypatch):
    path = tmp_path / "huge.zip"
    path.write_bytes(struct.pack("<4s4H2IH", b"PK\x05\x06", 0, 0, 600, 600, 1024**3, 0, 0))
    monkeypatch.setattr(
        zipfile, "ZipFile", lambda *args: pytest.fail("must reject before ZipFile allocation")
    )
    with pytest.raises(ModelPackError, match="bounds_invalid"):
        _bounded_zip(path)


def test_inspection_and_cancel_do_not_obsolete_active_catalog(pack_store, tmp_path):
    pack = pack_store
    first = upload(pack)
    prepared = pack["store"].inspect(first["job_id"], scope=pack["scope"], audit=pack["audit"])
    assert not pack["fixture"]["authority"].state_path.exists()
    pack["store"].activate(
        first["job_id"], scope=pack["scope"], audit=pack["audit"], pack_id=prepared["pack_id"]
    )
    before = pack["fixture"]["authority"].state_path.read_bytes()
    next_path, _ = structural_pack(pack["fixture"], tmp_path / "next.zip", sequence=2)
    second = upload(pack, next_path)
    pack["store"].inspect(second["job_id"], scope=pack["scope"], audit=pack["audit"])
    pack["store"].cancel(second["job_id"], scope=pack["scope"], audit=pack["audit"])
    assert pack["fixture"]["authority"].state_path.read_bytes() == before
    assert load_active_pack(pack["store"].root, pack["fixture"]["authority"])


def test_interrupted_verification_is_visible_and_never_activated(pack_store):
    pack = pack_store
    row = upload(pack)
    state = pack["store"]._load()
    state["jobs"][row["job_id"]]["status"] = "verifying"
    pack["store"]._save(state)
    restarted = ModelPackService(pack["store"].root, pack["fixture"]["authority"])
    assert restarted.status(row["job_id"], scope=pack["scope"])["status"] == "interrupted"
    assert not (restarted.root / "active.json").exists()
    assert restarted.discard(row["job_id"], scope=pack["scope"], audit=pack["audit"])[
        "original_preserved"
    ]


def test_changed_chunk_disk_state_and_insufficient_disk_fail_closed(pack_store, monkeypatch):
    pack = pack_store
    row = pack["store"].begin(scope=pack["scope"], total_bytes=100, audit=pack["audit"])
    path = pack["store"].root / "uploads" / row["job_id"] / "incoming.zip"
    path.write_bytes(b"interrupted write")
    with pytest.raises(ModelPackError, match="partial_state_changed"):
        pack["store"].chunk(row["job_id"], scope=pack["scope"], offset=0, data=b"fresh")
    pack["store"].cancel(row["job_id"], scope=pack["scope"], audit=pack["audit"])
    import app.services.model_pack_service as module

    def no_space(*args, **kwargs):
        raise OSError("fixture storage reserve")

    monkeypatch.setattr(module, "ensure_write_capacity", no_space)
    with pytest.raises(OSError):
        pack["store"].begin(scope=pack["scope"], total_bytes=100, audit=pack["audit"])


def test_audit_failure_never_activates_or_advances_admission(pack_store):
    pack = pack_store
    row = upload(pack)
    prepared = pack["store"].inspect(row["job_id"], scope=pack["scope"], audit=pack["audit"])

    def broken_audit(*args):
        raise OSError("synthetic failed audit")

    with pytest.raises(OSError):
        pack["store"].activate(
            row["job_id"], scope=pack["scope"], audit=broken_audit, pack_id=prepared["pack_id"]
        )
    assert not (pack["store"].root / "active.json").exists()
    assert not pack["fixture"]["authority"].state_path.exists()


def test_store_cannot_overlap_source_or_matter(pack_store, tmp_path):
    pack = pack_store
    for root, forbidden in (
        (tmp_path / "source/models", tmp_path / "source"),
        (tmp_path, tmp_path / "matter"),
    ):
        with pytest.raises(ModelPackError, match="external_store_required"):
            ModelPackService(root, pack["fixture"]["authority"], forbidden_roots=(forbidden,))


def test_active_pointer_tampering_is_not_trusted(pack_store):
    pack = pack_store
    (pack["store"].root / "active.json").write_bytes(
        canonical({"schema": "fi_active_pack_v1", "pack_id": "../outside"})
    )
    with pytest.raises(ModelPackError, match="pointer_invalid"):
        load_active_pack(pack["store"].root, pack["fixture"]["authority"])


def test_api_meaningful_import_activation_and_role_isolation(pack_store, bound_host, monkeypatch):  # noqa: F811
    pack, host = pack_store, bound_host
    monkeypatch.setattr(model_packs, "configured_service", lambda root: pack["store"])
    headers = {**host["headers"], "X-User-Role": "admin"}
    client, matter = host["client"], host["body"]["matter_id"]
    body = {"matter_id": matter, "user_confirmed": True, "total_bytes": pack["path"].stat().st_size}
    assert (
        client.post("/api/model-packs/imports", json=body, headers=host["headers"]).status_code
        == 403
    )
    assert (
        client.post(
            "/api/model-packs/imports", json={**body, "user_confirmed": False}, headers=headers
        ).status_code
        == 422
    )
    row = client.post("/api/model-packs/imports", json=body, headers=headers).json()
    route = "/api/model-packs/imports/" + row["job_id"]
    assert (
        client.post(
            route + "/chunks",
            params={"matter_id": matter, "offset": 0},
            content=pack["path"].read_bytes(),
            headers=headers,
        ).status_code
        == 200
    )
    assert client.get(route, params={"matter_id": "another"}, headers=headers).status_code == 409
    result = client.post(route + "/inspect", json={"matter_id": matter}, headers=headers)
    assert result.status_code == 200, result.text
    prepared = result.json()
    result = client.post(
        route + "/activate",
        json={"matter_id": matter, "pack_id": prepared["pack_id"], "user_confirmed": True},
        headers=headers,
    )
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "activated"
    inventory = client.get("/api/model-packs", params={"matter_id": matter}, headers=headers)
    assert len(inventory.json()["models"]) == 2
    assert str(pack["store"].root) not in inventory.text
    assert (host["root"] / "40_RUNTIME/local-agent/audit.json.enc").is_file()
