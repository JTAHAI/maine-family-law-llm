from __future__ import annotations

import base64
import hashlib
import importlib.metadata as metadata
import json
from email.message import Message
from types import SimpleNamespace

import pytest

from scripts import audit_compact_ranker_runtime as audit


def distribution(name, requires=(), version="1.0", licenses=()):
    info = Message()
    info["Name"] = name
    for license_file in licenses:
        info["License-File"] = license_file
    return SimpleNamespace(metadata=info, version=version, requires=requires)


def lookup_from(rows):
    def lookup(name):
        if name not in rows:
            raise metadata.PackageNotFoundError(name)
        return rows[name]

    return lookup


def test_closure_platform_default_and_transitive_extras():
    rows = {
        "root": distribution(
            "Root",
            [
                "child[fast]>=1",
                "win; sys_platform == 'win32'",
                "cuda; sys_platform == 'linux'",
                "unused; extra == 'training'",
            ],
        ),
        "child": distribution("child", ["leaf; extra == 'fast'", "root"]),
        "leaf": distribution("leaf"),
        "win": distribution("win"),
    }
    packages, edges, blockers = audit.dependency_closure(
        ["root"], lookup_from(rows), {"sys_platform": "win32"}
    )
    assert not blockers
    assert set(packages) == {"root", "child", "leaf", "win"}
    assert len(edges) == 4


def test_closure_revisits_dependency_for_later_extra():
    rows = {
        "root": distribution("root", ["child", "middle"]),
        "middle": distribution("middle", ["child[fast]"]),
        "child": distribution("child", ["leaf; extra == 'fast'"]),
        "leaf": distribution("leaf"),
    }
    packages, _, blockers = audit.dependency_closure(["root"], lookup_from(rows))
    assert "leaf" in packages
    assert not blockers


def test_dependency_failures_are_reported_without_url_credentials():
    rows = {
        "root": distribution(
            "root",
            [
                "child>=2",
                "missing",
                "malformed???",
                "urlpkg @ https://secret:password@example.test/wheel.whl",
            ],
        ),
        "child": distribution("child"),
    }
    _, _, blockers = audit.dependency_closure(["root"], lookup_from(rows))
    assert {b["code"] for b in blockers} == {
        "dependency_version_mismatch",
        "required_distribution_missing",
        "invalid_dependency_metadata",
        "direct_url_dependency_requires_review",
    }
    assert "secret" not in json.dumps(blockers)
    assert "password" not in json.dumps(blockers)


@pytest.mark.parametrize(
    "identity,code",
    [
        ("other", "distribution_identity_mismatch"),
        ("../../secret", "invalid_distribution_identity"),
    ],
)
def test_invalid_distribution_identity(identity, code):
    packages, _, blockers = audit.dependency_closure(
        ["root"], lookup_from({"root": distribution(identity)})
    )
    assert not packages
    assert blockers == [{"code": code, "package": "root"}]


@pytest.mark.parametrize("algorithm", ["sha256", "sha384", "sha512"])
def test_installed_record_integrity_and_tampering(tmp_path, algorithm):
    path = tmp_path / "engine.dll"
    path.write_bytes(b"fictional engine")
    encoded = (
        base64.urlsafe_b64encode(hashlib.new(algorithm, path.read_bytes()).digest())
        .decode()
        .rstrip("=")
    )
    record_hash = SimpleNamespace(mode=algorithm, value=encoded)
    result = audit.file_record(
        path, {"runtime": tmp_path}, expected_hash=record_hash, expected_size=16
    )
    assert result["path"] == "runtime/engine.dll"
    assert result["installed_record_hash_checked"] is True
    path.write_bytes(b"modified engine!")
    with pytest.raises(ValueError, match="installed_record_hash_mismatch"):
        audit.file_record(path, {"runtime": tmp_path}, expected_hash=record_hash)


def test_record_size_missing_file_weak_hash_and_root_escape(tmp_path):
    root = tmp_path / "allowed"
    root.mkdir()
    path = tmp_path / "outside.txt"
    path.write_bytes(b"fixture")
    with pytest.raises(ValueError, match="outside_approved_roots"):
        audit.file_record(path, {"runtime": root})
    with pytest.raises(ValueError, match="size_mismatch"):
        audit.file_record(path, {"runtime": tmp_path}, expected_size=500)
    with pytest.raises(ValueError, match="unsupported_record_hash"):
        audit.file_record(
            path, {"runtime": tmp_path}, expected_hash=SimpleNamespace(mode="md5", value="x")
        )
    with pytest.raises(FileNotFoundError):
        audit.file_record(root / "missing", {"runtime": root})


def test_pep639_legacy_and_nested_notices():
    dist = distribution("demo", licenses=["LICENSE", "third-party/NOTICE.txt", "COPYING"])
    names = {
        "demo.dist-info/METADATA",
        "demo.dist-info/licenses/LICENSE",
        "demo.dist-info/licenses/third-party/NOTICE.txt",
        "demo.dist-info/COPYING",
    }
    notices, missing = audit.license_paths(dist, names)
    assert len(notices) == 3
    assert not missing


def test_missing_notice_and_unsafe_declared_paths():
    dist = distribution("demo", licenses=["LICENSE", "../secret", "C:/secret"])
    notices, missing = audit.license_paths(dist, {"demo.dist-info/METADATA"})
    assert not notices
    assert missing == ["LICENSE", "unsafe_declared_license_path", "unsafe_declared_license_path"]


