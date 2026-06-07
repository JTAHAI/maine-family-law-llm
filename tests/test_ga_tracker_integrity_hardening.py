from __future__ import annotations

import json
from pathlib import Path

from legal.production.ga_pass_evidence import GAPassEvidenceAuditor
from legal.production.ga_pass_tracker import GAPassTracker

ROOT = Path(__file__).resolve().parents[1]


def _tracker_payload() -> dict:
    return json.loads((ROOT / "configs" / "maine_true_ga_pass_tracker.json").read_text(encoding="utf-8"))


def _write_tracker(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _report_for(path: Path) -> dict:
    tracker = GAPassTracker(project_root=ROOT)
    tracker.tracker_path = path
    return tracker.report().as_dict()


def test_default_true_ga_tracker_has_no_integrity_warnings() -> None:
    report = GAPassTracker(project_root=ROOT).report().as_dict()
    assert report["status"] == "pass"
    assert report["warnings"] == []


def test_tracker_blocks_when_completed_list_and_row_status_disagree(tmp_path: Path) -> None:
    payload = _tracker_payload()
    payload["current_true_ga_completed_passes"] = [39, 40, 41, 42, 43, 44, 45, 46]
    for row in payload["passes"]:
        if row["pass"] == 46:
            row["status"] = "open"
    tracker_path = tmp_path / "tracker.json"
    _write_tracker(tracker_path, payload)

    report = _report_for(tracker_path)
    assert report["status"] == "blocked"
    assert any("completed_passes_status_mismatch" in warning for warning in report["warnings"])


def test_tracker_blocks_when_row_is_complete_but_completion_list_not_updated(tmp_path: Path) -> None:
    payload = _tracker_payload()
    for row in payload["passes"]:
        if row["pass"] == 48:
            row["status"] = "complete"
    tracker_path = tmp_path / "tracker.json"
    _write_tracker(tracker_path, payload)

    report = _report_for(tracker_path)
    assert report["status"] == "blocked"
    assert 48 in report["completed_passes"]
    assert any("completed_passes_status_mismatch" in warning for warning in report["warnings"])


def test_tracker_blocks_wrong_next_pass_marker(tmp_path: Path) -> None:
    payload = _tracker_payload()
    for row in payload["passes"]:
        row["next"] = row["pass"] == 20
    tracker_path = tmp_path / "tracker.json"
    _write_tracker(tracker_path, payload)

    report = _report_for(tracker_path)
    assert report["status"] == "blocked"
    assert any("next_pass_marker_mismatch" in warning for warning in report["warnings"])


def test_ga_evidence_audit_refuses_to_count_with_blocked_tracker(tmp_path: Path) -> None:
    payload = _tracker_payload()
    payload["current_true_ga_completed_passes"] = [39, 40, 41, 42, 43, 44, 45, 46]
    for row in payload["passes"]:
        if row["pass"] == 46:
            row["status"] = "open"
    tracker_path = tmp_path / "tracker.json"
    _write_tracker(tracker_path, payload)

    report = GAPassEvidenceAuditor(project_root=ROOT, tracker_path=tracker_path).run().as_dict()
    assert report["status"] == "blocked"
    assert report["audited_completed_passes"] == []
    assert "tracker_report_not_pass" in report["blockers"]
    assert any("tracker_warning:completed_passes_status_mismatch" in blocker for blocker in report["blockers"])
