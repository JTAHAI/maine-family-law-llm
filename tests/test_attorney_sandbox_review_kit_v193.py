from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from legal.pilot import LaunchEvidenceGate, write_attorney_sandbox_review_kit
from maine_family_law_llm.chat_library import get_chat_library

ROOT = Path(__file__).resolve().parents[1]


def test_attorney_sandbox_review_kit_builds_fail_closed_public_queue(tmp_path):
    manifest = write_attorney_sandbox_review_kit(tmp_path / "kit", max_questions=12)

    assert manifest["status"] == "blocked_templates_created"
    assert manifest["pass"] == 48
    assert manifest["real_matter_allowed"] is False
    assert manifest["private_data_allowed"] is False
    assert manifest["question_count"] == 12
    assert (tmp_path / "kit" / "pilot" / "review_question_queue.json").exists()
    assert (tmp_path / "kit" / "pilot" / "attorney_sandbox_pilot_report.json").exists()

    queue = json.loads((tmp_path / "kit" / "pilot" / "review_question_queue.json").read_text())
    assert queue["status"] == "needs_attorney_review"
    assert queue["real_matter_allowed"] is False
    assert queue["private_data_allowed"] is False
    assert queue["question_count"] == 12
    assert all(row["review_status"] == "needs_attorney_review" for row in queue["questions"])
    assert all(row["private_data_included"] is False for row in queue["questions"])
    assert {"parental_rights", "safety_pfa"}.issubset({row["topic"] for row in queue["questions"]})


def test_attorney_sandbox_review_kit_defaults_do_not_close_launch_gate(tmp_path):
    write_attorney_sandbox_review_kit(tmp_path / "kit", max_questions=8)
    report = LaunchEvidenceGate().audit(
        pilot_root=tmp_path / "kit" / "pilot",
        release_root=tmp_path / "missing_release",
    ).as_dict()

    assert report["status"] == "blocked"
    assert 48 in report["open_passes"]
    assert 49 in report["open_passes"]
    assert "pass48_artifact_status_not_ready:attorney_sandbox_pilot_report.json:blocked" in report["blockers"]
    assert report["closed_passes"] == []


def test_attorney_sandbox_review_kit_cli_writes_manifest(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "scripts/build-attorney-sandbox-review-kit.py",
            "--output-root",
            str(tmp_path / "kit"),
            "--max-questions",
            "10",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked_templates_created"
    assert payload["question_count"] == 10
    assert (tmp_path / "kit" / "manifest.json").exists()


def test_attorney_sandbox_review_queue_covers_public_library_topics_without_private_inputs(tmp_path):
    manifest = write_attorney_sandbox_review_kit(tmp_path / "kit", max_questions=48)
    queue = json.loads((tmp_path / "kit" / "pilot" / "review_question_queue.json").read_text())
    library_topics = {item.topic for item in get_chat_library()}
    queued_topics = {row["topic"] for row in queue["questions"]}

    assert queued_topics.issubset(library_topics)
    assert len(queued_topics) >= 10
    assert manifest["forbidden_private_data_markers"] == [
        "party_names",
        "docket_numbers",
        "private_matter_facts",
        "uploaded_documents",
        "sealed_records",
        "juvenile_records",
        "client_confidential_material",
    ]
    serialized = json.dumps(queue).lower()
    assert "needs_attorney_review" in serialized
    assert "real_matter_allowed\": true" not in serialized
    assert "private_data_allowed\": true" not in serialized
