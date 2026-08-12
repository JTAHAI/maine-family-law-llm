from __future__ import annotations

import json
from pathlib import Path

import pytest

from maine_family_law_llm.store_preflight import DEFAULT_EVIDENCE_ROOT, DEFAULT_MSIX_PATH, build_preflight_report, main


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def preflight_report() -> dict[str, object]:
    return build_preflight_report(
        REPO_ROOT,
        DEFAULT_MSIX_PATH,
        DEFAULT_EVIDENCE_ROOT,
        DEFAULT_EVIDENCE_ROOT / "wack" / "wack-result.json",
    )


def test_store_preflight_report_marks_current_release_blocked_only_by_wack(preflight_report: dict[str, object]) -> None:
    assert preflight_report["manifest_audit"]["status"] == "pass"
    assert preflight_report["content_audit"]["status"] == "pass"
    assert preflight_report["evidence_audit"]["status"] == "pass"
    assert preflight_report["wack"]["status"] == "not_run"
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
            str(DEFAULT_EVIDENCE_ROOT / "wack" / "wack-result.json"),
            "--output-json",
            str(json_path),
            "--output-txt",
            str(txt_path),
        ]
    )
    assert exit_code == 0
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["final_readiness_state"] == "BLOCKED"
    assert payload["wack"]["status"] == "not_run"
    assert "WACK: not_run" in txt_path.read_text(encoding="utf-8")
    assert payload["package"]["sha256"] == preflight_report["package"]["sha256"]
