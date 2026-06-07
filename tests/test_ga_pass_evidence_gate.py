from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from legal.production.ga_pass_evidence import GAPassEvidenceAuditor

ROOT = Path(__file__).resolve().parents[1]




def _manifest_record(store: Path, *, source_id: str = "official-fixture") -> dict:
    body = f"official authority bytes for {source_id}".encode("utf-8")
    snapshot = store / f"{source_id}.html"
    snapshot.write_bytes(body)
    return {
        "source_id": source_id,
        "source_class": "statute_title_index",
        "jurisdiction": "maine",
        "retrieved_at": "2026-05-30T00:00:00+00:00",
        "hash": hashlib.sha256(body).hexdigest(),
        "parser_status": "parsed",
        "freshness_status": "known_extracted_timestamp",
        "data_class": "official_public_authority",
        "source_url_or_path": f"https://example.maine.gov/{source_id}",
        "snapshot_path": str(snapshot),
        "parser_audit": {"status": "parsed", "parser_version": "test"},
    }




def _authority_audit_payload(store: Path, *, status: str = "pass") -> dict:
    return {
        "status": status,
        "production_ready": True,
        "readiness": "authority_build_ready",
        "manifest_path": str(store / "source_manifest.json"),
        "total_records": 1,
        "blockers": [],
    }

def _write_tracker(path: Path, completed: list[int]) -> None:
    source = json.loads((ROOT / "configs" / "maine_true_ga_pass_tracker.json").read_text(encoding="utf-8"))
    source["current_true_ga_completed_passes"] = completed
    remaining = [int(row["pass"]) for row in source["passes"] if int(row["pass"]) not in completed]
    next_pass = min(remaining) if remaining else None
    for row in source["passes"]:
        pass_number = int(row["pass"])
        row["status"] = "complete" if pass_number in completed else "open"
        row["next"] = pass_number == next_pass
    path.write_text(json.dumps(source), encoding="utf-8")


