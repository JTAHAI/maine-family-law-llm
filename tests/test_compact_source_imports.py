"""Real child imports and parent handshake; no model-quality claims."""

import hashlib
import importlib
import json
import os
import sys
import py_compile
import subprocess

import psutil
import pytest
from test_compact_ranker_process import worker

from legal.agent_runtime.providers import LocalModelError
from legal.fast_interchange.compact_network_guard import GUARD_VERSION
from legal.fast_interchange.compact_ranker_process import WORKER_BOOTSTRAP
from legal.fast_interchange.compact_source_imports import (
    SOURCE_ALLOWLIST_VERSION,
    SOURCE_IMPORT_VERSION,
    source_only_active,
)


def child(tmp_path, body, *, allowlist=None, allowlist_sha256=None):
    prefix = WORKER_BOOTSTRAP.split(
        "from legal.fast_interchange.compact_ranker_worker import main;"
    )[0]
    command = [
        psutil.Process().exe(),
        "-I",
        "-S",
        "-B",
        "-c",
        prefix + body,
        str(tmp_path),
        str(tmp_path),
    ]
    if allowlist is not None:
        command.extend([str(allowlist), str(allowlist_sha256)])
    return subprocess.run(
        command,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=15,
        env={"TEMP": str(tmp_path), "TMP": str(tmp_path)},
    )


def test_valid_stale_cache_is_ignored_in_favor_of_source(tmp_path):
    source = tmp_path / "fictional_module.py"
    source.write_text("value='OLD'\n")
    info = source.stat()
    cache = py_compile.compile(str(source), doraise=True)
    source.write_text("value='NEW'\n")
    os.utime(source, ns=(info.st_atime_ns, info.st_mtime_ns))
    assert source.stat().st_size == info.st_size
    result = child(
        tmp_path, "import fictional_module,json; print(json.dumps(fictional_module.value))"
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == "NEW"
    assert cache and not source_only_active()  # Host imports were not monkeypatched.


def test_explicit_sourceless_loader_cannot_execute_cached_code(tmp_path):
    source = tmp_path / "fictional_module.py"
    source.write_text("raise RuntimeError('SHOULD_NOT_EXECUTE')\n")
    cache = py_compile.compile(str(source), doraise=True)
    result = child(
        tmp_path,
        "import importlib.machinery;"
        + f"importlib.machinery.SourcelessFileLoader('fictional',{cache!r}).get_code('fictional')",
    )
    assert result.returncode != 0
    assert "compact_sourceless_import_forbidden" in result.stderr
    assert "SHOULD_NOT_EXECUTE" not in result.stderr


def test_new_source_import_does_not_create_cache(tmp_path):
    (tmp_path / "fictional_module.py").write_text("value=1\n")
    result = child(tmp_path, "import fictional_module; print(fictional_module.value)")
    assert result.returncode == 0 and result.stdout.strip() == "1"
    assert not (tmp_path / "__pycache__").exists()


def test_hash_bound_allowlist_permits_only_selected_source(tmp_path):
    (tmp_path / "allowed.py").write_text("value = 'allowed'\n")
    (tmp_path / "unlisted.py").write_text("value = 'unlisted'\n")
    document = {
        "schema_version": SOURCE_ALLOWLIST_VERSION,
        "paths": ["repository/allowed.py"],
    }
    allowlist = tmp_path / "allowlist.json"
    raw = json.dumps(document, separators=(",", ":")).encode()
    allowlist.write_bytes(raw)
    checksum = hashlib.sha256(raw).hexdigest()
    permitted = child(
        tmp_path,
        "import allowed,json; print(json.dumps(allowed.value))",
        allowlist=allowlist,
        allowlist_sha256=checksum,
    )
    assert permitted.returncode == 0, permitted.stderr
    assert json.loads(permitted.stdout) == "allowed"
    denied = child(
        tmp_path,
        "import unlisted",
        allowlist=allowlist,
        allowlist_sha256=checksum,
    )
    assert denied.returncode != 0
    assert "compact_source_not_selected" in denied.stderr


def test_allowlist_hash_tampering_fails_before_source_import(tmp_path):
    (tmp_path / "allowed.py").write_text("value = 'allowed'\n")
    allowlist = tmp_path / "allowlist.json"
    allowlist.write_text(
        json.dumps({"schema_version": SOURCE_ALLOWLIST_VERSION, "paths": ["repository/allowed.py"]})
    )
    result = child(
        tmp_path,
        "import allowed",
        allowlist=allowlist,
        allowlist_sha256="0" * 64,
    )
    assert result.returncode != 0
    assert "compact_source_allowlist_integrity_invalid" in result.stderr


def test_hash_bound_allowlist_governs_a_real_native_extension(tmp_path):
    """Exercise the ExtensionFileLoader hook against Python's installed pyd.

    This is deliberately a bootstrap test, not a claim that the compact
    runtime's complete native dependency graph has been selected.
    """
    module = importlib.import_module("_sqlite3")
    location = os.path.realpath(module.__file__)
    root = os.path.realpath(sys.base_prefix)
    relative = os.path.relpath(location, root).replace("\\", "/")
    if relative.startswith("../"):
        pytest.skip("_sqlite3 is outside the interpreter root")
    allowlist = tmp_path / "native-allowlist.json"
    raw = json.dumps(
        {"schema_version": SOURCE_ALLOWLIST_VERSION, "paths": ["python_runtime/" + relative]},
        separators=(",", ":"),
    ).encode()
    allowlist.write_bytes(raw)
    checksum = hashlib.sha256(raw).hexdigest()
    permitted = child(
        tmp_path,
        "import _sqlite3; print(_sqlite3.sqlite_version)",
        allowlist=allowlist,
        allowlist_sha256=checksum,
    )
    assert permitted.returncode == 0, permitted.stderr
    denied_raw = json.dumps(
        {"schema_version": SOURCE_ALLOWLIST_VERSION, "paths": ["repository/unused.py"]},
        separators=(",", ":"),
    ).encode()
    allowlist.write_bytes(denied_raw)
    denied = child(
        tmp_path,
        "import _sqlite3",
        allowlist=allowlist,
        allowlist_sha256=hashlib.sha256(denied_raw).hexdigest(),
    )
    assert denied.returncode != 0
    assert "compact_source_not_selected" in denied.stderr


@pytest.mark.parametrize("policy", [None, "legacy", False, SOURCE_IMPORT_VERSION])
def test_warm_ack_requires_source_policy(tmp_path, monkeypatch, policy):
    engine = worker(tmp_path)
    response = dict(
        status="warm",
        forward_passes=1,
        model_sha256="a" * 64,
        review_required=True,
        production_admitted=False,
        network_guard=GUARD_VERSION,
    )
    if policy is not None:
        response["source_import_policy"] = policy
    stopped = []
    monkeypatch.setattr(engine, "_start", lambda: None)
    monkeypatch.setattr(engine, "_exchange", lambda *args, **kwargs: response)
    monkeypatch.setattr(engine, "_stop", lambda: stopped.append(True))
    if policy == SOURCE_IMPORT_VERSION:
        engine._ensure_warm()
        assert engine._warm and not stopped
    else:
        with pytest.raises(LocalModelError, match="compact local worker"):
            engine._ensure_warm()
        assert stopped and not engine._warm