def test_python_selection_preserves_tests_but_excludes_environment_caches(tmp_path):
    names = [
        "python.exe",
        "python311.dll",
        "LICENSE.txt",
        "NEWS.txt",
        "Lib/os.py",
        "Lib/test/test_os.py",
        "Lib/site-packages/other.py",
        "Lib/__pycache__/os.pyc",
        "Lib/test/test_os.pyc",
        "DLLs/libffi.dll",
        "tcl/init.tcl",
    ]
    for name in names:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fictional")
    selected = {p.relative_to(tmp_path).as_posix() for p in audit.python_runtime_files(tmp_path)}
    assert selected == {
        "python.exe",
        "python311.dll",
        "LICENSE.txt",
        "Lib/os.py",
        "Lib/test/test_os.py",
        "DLLs/libffi.dll",
        "tcl/init.tcl",
    }


def model_fixture(directory):
    names = [
        "README.md",
        "config.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "model.safetensors",
        "config_sentence_transformers.json",
    ]
    rows = []
    for name in names:
        content = b"fictional"
        (directory / name).write_bytes(content)
        rows.append(
            {"path": name, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
        )
    (directory / "acquisition.json").write_text(json.dumps({"files": rows}))
    return rows


def test_model_bytes_require_exact_existing_receipt(tmp_path):
    model_fixture(tmp_path)
    result = audit.model_inventory(tmp_path)
    assert result["bytes"] == 54
    assert len(result["files"]) == 6
    (tmp_path / "model.safetensors").write_bytes(b"modified!")
    with pytest.raises(ValueError, match="model_receipt_hash_mismatch"):
        audit.model_inventory(tmp_path)


@pytest.mark.parametrize("replacement", ["../outside", "config.json"])
def test_model_receipt_rejects_traversal_and_duplicates(tmp_path, replacement):
    rows = model_fixture(tmp_path)
    rows[0]["path"] = replacement
    (tmp_path / "acquisition.json").write_text(json.dumps({"files": rows}))
    with pytest.raises(ValueError, match="model_receipt_selection_mismatch"):
        audit.model_inventory(tmp_path)


@pytest.mark.parametrize("run_id", ["../escape", "long" * 10, "x/y", "", "UPPER"])
def test_audit_id_cannot_escape_output(run_id):
    with pytest.raises(ValueError, match="invalid_audit_id"):
        audit.execute(run_id)


def test_prior_inventory_never_overwritten(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "OUTPUT", tmp_path)
    existing = tmp_path / "ranker-runtime-files-test.jsonl"
    existing.write_text("prior evidence")
    with pytest.raises(ValueError, match="preserve_prior_evidence"):
        audit.execute("test")
    assert existing.read_text() == "prior evidence"


def test_explicit_package_runtime_requires_existing_windows_venv(tmp_path):
    with pytest.raises(ValueError, match="explicit_windows_venv"):
        audit.runtime_roots(tmp_path)
    (tmp_path / "Scripts").mkdir()
    (tmp_path / "Lib/site-packages").mkdir(parents=True)
    (tmp_path / "pyvenv.cfg").write_text("fictional environment")
    (tmp_path / "Scripts/python.exe").write_bytes(b"fixture")
    assert audit.runtime_roots(tmp_path)["package_runtime"] == tmp_path.resolve()


@pytest.mark.parametrize("fault", [None, "tamper", "notice"])
def test_full_audit_never_promotes_runtime_to_ga(tmp_path, monkeypatch, fault):
    environment = tmp_path / "environment"
    environment.mkdir()
    (environment / "pyvenv.cfg").write_text("fictional environment")
    python = tmp_path / "python"
    python.mkdir()
    (python / "python.exe").write_bytes(b"fictional executable")
    output = tmp_path / "evidence"
    model = output / "legal-passage-reranker"
    model.mkdir(parents=True)
    model_fixture(model)

    class Entry(str):
        pass

    dist = distribution("fixture", licenses=["LICENSE"])
    entries = []
    for filename in (
        "fixture.dist-info/METADATA",
        "fixture.dist-info/licenses/LICENSE",
        "engine.dll",
    ):
        if fault == "notice" and filename.endswith("LICENSE"):
            continue
        path = environment / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fixture")
        entry = Entry(filename)
        entry.size = 7
        entry.hash = SimpleNamespace(
            mode="sha256",
            value=base64.urlsafe_b64encode(hashlib.sha256(b"fixture").digest())
            .decode()
            .rstrip("="),
        )
        entries.append(entry)
    dist.files = entries
    dist.locate_file = lambda entry: environment / entry
    if fault == "tamper":
        (environment / "engine.dll").write_bytes(b"changed")
    monkeypatch.setattr(audit, "OUTPUT", output)
    monkeypatch.setattr(
        audit,
        "runtime_roots",
        lambda _root: {"package_runtime": environment, "python_runtime": python},
    )
    monkeypatch.setattr(audit, "dependency_closure", lambda _seeds: ({"fixture": dist}, [], []))
    assert audit.execute("fixture") is (fault is None)
    report = json.loads((output / "ranker-runtime-audit-fixture.json").read_text())
    assert report["decision"] == "BLOCKED_RUNTIME_QUALIFICATION"
    assert not report["ga_ready"]
    assert not report["production_admitted"]
    assert not report["complete_runtime_qualified"]
    assert report["measured_selection_under_cap"] is (fault != "tamper")
    assert report["installed_selection_integrity_passed"] is (fault != "tamper")
    assert report["notice_inventory_complete"] is (fault != "notice")
    inventory = output / report["inventory_file"]
    assert report["inventory_sha256"] == hashlib.sha256(inventory.read_bytes()).hexdigest()
    assert str(tmp_path) not in json.dumps(report)
