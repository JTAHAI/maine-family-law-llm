"""Actual local Windows file locks; synthetic bytes, not model inference."""

import hashlib
import json
import os
from copy import deepcopy
from pathlib import Path
from threading import Event

import pytest
from test_compact_admission import compact  # noqa: F401,F811

from legal.fast_interchange.admission import AdmissionError, digest
from legal.fast_interchange.compact_artifacts import verified_compact_artifacts

pytestmark = pytest.mark.skipif(
    os.name != "nt", reason="Windows lock boundary; no POSIX equivalence claimed"
)


@pytest.fixture
def files(compact, tmp_path):  # noqa: F811
    roots = dict(model=tmp_path / "model", runtime=tmp_path / "runtime", repository=tmp_path / "repository")
    for root in roots.values():
        root.mkdir()
    for kind, rows in (
        (
            "model",
            [
                ("model.safetensors", b"synthetic-weights", "weights"),
                ("README.md", b"synthetic-not-a-model", "notice"),
            ],
        ),
        (
            "runtime",
            [("python.exe", b"synthetic-runtime", "runtime"), ("empty.py", b"", "runtime")],
        ),
    ):
        compact[kind]["files"] = []
        for name, data, role in rows:
            (roots[kind] / name).write_bytes(data)
            compact[kind]["files"].append(
                dict(
                    path=name if kind == "model" else "runtime/" + name,
                    bytes=len(data),
                    sha256=hashlib.sha256(data).hexdigest(),
                    role=role,
                )
            )
    (roots["repository"] / "allowed.py").write_bytes(b"value = 'allowed'\n")
    row = dict(
        path="repository/allowed.py",
        bytes=(roots["repository"] / "allowed.py").stat().st_size,
        sha256=hashlib.sha256((roots["repository"] / "allowed.py").read_bytes()).hexdigest(),
        role="runtime",
    )
    compact["runtime"]["files"].append(row)
    grant = compact["payload"]["grants"][0]
    grant["model_inventory_sha256"] = digest(compact["model"])
    grant["runtime"]["inventory_sha256"] = digest(compact["runtime"])
    grant["rights"]["notices_inventory_sha256"] = digest(
        [
            dict(kind=kind, **row)
            for kind in ("model", "runtime")
            for row in compact[kind]["files"]
            if row["role"] == "notice"
        ]
    )
    return compact, roots


def open_lease(files, **overrides):
    f, roots = files
    args = dict(
        model_inventory=f["model"],
        runtime_inventory=f["runtime"],
        roots=roots,
        expected_model={r["path"]: (r["bytes"], r["sha256"]) for r in f["model"]["files"]},
        expected_policies=f["policies"],
        release_id="fictional-release",
    )
    args.update(overrides)
    return verified_compact_artifacts(f["authority"], f["sign"](f["payload"]), **args)


def test_actual_byte_locks_block_writes_and_rename_then_release(files):
    f, roots = files
    updates = []
    with open_lease(files, progress=updates.append) as lease:
        receipt = lease.receipt()
        assert receipt["artifact_bytes_verified"] is True
        assert receipt["windows_read_locks_held"] is True
        assert receipt["selected_files"] == 5
        assert receipt["selected_bytes"] == sum(
            r["bytes"] for k in ("model", "runtime") for r in f[k]["files"]
        )
        assert receipt["runtime_scope"] == "selected_files_only"
        assert (
            not receipt["production_admitted"]
            and not receipt["runnable"]
            and not receipt["native_closure_qualified"]
        )
        # A caller cannot mutate the identity it will later approve.
        receipt["task"]["field_type"] = "money"
        assert lease.receipt()["task"]["field_type"] == "clock_time"
        for target in (roots["model"] / "model.safetensors", roots["runtime"] / "python.exe"):
            with pytest.raises(OSError):
                target.write_bytes(b"altered")
            with pytest.raises(OSError):
                target.rename(target.with_suffix(".moved"))
        with pytest.raises(OSError):
            roots["model"].rename(roots["model"].with_name("moved-model"))
    with pytest.raises(AdmissionError, match="lease_closed"):
        lease.receipt()
    (roots["model"] / "model.safetensors").write_bytes(b"unlocked")
    assert len(updates) == 5 and all(
        set(u) == {"files_verified", "total_files", "bytes_verified"} for u in updates
    )


@pytest.mark.parametrize(
    "defect,code",
    [
        ("hash", "hash_mismatch"),
        ("size", "size_mismatch"),
        ("missing", "verification_failed"),
        ("extra", "model_layout_mismatch"),
        ("directory", "link_or_type_forbidden"),
        ("notice", "hash_mismatch"),
    ],
)
def test_bad_actual_files_do_not_advance_or_leak_locks(files, defect, code):
    f, roots = files
    target = roots["model"] / ("README.md" if defect == "notice" else "model.safetensors")
    if defect in {"hash", "notice"}:
        target.write_bytes(b"x" * target.stat().st_size)
    elif defect == "size":
        target.write_bytes(b"x")
    elif defect in {"missing", "directory"}:
        target.rename(target.with_suffix(".saved"))
        if defect == "directory":
            target.mkdir()
    else:
        (roots["model"] / "unapproved.py").write_bytes(b"untrusted")
    with pytest.raises(AdmissionError, match=code):
        with open_lease(files):
            pytest.fail("invalid files leased")
    assert not f["authority"].state_path.exists()
    # On failure any earlier locked notice must be released.
    (roots["model"] / "README.md").write_bytes(b"released")