def _write_pass19_external_requirements(path: Path) -> None:
    payload = {
        "counting_rule": "test external Pass 19 evidence requirements",
        "passes": [
            {
                "pass": 19,
                "required_artifacts": [
                    {
                        "root": "data",
                        "glob": "official_authority_store/source_manifest.json",
                    },
                    {
                        "root": "data",
                        "glob": "official_authority_store/authority_build_audit.json",
                        "status_values": ["pass"],
                    },
                ],
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_pass26_external_requirements(path: Path) -> None:
    payload = {
        "counting_rule": "test external Pass 26 evidence requirements",
        "passes": [
            {
                "pass": 26,
                "required_artifacts": [
                    {"root": "data", "glob": "eval_store/gold_annotation_queue.jsonl"},
                    {
                        "root": "data",
                        "glob": "eval_store/gold_annotation_queue_audit.json",
                        "status_values": ["pass"],
                    },
                ],
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_default_ga_pass_evidence_audit_accepts_completed_repo_evidence_passes() -> None:
    report = GAPassEvidenceAuditor(project_root=ROOT).run().as_dict()
    assert report["status"] == "pass"
    assert report["true_ga_completed_claimed"] == list(range(19, 48))
    assert report["true_ga_remaining"] == 4
    assert report["audited_completed_passes"] == list(range(19, 48))


def test_completed_true_ga_pass_without_real_external_evidence_is_blocked(tmp_path: Path) -> None:
    tracker = tmp_path / "tracker.json"
    _write_tracker(tracker, [19])
    data_root = tmp_path / "external_data"
    data_root.mkdir()
    requirements = tmp_path / "requirements.json"
    _write_pass19_external_requirements(requirements)
    report = GAPassEvidenceAuditor(
        project_root=ROOT,
        data_root=data_root,
        tracker_path=tracker,
        requirements_path=requirements,
    ).run().as_dict()
    assert report["status"] == "blocked"
    assert report["audited_completed_passes"] == []
    assert any("pass_19:missing_artifact" in blocker for blocker in report["blockers"])


def test_completed_pass19_with_required_external_evidence_passes(tmp_path: Path) -> None:
    tracker = tmp_path / "tracker.json"
    _write_tracker(tracker, [19])
    data_root = tmp_path / "external_data"
    store = data_root / "official_authority_store"
    store.mkdir(parents=True)
    (store / "source_manifest.json").write_text(json.dumps([_manifest_record(store)]), encoding="utf-8")
    (store / "authority_build_audit.json").write_text(json.dumps(_authority_audit_payload(store)), encoding="utf-8")
    requirements = tmp_path / "requirements.json"
    _write_pass19_external_requirements(requirements)
    report = GAPassEvidenceAuditor(
        project_root=ROOT,
        data_root=data_root,
        tracker_path=tracker,
        requirements_path=requirements,
    ).run().as_dict()
    assert report["status"] == "pass"
    assert report["audited_completed_passes"] == [19]
    assert report["blockers"] == []




def test_completed_pass19_rejects_skeletal_authority_audit_status_only(tmp_path: Path) -> None:
    tracker = tmp_path / "tracker.json"
    _write_tracker(tracker, [19])
    data_root = tmp_path / "external_data"
    store = data_root / "official_authority_store"
    store.mkdir(parents=True)
    (store / "source_manifest.json").write_text(json.dumps([_manifest_record(store)]), encoding="utf-8")
    (store / "authority_build_audit.json").write_text(json.dumps({"status": "pass"}), encoding="utf-8")
    requirements = tmp_path / "requirements.json"
    _write_pass19_external_requirements(requirements)
    report = GAPassEvidenceAuditor(
        project_root=ROOT,
        data_root=data_root,
        tracker_path=tracker,
        requirements_path=requirements,
    ).run().as_dict()
    assert report["status"] == "blocked"
    assert any("authority_build_audit_not_production_ready" in blocker for blocker in report["blockers"])


def test_completed_pass19_rejects_blocked_authority_audit_even_with_status_pass(tmp_path: Path) -> None:
    tracker = tmp_path / "tracker.json"
    _write_tracker(tracker, [19])
    data_root = tmp_path / "external_data"
    store = data_root / "official_authority_store"
    store.mkdir(parents=True)
    (store / "source_manifest.json").write_text(json.dumps([_manifest_record(store)]), encoding="utf-8")
    (store / "authority_build_audit.json").write_text(
        json.dumps(
            {
                "status": "pass",
                "production_ready": False,
                "readiness": "authority_build_blocked_until_external_official_snapshots_are_ingested",
                "blockers": ["source_class_minimum_not_met"],
            }
        ),
        encoding="utf-8",
    )
    requirements = tmp_path / "requirements.json"
    _write_pass19_external_requirements(requirements)
    report = GAPassEvidenceAuditor(
        project_root=ROOT,
        data_root=data_root,
        tracker_path=tracker,
        requirements_path=requirements,
    ).run().as_dict()
    assert report["status"] == "blocked"
    assert any("json_report_has_blockers" in blocker for blocker in report["blockers"])

def test_completed_pass19_rejects_failed_audit_json(tmp_path: Path) -> None:
    tracker = tmp_path / "tracker.json"
    _write_tracker(tracker, [19])
    data_root = tmp_path / "external_data"
    store = data_root / "official_authority_store"
    store.mkdir(parents=True)
    (store / "source_manifest.json").write_text(json.dumps([_manifest_record(store)]), encoding="utf-8")
    (store / "authority_build_audit.json").write_text(json.dumps({"status": "blocked"}), encoding="utf-8")
    requirements = tmp_path / "requirements.json"
    _write_pass19_external_requirements(requirements)
    report = GAPassEvidenceAuditor(
        project_root=ROOT,
        data_root=data_root,
        tracker_path=tracker,
        requirements_path=requirements,
    ).run().as_dict()
    assert report["status"] == "blocked"
    assert any("authority_build_audit_not_production_ready" in blocker for blocker in report["blockers"])


def test_completed_pass19_rejects_minimal_placeholder_manifest_record(tmp_path: Path) -> None:
    tracker = tmp_path / "tracker.json"
    _write_tracker(tracker, [19])
    data_root = tmp_path / "external_data"
    store = data_root / "official_authority_store"
    store.mkdir(parents=True)
    (store / "source_manifest.json").write_text(json.dumps([{"source_id": "official-fixture"}]), encoding="utf-8")
    (store / "authority_build_audit.json").write_text(json.dumps({"status": "pass"}), encoding="utf-8")
    requirements = tmp_path / "requirements.json"
    _write_pass19_external_requirements(requirements)
    report = GAPassEvidenceAuditor(
        project_root=ROOT,
        data_root=data_root,
        tracker_path=tracker,
        requirements_path=requirements,
    ).run().as_dict()
    assert report["status"] == "blocked"
    assert any("source_manifest_record_missing" in blocker for blocker in report["blockers"])


def test_completed_pass19_rejects_manifest_with_missing_snapshot(tmp_path: Path) -> None:
    tracker = tmp_path / "tracker.json"
    _write_tracker(tracker, [19])
    data_root = tmp_path / "external_data"
    store = data_root / "official_authority_store"
    store.mkdir(parents=True)
    record = _manifest_record(store)
    Path(record["snapshot_path"]).unlink()
    (store / "source_manifest.json").write_text(json.dumps([record]), encoding="utf-8")
    (store / "authority_build_audit.json").write_text(json.dumps({"status": "pass"}), encoding="utf-8")
    requirements = tmp_path / "requirements.json"
    _write_pass19_external_requirements(requirements)
    report = GAPassEvidenceAuditor(
        project_root=ROOT,
        data_root=data_root,
        tracker_path=tracker,
        requirements_path=requirements,
    ).run().as_dict()
    assert report["status"] == "blocked"
    assert any("source_manifest_snapshot_missing" in blocker for blocker in report["blockers"])


def test_completed_pass19_rejects_placeholder_manifest_shape(tmp_path: Path) -> None:
    tracker = tmp_path / "tracker.json"
    _write_tracker(tracker, [19])
    data_root = tmp_path / "external_data"
    store = data_root / "official_authority_store"
    store.mkdir(parents=True)
    (store / "source_manifest.json").write_text(json.dumps({"sources": []}), encoding="utf-8")
    (store / "authority_build_audit.json").write_text(json.dumps({"status": "pass"}), encoding="utf-8")
    requirements = tmp_path / "requirements.json"
    _write_pass19_external_requirements(requirements)
    report = GAPassEvidenceAuditor(
        project_root=ROOT,
        data_root=data_root,
        tracker_path=tracker,
        requirements_path=requirements,
    ).run().as_dict()
    assert report["status"] == "blocked"
    assert any("source_manifest_not_array" in blocker for blocker in report["blockers"])


def test_completed_pass26_rejects_empty_generated_queue(tmp_path: Path) -> None:
    tracker = tmp_path / "tracker.json"
    _write_tracker(tracker, [26])
    data_root = tmp_path / "external_data"
    eval_store = data_root / "eval_store"
    eval_store.mkdir(parents=True)
    (eval_store / "gold_annotation_queue.jsonl").write_text("", encoding="utf-8")
    (eval_store / "gold_annotation_queue_audit.json").write_text(json.dumps({"status": "pass"}), encoding="utf-8")
    requirements = tmp_path / "requirements.json"
    _write_pass26_external_requirements(requirements)
    report = GAPassEvidenceAuditor(
        project_root=ROOT,
        data_root=data_root,
        tracker_path=tracker,
        requirements_path=requirements,
    ).run().as_dict()
    assert report["status"] == "blocked"
    assert any("empty_artifact_file" in blocker for blocker in report["blockers"])



def test_completed_pass26_rejects_skeletal_annotation_queue_audit(tmp_path: Path) -> None:
    tracker = tmp_path / "tracker.json"
    _write_tracker(tracker, [26])
    data_root = tmp_path / "external_data"
    eval_store = data_root / "eval_store"
    eval_store.mkdir(parents=True)
    row = {
        "queue_id": "q-1",
        "task_type": "maine_rag_retrieval_gold",
        "source_id": "official-fixture",
        "source_class": "statute_title_index",
        "jurisdiction": "maine",
        "review_status": "needs_attorney_review",
        "double_review_required": True,
        "conflict_status": "unreviewed",
        "promoted_gold_dataset": None,
        "private_data_allowed_for_training": False,
        "created_at": "2026-05-31T00:00:00+00:00",
        "instructions": "Attorney review required before promotion to gold.",
    }
    (eval_store / "gold_annotation_queue.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    (eval_store / "gold_annotation_queue_audit.json").write_text(
        json.dumps({"status": "pass"}),
        encoding="utf-8",
    )
    requirements = tmp_path / "requirements.json"
    _write_pass26_external_requirements(requirements)
    report = GAPassEvidenceAuditor(
        project_root=ROOT,
        data_root=data_root,
        tracker_path=tracker,
        requirements_path=requirements,
    ).run().as_dict()
    assert report["status"] == "blocked"
    assert any("gold_annotation_queue_audit_empty" in blocker for blocker in report["blockers"])


def test_ga_pass_evidence_script_outputs_json() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "audit-ga-pass-evidence.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["status"] == "pass"
    assert payload["true_ga_remaining"] == 4
    assert payload["audited_completed_passes"] == list(range(19, 48))


def test_completed_pass50_rejects_signed_report_with_blocked_status(tmp_path: Path) -> None:
    tracker = tmp_path / "tracker.json"
    _write_tracker(tracker, [50])
    pilot_root = tmp_path / "pilot_root"
    pilot_root.mkdir(parents=True)
    (pilot_root / "ga_release_candidate_signoff.json").write_text(
        json.dumps(
            {
                "status": "blocked",
                "signed": True,
                "signoffs": ["legal", "security", "product", "ops"],
                "blockers": [],
            }
        ),
        encoding="utf-8",
    )
    report = GAPassEvidenceAuditor(
        project_root=ROOT,
        pilot_root=pilot_root,
        tracker_path=tracker,
    ).run().as_dict()
    assert report["status"] == "blocked"
    assert any("artifact_status_not_accepted:pilot:ga_release_candidate_signoff.json" in blocker for blocker in report["blockers"])


def test_completed_pass50_accepts_signed_report_without_negative_status(tmp_path: Path) -> None:
    tracker = tmp_path / "tracker.json"
    _write_tracker(tracker, [50])
    pilot_root = tmp_path / "pilot_root"
    pilot_root.mkdir(parents=True)
    (pilot_root / "ga_release_candidate_signoff.json").write_text(
        json.dumps(
            {
                "status": "pass",
                "signed": True,
                "signoffs": ["legal", "security", "product", "ops"],
                "blockers": [],
            }
        ),
        encoding="utf-8",
    )
    report = GAPassEvidenceAuditor(
        project_root=ROOT,
        pilot_root=pilot_root,
        tracker_path=tracker,
    ).run().as_dict()
    assert report["status"] == "pass"
    assert report["audited_completed_passes"] == [50]

def test_completed_pass26_accepts_source_safe_queue_operations_summary() -> None:
    report = GAPassEvidenceAuditor(project_root=ROOT).run().as_dict()
    assert report["status"] == "pass"
    assert 26 in report["audited_completed_passes"]
    assert report["true_ga_remaining"] == 4
