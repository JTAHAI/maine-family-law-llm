from __future__ import annotations

import json
import subprocess
import zipfile
from pathlib import Path

import pytest
from maine_family_law_llm import store_preflight as preflight_module

from maine_family_law_llm.store_preflight import (
    build_preflight_report,
    main,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def preflight_inputs(tmp_path_factory):
    # Small explicit negative fixture, not an ignored multi-GB historic build.
    root = tmp_path_factory.mktemp("preflight-inputs")
    candidate = root / "fictional-old-candidate.msix"
    identity = json.loads((REPO_ROOT / "store/msix/identity.example.json").read_text())
    identity["package_version"] = "8.0.0.0"
    manifest = (REPO_ROOT / "store/msix/AppxManifest.xml.in").read_text()
    for name, value in identity.items():
        manifest = manifest.replace(f"__{name.upper()}__", value)
    with zipfile.ZipFile(candidate, "w") as archive:
        archive.writestr("AppxManifest.xml", manifest)
    evidence = root / "evidence"
    evidence.mkdir()
    wack = root / "wack.json"
    wack.write_text(json.dumps({"status": "blocked", "reason": "synthetic_not_run"}))
    return candidate, evidence, wack


@pytest.fixture(scope="module")
def preflight_report(preflight_inputs) -> dict[str, object]:
    return build_preflight_report(
        REPO_ROOT,
        *preflight_inputs,
    )


def test_store_preflight_report_fail_closes_on_missing_qualification_evidence_and_wack(preflight_report: dict[str, object], preflight_inputs) -> None:
    # A synthetic old package must not satisfy the current release identity.
    assert preflight_report["manifest_audit"]["status"] == "fail"
    assert preflight_report["manifest_audit"]["issues"] == ["version_mismatch"]
    assert preflight_report["manifest_audit"]["identity"]["Version"] == "8.0.0.0"
    # Missing payload and qualification evidence must remain blockers.
    assert preflight_report["content_audit"]["status"] == "fail"
    assert preflight_report["content_audit"]["issues"]
    assert preflight_report["evidence_audit"]["status"] == "fail"
    assert "missing_installed_offline_qualification" in preflight_report["evidence_audit"]["issues"]
    assert preflight_report["wack"]["status"] == "blocked"
    assert preflight_report["final_readiness_state"] == "BLOCKED"
    assert len(str(preflight_report["package"]["sha256"])) == 64
    assert preflight_report["package"]["path"] == str(preflight_inputs[0].resolve())


def test_store_preflight_cli_writes_expected_evidence(tmp_path, preflight_report: dict[str, object], preflight_inputs) -> None:
    json_path = tmp_path / "store-preflight.json"
    txt_path = tmp_path / "store-preflight.txt"
    exit_code = main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--msix-path",
            str(preflight_inputs[0]),
            "--evidence-root",
            str(preflight_inputs[1]),
            "--wack-result",
            str(preflight_inputs[2]),
            "--output-json",
            str(json_path),
            "--output-txt",
            str(txt_path),
        ]
    )
    assert exit_code == 0
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["final_readiness_state"] == "BLOCKED"
    assert payload["wack"]["status"] == "blocked"
    assert "WACK: blocked" in txt_path.read_text(encoding="utf-8")
    assert payload["package"]["sha256"] == preflight_report["package"]["sha256"]


def test_wack_report_without_legacy_path_is_bound_to_candidate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    candidate = tmp_path / "candidate.msix"
    candidate.write_bytes(b"candidate")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    wack = tmp_path / "wack-result.json"
    wack.write_text(json.dumps({"status": "blocked", "package": {"sha256": "a" * 64}}), encoding="utf-8")
    monkeypatch.setattr(preflight_module, "sha256_file", lambda _path: "b" * 64)
    monkeypatch.setattr(preflight_module, "audit_manifest", lambda *_args: {"status": "pass", "issues": []})
    monkeypatch.setattr(preflight_module, "audit_archive", lambda *_args: {"status": "pass", "issues": []})
    monkeypatch.setattr(preflight_module, "audit_evidence", lambda *_args: {"status": "pass", "issues": []})
    report = build_preflight_report(REPO_ROOT, candidate, evidence, wack)
    assert report["wack"]["package_path"] == str(candidate.resolve())
    assert "wack:package_hash_mismatch" in report["blockers"]
    assert report["final_readiness_state"] == "BLOCKED"


