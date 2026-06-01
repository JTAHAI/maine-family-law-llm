from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from legal.production.ga_pass_tracker import GAPassTracker

ROOT = Path(__file__).resolve().parents[1]


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def _operator_data_root(tmp_path: Path) -> Path:
    data_root = tmp_path / "ME_FM_LLM_data"
    parsed_root = data_root / "parsed_authority_store"
    authority_index = data_root / "authority_layer" / "citation_index.json"
    _write_jsonl(
        parsed_root / "statutes" / "title19a.jsonl",
        [
            {
                "source_id": "parsed-title-19a-section-1653",
                "record_id": "parsed-title-19a-section-1653",
                "source_class": "statute",
                "authority_kind": "statute_section",
                "jurisdiction": "maine",
                "citation": "19-A M.R.S. § 1653",
                "authority_status": "verified_official_maine",
                "freshness_status": "fresh",
                "text": "The court shall apply the best interest of the child standard when allocating parental rights and responsibilities in Maine family matters.",
            }
        ],
    )
    _write_jsonl(
        parsed_root / "forms" / "family_forms.jsonl",
        [
            {
                "source_id": "form-fm-001",
                "record_id": "form-fm-001",
                "source_class": "court_form",
                "jurisdiction": "maine",
                "form_id": "FM-001",
                "title": "Family Matter Summary Sheet FM-001",
                "version_date": "01/2026",
                "text": "FM-001 Family Matter Summary Sheet current official Maine Judicial Branch form.",
            }
        ],
    )
    _write_json(
        authority_index,
        [
            {
                "source_id": "authority-index-row-873",
                "kind": "maine_statute",
                "normalized_citation": "19-A M.R.S. § 1653",
                "authority_status": "verified_official_maine",
                "freshness_status": "fresh",
                "metadata": {"jurisdiction": "maine"},
            }
        ],
    )
    _write_json(
        data_root / "retrieval_smoke_report.json",
        {"status": "pass", "case_count": 3, "metrics": {"recall_at_20": 1.0}},
    )
    _write_json(data_root / "source_update_report.json", {"status": "pass"})
    return data_root


def test_pass27_31_46_operator_closure_script_passes_on_source_backed_fixture(tmp_path: Path) -> None:
    data_root = _operator_data_root(tmp_path)
    output = data_root / "pass27_31_46_operator_source_backed_closure.json"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run-pass27-31-46-operator-closure.py",
            "--data-root",
            str(data_root),
            "--limit",
            "10",
            "--output",
            str(output),
            "--require-ready",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload["status"] == "pass"
    assert payload["passes_closed_when_ready"] == [27, 28, 29, 30, 31, 46]
    assert payload["review_mode"] == "operator_source_backed"
    assert payload["attorney_reviewed"] is False
    assert payload["legal_signoff"] is False
    assert payload["pilot_signoff"] is False
    assert payload["operator_release_allowed"] is True
    assert payload["true_ga_release_allowed"] is False

    pass46 = json.loads((data_root / "pass46_operator_source_backed_release_eval.json").read_text())
    assert pass46["status"] == "pass"
    assert pass46["operator_release_allowed"] is True
    assert pass46["true_ga_release_allowed"] is False


def test_tracker_now_counts_operator_source_backed_closure_and_leaves_launch_only() -> None:
    report = GAPassTracker(project_root=ROOT).report().as_dict()

    assert report["status"] == "pass"
    assert report["true_ga_completed"] == 29
    assert report["true_ga_remaining"] == 4
    for pass_number in [27, 28, 29, 30, 31, 46]:
        assert pass_number in report["completed_passes"]
    assert report["remaining_passes"] == [48, 49, 50, 51]
    assert report["next_true_ga_pass"] == 48
