from __future__ import annotations

import json
from pathlib import Path

import pytest
from maine_family_law_llm import store_preflight as preflight_module

from maine_family_law_llm.store_preflight import (
    DEFAULT_EVIDENCE_ROOT,
    DEFAULT_MSIX_PATH,
    DEFAULT_WACK_RESULT,
    build_preflight_report,
    main,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def preflight_report() -> dict[str, object]:
    return build_preflight_report(
        REPO_ROOT,
        DEFAULT_MSIX_PATH,
        DEFAULT_EVIDENCE_ROOT,
        DEFAULT_WACK_RESULT,
    )


def test_store_preflight_report_fail_closes_on_missing_qualification_evidence_and_wack(preflight_report: dict[str, object]) -> None:
    assert preflight_report["manifest_audit"]["status"] == "pass"
    # This is the retained candidate, not a newly qualified Store artifact.  It
    # must remain blocked when archive/signature proof is absent or fails.
    assert preflight_report["content_audit"]["status"] == "fail"
    assert preflight_report["content_audit"]["issues"]
    assert preflight_report["evidence_audit"]["status"] == "fail"
    assert "missing_installed_offline_qualification" in preflight_report["evidence_audit"]["issues"]
    assert preflight_report["wack"]["status"] == "blocked"
    assert preflight_report["final_readiness_state"] == "BLOCKED"
    assert len(str(preflight_report["package"]["sha256"])) == 64
    assert preflight_report["package"]["path"] == str(DEFAULT_MSIX_PATH.resolve())


def test_store_preflight_cli_writes_expected_evidence(tmp_path, preflight_report: dict[str, object]) -> None:
    json_path = tmp_path / "store-preflight.json"
    txt_path = tmp_path / "store-preflight.txt"
    exit_code = main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--msix-path",
            str(DEFAULT_MSIX_PATH),
            "--evidence-root",
            str(DEFAULT_EVIDENCE_ROOT),
            "--wack-result",
            str(DEFAULT_WACK_RESULT),
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
