from __future__ import annotations

import hashlib
import importlib.metadata as metadata
import io
import json
import zipfile
from email.message import Message
from types import SimpleNamespace

import pytest

from scripts import audit_compact_ranker_runtime as audit
from scripts import qualify_compact_tokenizers_notice as notice


@pytest.fixture
def installed(tmp_path, monkeypatch):
    directory = tmp_path / "notices"
    directory.mkdir()
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    rows = {
        notice.INFO + "/METADATA": b"Name: tokenizers\nVersion: 0.22.2\n",
        notice.INFO + "/RECORD": b"fictional record",
        "tokenizers/tokenizers.pyd": b"fictional binary",
        "tokenizers/__init__.py": b"fictional python",
    }
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in rows.items():
            archive.writestr(name, content)
            path = runtime / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    license_bytes = b"fictional license fixture"
    wheel = {
        **notice.WHEEL,
        "bytes": len(data.getvalue()),
        "sha256": hashlib.sha256(data.getvalue()).hexdigest(),
    }
    license_pin = {
        "name": notice.LICENSE["name"],
        "url": notice.LICENSE["url"],
        "bytes": len(license_bytes),
        "sha256": hashlib.sha256(license_bytes).hexdigest(),
    }
    monkeypatch.setattr(notice, "WHEEL", wheel)
    monkeypatch.setattr(notice, "LICENSE", license_pin)
    (directory / wheel["name"]).write_bytes(data.getvalue())
    (directory / license_pin["name"]).write_bytes(license_bytes)
    info = Message()
    info["Name"] = "tokenizers"
    dist = SimpleNamespace(
        metadata=info,
        version=notice.VERSION,
        files=list(rows),
        locate_file=lambda name: runtime / name,
    )
    return dist, directory, runtime


def test_notice_requires_exact_installed_payload_and_keeps_all_gates_closed(installed):
    dist, directory, _ = installed
    proof = notice.inspect_installed(dist, directory)
    assert len(proof["installed_payload"]) == 3
    assert proof["installed_payload_matches_pinned_wheel"]
    for key in (
        "ga_ready",
        "production_admitted",
        "license_compliance_approved",
        "transitive_native_notices_qualified",
        "wheel_build_from_source_commit_proven",
    ):
        assert proof[key] is False
    assert str(directory) not in json.dumps(proof)


@pytest.mark.parametrize(
    "fault", ["changed", "missing", "extra", "direct_url", "version", "license", "wheel"]
)
def test_mismatch_cannot_qualify_notice(installed, fault):
    dist, directory, runtime = installed
    if fault == "changed":
        (runtime / "tokenizers/tokenizers.pyd").write_bytes(b"changed!! binary")
    elif fault == "missing":
        dist.files.remove("tokenizers/tokenizers.pyd")
    elif fault in {"extra", "direct_url"}:
        dist.files.append(
            notice.INFO + ("/direct_url.json" if fault == "direct_url" else "/unexpected.py")
        )
    elif fault == "version":
        dist.version = "0.22.3"
    else:
        pin = notice.LICENSE if fault == "license" else notice.WHEEL
        path = directory / pin["name"]
        path.write_bytes(b"x" * pin["bytes"])
    with pytest.raises(ValueError, match="notice_"):
        notice.inspect_installed(dist, directory)


def test_modified_record_alone_is_not_publisher_proof(installed):
    dist, directory, runtime = installed
    (runtime / (notice.INFO + "/RECORD")).write_text("pip rewrites RECORD")
    proof = notice.inspect_installed(dist, directory)
    assert proof["installed_payload_matches_pinned_wheel"]
    assert proof["wheel_build_from_source_commit_proven"] is False


@pytest.mark.parametrize(
    "name",
    [
        "../evil",
        "tokenizers/../evil",
        "C:/evil",
        "tokenizers/a\\b",
        "/tokenizers/evil",
        "unexpected/evil",
    ],
)
def test_archive_member_paths_never_extracted(name):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        # ZipInfo normalizes Windows backslashes in its constructor; preserve
        # the hostile on-disk spelling so this really tests the reader boundary.
        item = zipfile.ZipInfo("entry")
        item.filename = name
        archive.writestr(item, b"fixture")
    with pytest.raises(ValueError, match="notice_wheel_member_invalid"):
        notice.wheel_members(data.getvalue())


def test_archive_case_collision_and_link_refused():
    for names in [("tokenizers/a", "tokenizers/A"), ("tokenizers/link",)]:
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            for name in names:
                item = zipfile.ZipInfo(name)
                if name.endswith("link"):
                    item.external_attr = 0o120777 << 16
                archive.writestr(item, b"fixture")
        with pytest.raises(ValueError, match="notice_wheel_member_invalid"):
            notice.wheel_members(data.getvalue())