@pytest.mark.parametrize(
    ("change", "blocker"),
    [
        ({"package": {"sha256": "a" * 64}}, "wack:package_hash_mismatch"),
        ({"package": {}}, "wack:package_hash_missing"),
        ({"package_path": "unrelated.msix"}, "wack:package_path_mismatch"),
        ({"status": "completed"}, "wack:completed"),
        ({"execution_status": "not_run"}, "wack:execution_not_completed"),
        ({"blockers": ["failed_test"]}, "wack:qualification_blockers_present"),
        ({"store_release_blocked": True}, "wack:qualification_blockers_present"),
        ({"report": {"failure_count": 1}}, "wack:report_failed"),
        ({"report": {"parser_error": "bad_xml"}}, "wack:report_failed"),
        ({"report": {}}, "wack:report_evidence_missing"),
        ({"report": {"failure_count": 0, "sha256": "c" * 64}}, "wack:explicit_passed_tests_missing"),
        ({"package_sha256": "a" * 64}, "wack:conflicting_package_hashes"),
        ({}, None),
    ],
)
def test_readiness_requires_consistent_success_for_exact_package(monkeypatch, tmp_path, change, blocker):
    candidate = tmp_path / "candidate.msix"
    candidate.write_bytes(b"fictional-package")
    result = tmp_path / "wack-result.json"
    payload = {
        "status": "pass",
        "execution_status": "completed",
        "package": {"sha256": "b" * 64},
        "report": {"failure_count": 0, "passed_test_count": 1, "sha256": "c" * 64},
        **change,
    }
    result.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(preflight_module, "sha256_file", lambda _path: "b" * 64)
    for name in ("audit_manifest", "audit_archive", "audit_evidence"):
        monkeypatch.setattr(preflight_module, name, lambda *_args: {"status": "pass", "issues": []})
    report = build_preflight_report(REPO_ROOT, candidate, tmp_path, result)
    if blocker:
        assert blocker in report["blockers"]
        assert report["final_readiness_state"] == "BLOCKED"
    else:
        assert not report["blockers"]
        assert report["final_readiness_state"] == "READY_FOR_PARTNER_CENTER_UPLOAD"


@pytest.mark.parametrize("payload", ["not-json", "[]", "null"])
def test_unreadable_wack_result_fails_closed(tmp_path, payload):
    result = tmp_path / "wack-result.json"
    result.write_text(payload, encoding="utf-8")
    parsed = preflight_module._parse_wack_result(result, candidate_msix_path=tmp_path / "candidate.msix")
    assert parsed["status"] == "blocked"
    assert parsed["validation_issues"] == ["result_unreadable"]


def _archive_fixture(tmp_path, extra=()):
    candidate = tmp_path / "synthetic.msix"
    with zipfile.ZipFile(candidate, "w") as archive:
        for name in sorted(preflight_module.REQUIRED_TOP_LEVEL_FILES):
            archive.writestr(name, "synthetic-structure-only")
        archive.writestr("LICENSE", "fictional")
        for name in extra:
            archive.writestr(name, "fictional")
    return candidate


def test_unsigned_store_archive_does_not_require_private_signing_certificate(tmp_path, monkeypatch):
    def unexpected_tool(_name):
        raise AssertionError("Unsigned Store submission must not invoke signtool")

    monkeypatch.setattr(preflight_module, "_find_sdk_tool", unexpected_tool)
    report = preflight_module.audit_archive(_archive_fixture(tmp_path))
    assert report["status"] == "pass"
    assert report["signature_state"] == "unsigned_store_signing_pending"
    assert report["signing_scope"] == "microsoft_store_submission_not_sideload_installation"


@pytest.mark.parametrize("outcome", ["unavailable", "invalid", "untrusted", "valid"])
def test_present_signature_requires_successful_verification(tmp_path, monkeypatch, outcome):
    monkeypatch.setattr(
        preflight_module, "_find_sdk_tool",
        lambda _name: None if outcome == "unavailable" else "fictional-signtool",
    )
    monkeypatch.setattr(
        preflight_module.subprocess, "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args, 0 if outcome == "valid" else 1,
            "not trusted" if outcome == "untrusted" else "", "",
        ),
    )
    report = preflight_module.audit_archive(_archive_fixture(tmp_path, ["AppxSignature.p7x"]))
    assert report["status"] == ("pass" if outcome == "valid" else "fail")


@pytest.mark.parametrize("entry", ["/outside.txt", "\\outside.txt", "../outside.txt", "C:/outside.txt"])
def test_archive_checks_original_path_before_normalization(tmp_path, entry):
    report = preflight_module.audit_archive(_archive_fixture(tmp_path, [entry]))
    assert report["status"] == "fail"
    assert "path_traversal_or_ads" in report["issues"]
