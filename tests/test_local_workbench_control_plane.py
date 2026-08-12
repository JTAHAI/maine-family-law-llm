from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from legal.local_workbench import LocalWorkbenchError, LocalWorkbenchService
from maine_family_law_llm import api as api_module


def test_local_workbench_control_plane_is_encrypted_reviewable_and_local(tmp_path):
    service = LocalWorkbenchService(tmp_path, encryption_key="test-local-workbench-key")

    readiness = service.readiness()
    assert readiness["cpu_baseline_supported"] is True
    assert readiness["network_used"] is False
    assert readiness["recommended_mode"]

    model = service.register_model(
        {
            "model_id": "compact_local",
            "display_name": "Compact local model",
            "role": "assistant",
            "version": "1.0",
            "artifact_sha256": "a" * 64,
            "min_ram_bytes": 0,
            "context_limit_tokens": 4096,
        }
    )
    assert model["privacy_status"] == "local_only"
    assert model["receipt"]["event_hash"]

    route = service.route_model({"task": "summarize local evidence"})
    assert route["selected_model"]["model_id"] == "compact_local"
    assert route["network_used"] is False

    plan = service.propose_plan(
        {
            "plan_id": "review_packet_plan",
            "title": "Prepare a review packet",
            "actions": [
                {
                    "action_id": "stage_extract",
                    "operation": "extract",
                    "summary": "Extract text for review.",
                    "permissions": ["write_workspace"],
                    "reversible": True,
                }
            ],
        }
    )
    assert plan["status"] == "proposed"
    approved = service.approve_plan("review_packet_plan")
    assert approved["status"] == "approved"
    assert approved["execution_not_automatic"] is True

    preferences = service.set_preferences({"motion": "reduced", "screen_reader_mode": True})
    assert preferences["preferences"]["motion"] == "reduced"
    assert preferences["preferences"]["screen_reader_mode"] is True

    privacy = service.set_privacy({"network_mode": "local_only", "telemetry": "off"})
    assert privacy["privacy"]["network_mode"] == "local_only"
    assert privacy["network_used"] is False

    automation = service.create_automation(
        {
            "automation_id": "packet_routine",
            "title": "Packet routine",
            "steps": [
                {"action": "extract", "summary": "Extract locally."},
                {"action": "prepare_packet", "summary": "Prepare a review packet."},
            ],
        }
    )
    assert automation["approval_required_every_run"] is True
    automation_plan = service.propose_automation_run("packet_routine")
    assert automation_plan["requires_confirmation"] is True
    assert len(automation_plan["actions"]) == 2

    work_item = service.create_work_item(
        {
            "work_item_id": "review_deadline",
            "title": "Review the new notice",
            "kind": "deadline",
            "priority": "high",
            "source_ids": ["notice_record"],
        }
    )
    assert work_item["status"] == "open"
    assert work_item["review_required"] is True

    first_snapshot = service.snapshot_source(
        {
            "source_id": "maine_statute",
            "label": "Maine statute",
            "version": "2026.1",
            "content_sha256": "d" * 64,
        }
    )
    assert first_snapshot["changed_since_prior"] is False
    changed_snapshot = service.snapshot_source(
        {
            "source_id": "maine_statute",
            "label": "Maine statute",
            "version": "2026.2",
            "content_sha256": "e" * 64,
        }
    )
    assert changed_snapshot["changed_since_prior"] is True

    connector = service.register_connector(
        {"connector_id": "calendar_review", "kind": "calendar", "label": "Review calendar"}
    )
    assert connector["enabled"] is False
    assert connector["network_access"] == "not_granted"

    template = service.register_template(
        {
            "template_id": "review_template",
            "title": "Review template",
            "steps": ["Inspect sources", "Prepare review packet"],
        }
    )
    assert template["status"] == "local_reviewed_template"

    handoff = service.prepare_handoff(
        {
            "handoff_id": "review_handoff",
            "recipient_label": "Local reviewer",
            "recipient_role": "reviewer",
            "scope_summary": "Redacted review packet only.",
        }
    )
    assert handoff["status"] == "prepared_not_transmitted"
    assert handoff["delivery_requires_confirmation"] is True

    extension = service.register_extension(
        {
            "extension_id": "review_helper",
            "name": "Review helper",
            "permissions": ["read_local_files"],
            "manifest_sha256": "b" * 64,
        }
    )
    assert extension["status"] == "review_pending"
    assert extension["execution_enabled"] is False

    evaluation = service.record_evaluation(
        {
            "evaluation_id": "retrieval_eval",
            "subject_id": "compact_local",
            "kind": "retrieval",
            "metrics": {"precision": 0.8, "latency_ms": 120.0},
            "sample_count": 25,
        }
    )
    assert evaluation["metrics"]["precision"] == 0.8

    status = service.status()
    assert status["model_count"] == 1
    assert status["automation_count"] == 1
    assert status["extension_count"] == 1
    assert status["open_work_item_count"] == 1
    assert status["connector_count"] == 1
    assert status["template_count"] == 1
    assert status["handoff_count"] == 1
    assert status["evaluation_count"] == 1
    assert status["plan_counts"]["approved"] == 1
    assert status["local_only_by_default"] is True
    assert status["network_used"] is False
    assert (tmp_path / "90_LOCAL_WORKBENCH" / "state.json.enc").is_file()
    assert not (tmp_path / "90_LOCAL_WORKBENCH" / "state.json").exists()
    manifest = service.portable_manifest()
    assert manifest["contains_private_content"] is False
    assert manifest["export_not_created"] is True
    assert manifest["counts"]["work_items"] == 1