def test_blob_pin_requires_exact_upstream_content():
    raw = b"upstream license"
    pin = {
        "bytes": len(raw),
        "git_blob_sha1": hashlib.sha1(
            f"blob {len(raw)}\0".encode() + raw, usedforsecurity=False
        ).hexdigest(),
    }
    notice.checked_bytes(raw, pin)
    with pytest.raises(ValueError, match="source_blob_mismatch"):
        notice.checked_bytes(b"x" * len(raw), pin)


@pytest.mark.parametrize(
    "fault", ["redirect", "encoded", "overflow", "truncated", "tamper", "valid"]
)
def test_bounded_acquisition_preserves_no_unverified_payload(tmp_path, fault):
    raw = b"fictional notice"
    pin = {
        "name": "fixture.txt",
        "url": notice.LICENSE["url"],
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }

    class Response:
        status_code = 302 if fault == "redirect" else 200
        headers = {"Content-Encoding": "gzip"} if fault == "encoded" else {}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def iter_content(self, size):
            yield (
                raw + b"x"
                if fault == "overflow"
                else raw[:-1]
                if fault == "truncated"
                else b"x" * len(raw)
                if fault == "tamper"
                else raw
            )

    class Session:
        def get(self, url, **kwargs):
            assert url == pin["url"]
            assert kwargs["allow_redirects"] is False
            assert kwargs["timeout"] == (10, 20)
            assert self.trust_env is False
            return Response()

    if fault == "valid":
        result = notice.acquire(pin, tmp_path, session=Session())
        assert result.read_bytes() == raw
        # Existing valid file needs no network, and invalid one is preserved.
        notice.acquire(pin, tmp_path, session=object())
        result.write_bytes(b"modified")
        with pytest.raises(ValueError, match="size_mismatch"):
            notice.acquire(pin, tmp_path, session=object())
        assert result.read_bytes() == b"modified"
    else:
        with pytest.raises(ValueError, match="notice_"):
            notice.acquire(pin, tmp_path, session=Session())
        assert not (tmp_path / pin["name"]).exists()


def test_prior_notice_evidence_cannot_be_overwritten(tmp_path, monkeypatch):
    monkeypatch.setattr(notice, "OUTPUT", tmp_path)
    target = tmp_path / "tokenizers-notice-proof-existing.json"
    target.write_text("prior evidence")
    with pytest.raises(ValueError, match="preserve_prior_evidence"):
        notice.execute("existing", download=True)
    assert target.read_text() == "prior evidence"


def test_audit_cli_keeps_supplemental_notice_opt_in():
    import inspect

    assert inspect.signature(audit.execute).parameters["include_tokenizers_notice"].default is False


@pytest.mark.parametrize("fault", [None, "tamper", "declared_missing"])
def test_full_inventory_consumes_verified_notice_without_admitting_runtime(
    installed, monkeypatch, fault
):
    dist, directory, runtime = installed
    output = directory.parent / "evidence"
    output.mkdir()
    (runtime / "pyvenv.cfg").write_text("fictional")
    entries = []
    for name in dist.files:
        entry = metadata.PackagePath(name)
        entry.hash = None
        entry.size = (runtime / name).stat().st_size
        entries.append(entry)
    dist.files = entries
    if fault == "tamper":
        (directory / notice.LICENSE["name"]).write_bytes(b"x" * notice.LICENSE["bytes"])
    if fault == "declared_missing":
        dist.metadata["License-File"] = "MISSING-NATIVE-NOTICE"
    monkeypatch.setattr(audit, "OUTPUT", output)
    monkeypatch.setattr(notice, "DIRECTORY", directory)
    monkeypatch.setattr(
        audit,
        "runtime_roots",
        lambda _root: {"package_runtime": runtime, "python_runtime": runtime},
    )
    monkeypatch.setattr(audit, "dependency_closure", lambda _: ({"tokenizers": dist}, [], []))
    monkeypatch.setattr(audit, "python_runtime_files", lambda _: [])
    monkeypatch.setattr(audit, "model_inventory", lambda _: {"bytes": 0, "files": []})
    assert audit.execute("supplement", include_tokenizers_notice=True) is (fault is None)
    report = json.loads((output / "ranker-runtime-audit-supplement.json").read_text())
    assert report["installed_notice_inventory_complete"] is False
    assert report["notice_inventory_complete"] is (fault is None)
    assert report["installed_selection_integrity_passed"] is (fault != "tamper")
    assert report["ga_ready"] is False
    assert report["production_admitted"] is False
    assert report["complete_runtime_qualified"] is False
    assert report["decision"] == "BLOCKED_RUNTIME_QUALIFICATION"
    if fault != "tamper":
        item = report["packages"][0]["notice_files"][0]
        assert item["path"].startswith("supplemental_notices/")
        assert report["package_bytes"] == sum(p.size for p in entries) + notice.LICENSE["bytes"]
