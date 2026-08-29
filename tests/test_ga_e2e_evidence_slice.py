from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "dist" / "ga_today" / "evidence"
MANIFEST = (
    ROOT
    / "dist"
    / "ga_today"
    / "e2e_runtime"
    / "fictional_ga_matter_20260811"
    / "fictional_ga_matter_manifest.json"
)


def require_archived_evidence(path: Path) -> Path:
    if not path.is_file():
        pytest.skip(
            "Archived GA end-to-end evidence is unavailable in this checkout; "
            "current release qualification remains blocked until it is recreated."
        )
    return path


def test_fictional_ga_fixture_is_deterministic_and_non_private() -> None:
    payload = json.loads(require_archived_evidence(MANIFEST).read_text(encoding="utf-8"))
    records = {row["filename"]: row for row in payload["records"]}

    assert payload["fictional"] is True
    assert payload["private_or_real_data"] is False
    assert payload["record_count"] == 14
    assert records["06_discovery_request.docx"]["sha256"] == records[
        "07_discovery_request_exact_duplicate.docx"
    ]["sha256"]
    assert records["08_discovery_request_changed_copy.docx"]["sha256"] != records[
        "06_discovery_request.docx"
    ]["sha256"]

    fixture_inputs = MANIFEST.parent / "inputs"
    for row in payload["records"]:
        source = fixture_inputs / row["filename"]
        assert source.is_file()
        assert hashlib.sha256(source.read_bytes()).hexdigest() == row["sha256"]


def test_ga_e2e_matrix_has_all_journeys_and_fail_closed_results() -> None:
    matrix = json.loads(require_archived_evidence(EVIDENCE / "03_e2e_feature_matrix.json").read_text(encoding="utf-8"))
    required = {
        "action",
        "expected_result",
        "actual_result",
        "api_routes",
        "ui_state",
        "source_or_artifact_ids",
        "duration_ms",
        "screenshot_or_dom_evidence",
        "pass",
        "failure_artifact",
    }

    assert matrix["decision"] == "BLOCKED"
    assert matrix["fictional_matter"]["private_or_real_data"] is False
    assert matrix["journey_summary"] == {"total": 22, "passed": 7, "failed": 15}
    assert [row["journey"] for row in matrix["journeys"]] == list(range(1, 23))
    for row in matrix["journeys"]:
        assert required <= row.keys()
        assert row["actual_result"]
        if not row["pass"]:
            assert row["failure_artifact"]


def test_ga_e2e_png_and_artifact_hash_evidence_is_valid() -> None:
    matrix = json.loads(require_archived_evidence(EVIDENCE / "03_e2e_feature_matrix.json").read_text(encoding="utf-8"))
    assert matrix["screenshots"]
    for shot in matrix["screenshots"]:
        path = ROOT / shot["path"]
        assert path.is_file()
        assert shot["png_valid"] is True
        assert shot["width"] > 0 and shot["height"] > 0
        assert hashlib.sha256(path.read_bytes()).hexdigest() == shot["sha256"]
    for artifact in matrix["artifact_hashes"]:
        path = Path(artifact["path"])
        if not path.is_absolute():
            path = ROOT / path
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"]