@pytest.mark.parametrize(
    "defect,code",
    [
        ("pins", "code_pins_mismatch"),
        ("notices", "notices_binding_mismatch"),
        ("release", "release_not_declared"),
        ("runtime_root", "runtime_root_missing"),
    ],
)
def test_binding_denials(files, defect, code):
    f, roots = files
    overrides = {}
    if defect == "pins":
        overrides["expected_model"] = {}
    elif defect == "notices":
        f["payload"]["grants"][0]["rights"]["notices_inventory_sha256"] = "0" * 64
    elif defect == "release":
        overrides["release_id"] = "wrong-release"
    else:
        overrides["roots"] = dict(model=roots["model"])
    with pytest.raises(AdmissionError, match=code):
        with open_lease(files, **overrides):
            pytest.fail("bad binding leased")
    assert not f["authority"].state_path.exists()


@pytest.mark.parametrize("when", [0, 1, 4])
def test_cancel_releases_all_locks_without_advancing(files, when):
    f, roots = files
    cancel = Event()
    if when == 0:
        cancel.set()

    def progress(update):
        if update["files_verified"] == when:
            cancel.set()

    with pytest.raises(AdmissionError, match="canceled"):
        with open_lease(files, cancellation=cancel, progress=progress):
            pytest.fail("canceled lease")
    assert not f["authority"].state_path.exists()
    (roots["model"] / "README.md").write_bytes(b"released")


def test_trust_is_rechecked_after_hashing(files):
    f, _ = files

    def revoke(update):
        if update["files_verified"] == update["total_files"]:
            from legal.fast_interchange.admission import canonical

            f["trust"]["revoked_release_ids"] = ["fictional-release"]
            f["trust_path"].write_bytes(canonical(f["trust"]))

    with pytest.raises(AdmissionError, match="release_revoked"):
        with open_lease(files, progress=revoke):
            pytest.fail("revoked while verifying")
    assert not f["authority"].state_path.exists()


def test_hardlink_alias_cannot_hide_duplicate_identity(files):
    f, roots = files
    alias = roots["runtime"] / "alias.py"
    os.link(roots["runtime"] / "python.exe", alias)
    row = deepcopy(f["runtime"]["files"][0])
    row["path"] = "runtime/alias.py"
    f["runtime"]["files"].append(row)
    f["payload"]["grants"][0]["runtime"]["inventory_sha256"] = digest(f["runtime"])
    with pytest.raises(AdmissionError, match="duplicate_file_identity"):
        with open_lease(files):
            pytest.fail("aliased file counted twice")


def test_consumer_exception_keeps_original_error_and_unlocks(files):
    _, roots = files
    with pytest.raises(RuntimeError, match="fictional-consumer-failure"):
        with open_lease(files):
            raise RuntimeError("fictional-consumer-failure")
    (roots["model"] / "README.md").write_bytes(b"released")


@pytest.mark.parametrize("directory", [False, True])
def test_actual_reparse_point_is_not_followed(files, directory):
    _, roots = files
    original = roots["model"] if directory else roots["model"] / "model.safetensors"
    saved = original.with_name(original.name + "-original")
    original.rename(saved)
    try:
        original.symlink_to(saved, target_is_directory=directory)
    except OSError as exc:
        if getattr(exc, "winerror", None) == 1314:
            pytest.skip("Windows does not grant symbolic-link creation to this test user")
        raise
    with pytest.raises(AdmissionError, match="link_or_type_forbidden"):
        with open_lease(files):
            pytest.fail("reparse point accepted")


def test_caller_mutation_cannot_rebind_in_progress_inspection(files):
    f, _ = files
    original_task = deepcopy(f["payload"]["grants"][0]["task"])

    def mutate(update):
        f["payload"]["grants"][0]["task"]["field_type"] = "money"
        f["model"]["files"][0]["sha256"] = "0" * 64
        f["policies"].clear()

    with open_lease(files, progress=mutate) as lease:
        assert lease.receipt()["task"] == original_task


def test_actual_windows_junction_rejected_without_following(files):
    import _winapi

    _, roots = files
    original = roots["model"]
    saved = original.with_name("original-model")
    original.rename(saved)
    _winapi.CreateJunction(str(saved), str(original))
    with pytest.raises(AdmissionError, match="link_or_type_forbidden"):
        with open_lease(files):
            pytest.fail("junction accepted")
    assert (saved / "model.safetensors").read_bytes() == b"synthetic-weights"


def test_missing_runtime_binding_is_rejected_before_any_artifact_read(files, monkeypatch):
    from legal.fast_interchange.compact_artifacts import _WindowsLocks

    _, roots = files

    def forbidden_read(*args):
        pytest.fail("missing runtime binding triggered artifact read")

    monkeypatch.setattr(_WindowsLocks, "verify_file", forbidden_read)
    with pytest.raises(AdmissionError, match="runtime_root_missing"):
        with open_lease(files, roots={"model": roots["model"]}):
            pytest.fail("missing root accepted")


def test_lease_derived_allowlist_is_locked_and_removed_with_lease(files, tmp_path):
    _, roots = files
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    with open_lease(files) as lease:
        path, checksum = lease.worker_allowlist(scratch)
        raw = Path(path).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == checksum
        assert json.loads(raw) == {
            "schema_version": "compact_source_allowlist_v1",
            "paths": ["repository/allowed.py"],
        }
        with pytest.raises(OSError):
            Path(path).write_bytes(b"changed")
        assert lease.worker_allowlist(scratch) == (path, checksum)
    assert not Path(path).exists()


def test_canceled_allowlist_acquisition_does_not_orphan_scratch_file(files, tmp_path):
    cancel = Event()
    scratch = tmp_path / "scratch-canceled"
    scratch.mkdir()
    target = scratch / "compact-serving-allowlist.json"
    with open_lease(files, cancellation=cancel) as lease:
        cancel.set()
        with pytest.raises(AdmissionError, match="canceled"):
            lease.worker_allowlist(scratch)
    assert not target.exists()