def test_local_workbench_rejects_unsafe_unapproved_extension_permissions(tmp_path):
    service = LocalWorkbenchService(tmp_path, encryption_key="test-local-workbench-key")
    with pytest.raises(LocalWorkbenchError, match="extension_permission_invalid"):
        service.register_extension(
            {
                "extension_id": "unsafe_extension",
                "permissions": ["network"],
            }
        )


def test_local_workbench_ga_slices_verify_artifacts_govern_performance_and_fail_closed(
    tmp_path, monkeypatch
):
    artifact_root = tmp_path / "model_artifacts"
    artifact_root.mkdir()
    artifact = artifact_root / "compact.gguf"
    artifact.write_bytes(b"trusted-local-artifact")
    artifact_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()
    monkeypatch.setenv("MFL_MODEL_ARTIFACT_ROOT", str(artifact_root))
    service = LocalWorkbenchService(
        tmp_path / "workspace", encryption_key="test-local-workbench-key"
    )
    service.register_model(
        {
            "model_id": "ga_compact",
            "artifact_sha256": artifact_hash,
            "min_ram_bytes": 0,
        }
    )

    admission = service.admit_local_artifact(
        {"model_id": "ga_compact", "filename": "compact.gguf", "expected_sha256": artifact_hash}
    )
    assert admission["status"] == "verified_local_artifact_review_required"
    assert admission["network_used"] is False

    policy = service.configure_performance_policy(
        {
            "mode": "battery_saver",
            "max_concurrent_jobs": 1,
            "max_context_tokens": 512,
            "memory_budget_ratio": 0.3,
        }
    )
    assert policy["policy"]["mode"] == "battery_saver"
    preflight = service.preflight_local_job(
        {"task": "summarize", "context_tokens": 1024, "estimated_memory_bytes": 0}
    )
    assert preflight["status"] == "queue_or_reduce_required"
    assert "requested_context_exceeds_policy" in preflight["blockers"]

    changes = service.route_source_change(
        {
            "changes": [
                {"source_id": "maine_statute", "change_type": "content_hash_changed"},
                {"source_id": "maine_form", "change_type": "metadata_changed"},
            ]
        }
    )
    assert len(changes["created_work_items"]) == 2
    assert changes["review_required"] is True

    blocked = service.release_readiness()
    assert blocked["status"] == "blocked"
    assert blocked["automatic_ga_release_authorized"] is False
    evidence = service.record_release_evidence(
        {
            "evidence_id": "backup_evidence",
            "control": "backup_restore",
            "status": "pass",
            "sha256": "f" * 64,
            "summary": "Verified isolated restore drill.",
        }
    )
    assert evidence["control"] == "backup_restore"
    assert "release_control_not_passed:security" in service.release_readiness()["blockers"]


