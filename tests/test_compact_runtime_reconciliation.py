"""Targeted synthetic RECORD ownership and integrity parser tests."""

import base64
import hashlib
from email.parser import Parser
from types import SimpleNamespace

import pytest

from scripts.reconcile_compact_runtime import (
    build_ownership,
    parse_record,
    public_origin,
    safe_relative,
)


def row(name, data):
    sha = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip("=")
    return f"{name},sha256={sha},{len(data)}\n"


def test_record_hash_and_empty_self_entry_are_distinct():
    result = parse_record(
        (row("fixture.py", b"fictional") + "fixture.dist-info/RECORD,,\n").encode()
    )
    assert result["fixture.py"]["hash"].mode == "sha256"
    assert result["fixture.py"]["size"] == 9
    assert result["fixture.dist-info/record"]["hash"] is None


@pytest.mark.parametrize(
    "name",
    [
        "/absolute",
        "../escape",
        "a/../b",
        "a//b",
        "a/./b",
        "C:/x",
        "a\\b",
        "NUL",
        "CON.txt",
        "bad ",
        "bad.",
        "bad?name",
        "bad*name",
        "bad\x00name",
    ],
)
def test_unsafe_record_path_never_becomes_a_candidate(name):
    assert not safe_relative(name)
    assert parse_record((name + ",,\n").encode()) == {}


@pytest.mark.parametrize(
    "raw",
    [
        b"bad,row\n",
        b"same.py,,\nSAME.py,,\n",
        b"x.py,md5=abcd,1\n",
        b"x.py,sha256=invalid,1\n",
        b"x.py,,-1\n",
        b"x.py,,1500000000\n",
    ],
)
def test_invalid_record_is_not_silently_accepted(raw):
    with pytest.raises(ValueError):
        parse_record(raw)


def test_owner_index_binds_exact_distribution_and_notices(tmp_path):
    info = tmp_path / "fictional-1.0.dist-info"
    info.mkdir()
    metadata = b"Name: fictional\nVersion: 1.0\nLicense-Expression: MIT\nLicense-File: LICENSE\n\n"
    (info / "METADATA").write_bytes(metadata)
    (info / "LICENSE").write_bytes(b"fictional license fixture")
    record = (
        row("fixture.py", b"content")
        + row(info.name + "/METADATA", metadata)
        + row(info.name + "/LICENSE", b"fictional license fixture")
    )
    (info / "RECORD").write_text(record)
    owners, packages, errors = build_ownership(tmp_path, {"fixture.py"})
    assert not errors and len(owners["fixture.py"]) == 1
    package = packages[info.name]
    assert package["notice_paths"] == [info.name + "/LICENSE"]
    assert package["license_review"] == "not_cleared" and package["origin_verified"] is False
    assert package["record_sha256"] == hashlib.sha256((info / "RECORD").read_bytes()).hexdigest()


def test_origin_notes_drop_credentials_queries_and_local_paths():
    metadata = Parser().parsestr(
        "Project-URL: Source, https://example.invalid/source\n"
        "Home-page: https://user:secret@example.invalid/private\n"
        "Project-URL: Download, https://example.invalid/x?token=secret\n"
        "Project-URL: Local, file:///private/path\n"
    )
    assert public_origin(metadata) == ["https://example.invalid/source"]


@pytest.mark.parametrize(
    "size,expected,code", [(1_500_000_000, None, "size_budget"), (2, 1, "size_mismatch")]
)
def test_size_is_rejected_before_reading_unbounded_content(monkeypatch, size, expected, code):
    from scripts import audit_compact_ranker_runtime as audit

    class NoRead:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def fileno(self):
            return 99

        def read(self, *args):
            pytest.fail("invalid-size artifact was read")

    fake_path = SimpleNamespace(open=lambda mode: NoRead())
    monkeypatch.setattr(audit, "logical_path", lambda *args: ("runtime/fictional", fake_path))
    monkeypatch.setattr(audit.os, "fstat", lambda fd: SimpleNamespace(st_size=size))
    with pytest.raises(ValueError, match=code):
        audit.file_record("unused", {}, expected_size=expected)


@pytest.mark.parametrize(
    "scenario", ["valid", "missing_required", "optional_probe", "tampered", "ambiguous"]
)
def test_reconciliation_distinguishes_real_imports_from_optional_probes(
    tmp_path, monkeypatch, scenario
):
    import json

    from scripts import reconcile_compact_runtime as reconciliation

    site = tmp_path / "runtime/Lib/site-packages"
    site.mkdir(parents=True)
    source = b"# fictional source only\n"
    info = site / "fictional-1.0.dist-info"
    info.mkdir()
    metadata = b"Name: fictional\nVersion: 1.0\nLicense-Expression: MIT\nLicense-File: LICENSE\n\n"
    (info / "METADATA").write_bytes(metadata)
    notice = b"fictional notice fixture"
    (info / "LICENSE").write_bytes(notice)
    record = (
        row("fictional.py", source)
        + row(info.name + "/METADATA", metadata)
        + row(info.name + "/LICENSE", notice)
    )
    (info / "RECORD").write_text(record, encoding="utf-8")
    if scenario not in {"missing_required", "optional_probe"}:
        (site / "fictional.py").write_bytes(
            b"x" * len(source) if scenario == "tampered" else source
        )
    if scenario == "ambiguous":
        other = site / "other-1.0.dist-info"
        other.mkdir()
        (other / "METADATA").write_bytes(b"Name: other\nVersion: 1.0\n\n")
        (other / "RECORD").write_text(row("fictional.py", source), encoding="utf-8")
    logical = "package_runtime/Lib/site-packages/fictional.py"
    selection = dict(unaccounted_observed_runtime_paths=[logical], files=[], selected_bytes=0)
    trace = dict(modules=[] if scenario == "optional_probe" else [logical], native_mappings=[])
    (tmp_path / "observed-serving-selection-cpu02.json").write_text(json.dumps(selection))
    (tmp_path / "serving-trace-cpu02-3.json").write_text(json.dumps(trace))
    monkeypatch.setattr(reconciliation, "OUT", tmp_path)
    monkeypatch.setattr(reconciliation, "selected_runtime_site", lambda: site)
    result = reconciliation.reconcile("fictional")
    codes = {item["code"] for item in result["blockers"]}
    if scenario == "valid":
        assert not codes and len(result["files"]) == 1
        assert result["files"][0]["actually_imported_or_mapped"] is True
        assert result["files"][0]["installed_record_hash_checked"] is True
    elif scenario == "optional_probe":
        assert not codes and result["optional_missing_attempts"] == [logical]
        assert not result["files"]
    elif scenario == "ambiguous":
        assert "ownership_missing_or_ambiguous" in codes and not result["files"]
    else:
        assert "installed_record_integrity_failed" in codes
        assert not result["optional_missing_attempts"]
    assert all(
        result[key] is False
        for key in ("origin_verified", "runtime_qualified", "ga_ready", "production_admitted")
    )
    with pytest.raises(ValueError, match="preserve_prior_evidence"):
        reconciliation.reconcile("fictional")