def test_local_workbench_ga_mode_refuses_development_encryption_key(tmp_path, monkeypatch):
    monkeypatch.setenv("MFL_GA_HARDENING", "1")
    monkeypatch.delenv("MAINE_MATTER_STORE_KEY", raising=False)
    with pytest.raises(LocalWorkbenchError, match="control_plane_production_key_required"):
        LocalWorkbenchService(tmp_path)


def test_local_workbench_control_plane_api_is_local_and_reviewable(monkeypatch, tmp_path):
    case = tmp_path / "case"
    case.mkdir()
    monkeypatch.setattr(api_module, "active_case_root", lambda: case)
    client = TestClient(api_module.app)

    status = client.get("/api/local-workbench/status")
    assert status.status_code == 200
    assert status.json()["local_only_by_default"] is True
    assert status.json()["network_used"] is False

    model = client.post(
        "/api/local-workbench/models",
        json={
            "model_id": "api_compact",
            "display_name": "API compact",
            "artifact_sha256": "c" * 64,
        },
    )
    assert model.status_code == 200
    assert model.json()["privacy_status"] == "local_only"

    plan = client.post(
        "/api/local-workbench/plans",
        json={
            "plan_id": "api_review_plan",
            "title": "API review plan",
            "actions": [
                {
                    "action_id": "api_extract",
                    "operation": "extract",
                    "summary": "Extract locally.",
                    "permissions": ["write_workspace"],
                }
            ],
        },
    )
    assert plan.status_code == 200
    approval = client.post("/api/local-workbench/plans/api_review_plan/approve")
    assert approval.status_code == 200
    assert approval.json()["execution_not_automatic"] is True

    preferences = client.put(
        "/api/local-workbench/preferences",
        json={"preferences": {"motion": "reduced", "screen_reader_mode": True}},
    )
    assert preferences.status_code == 200
    assert preferences.json()["preferences"]["motion"] == "reduced"

    work_item = client.post(
        "/api/local-workbench/work-items",
        json={
            "work_item_id": "api_review_item",
            "title": "Review local output",
            "kind": "review",
            "priority": "normal",
        },
    )
    assert work_item.status_code == 200
    manifest = client.get("/api/local-workbench/portable-manifest")
    assert manifest.status_code == 200
    assert manifest.json()["export_not_created"] is True

    performance = client.put(
        "/api/local-workbench/performance-policy",
        json={"mode": "battery_saver", "max_concurrent_jobs": 1, "max_context_tokens": 512},
    )
    assert performance.status_code == 200
    preflight = client.post(
        "/api/local-workbench/jobs/preflight",
        json={"task": "local summary", "context_tokens": 1024},
    )
    assert preflight.status_code == 200
    assert preflight.json()["status"] == "queue_or_reduce_required"

    routed = client.post(
        "/api/local-workbench/source-changes/route",
        json={"changes": [{"source_id": "api_statute", "change_type": "content_hash_changed"}]},
    )
    assert routed.status_code == 200
    assert len(routed.json()["created_work_items"]) == 1
    readiness = client.get("/api/local-workbench/release-readiness")
    assert readiness.status_code == 200
    assert readiness.json()["status"] == "blocked"
    backup = client.get("/api/local-workbench/backup-restore/status")
    assert backup.status_code == 200
    assert backup.json()["status"] == "blocked"


def test_local_workbench_control_center_ui_is_present_and_mirrored():
    source_root = Path("src/maine_family_law_llm/ui")
    mirror_root = Path("maine_family_law_llm/ui")
    html = (source_root / "workbench.html").read_text(encoding="utf-8")
    script = (source_root / "workbench.js").read_text(encoding="utf-8")
    styles = (source_root / "workbench.css").read_text(encoding="utf-8")

    assert 'id="local-workbench-overlay"' in html
    assert 'id="local-workbench-button"' in html
    assert 'id="quick-local-workbench"' in html
    assert 'id="local-workbench-release-readiness"' in html
    assert "/api/local-workbench/status" in script
    assert "/api/local-workbench/release-readiness" in script
    assert "closeLocalWorkbench" in script
    assert ".local-workbench-card h3" in styles
    for filename in ("workbench.html", "workbench.js", "workbench.css"):
        assert (source_root / filename).read_bytes() == (mirror_root / filename).read_bytes()
