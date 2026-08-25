from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from app.api.main import app as enterprise_app
from app.api.production import ACCEPTED_FEATURE_IDS, app as production_app
from legal.addons import ADDON_IDS, AddonStudioError, AddonStudioStore
from maine_family_law_llm import api as api_module
from maine_family_law_llm.local_workbench_ui import read_workbench_asset
from maine_family_law_llm.production_ui import production_ui_manifest


HEADERS = {"X-User-Role": "reviewer", "X-Tenant-Id": "tenant-addon-e2e"}
HASH_A = hashlib.sha256(b"fictional-record-a").hexdigest()


@pytest.fixture()
def matter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    root = tmp_path / "fictional-addon-matter"
    root.mkdir()
    (root / "hearing.wav").write_bytes(b"RIFF-FICTIONAL-AUDIO")
    (root / "models").mkdir()
    (root / "models" / "local-model.gguf").write_bytes(b"GGUF" + b"\x00" * 64)
    monkeypatch.setattr(api_module, "active_case_root", lambda: root)
    monkeypatch.setenv("MAINE_MATTER_STORE_KEY", "addon-studio-fictional-test-key")
    return root


def _post(client: TestClient, addon_id: str, payload: dict) -> dict:
    response = client.post(f"/api/addons/{addon_id}/actions", json=payload, headers=HEADERS)
    assert response.status_code == 200, (addon_id, response.text)
    assert response.headers["x-mfll-audit-event-id"]
    value = response.json()
    assert value["addon_id"] == addon_id
    assert value["review_required"] is True
    assert value["local_only"] is True
    assert value["rbac"]["tenant_scoped"] is True
    return value


def _configure_fake_whisper(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = tmp_path / "fictional_whisper_adapter.py"
    script.write_text(
        "import json,sys\n"
        "json.dump({'text':'Fictional local transcript.', 'segments':[{'start':0,'end':1}]}, open(sys.argv[2], 'w'))\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(
        "MFL_WHISPER_COMMAND_JSON",
        json.dumps([sys.executable, str(script), "{input}", "{output}"]),
    )
    monkeypatch.setenv("MFL_WHISPER_TOOL_ROOT", str(Path(sys.executable).resolve().parent))


def _signed_extension_payload() -> dict:
    private = Ed25519PrivateKey.generate()
    manifest = {
        "extension_id": "fictional_extension",
        "version": "1.0.0",
        "artifact_sha256": HASH_A,
        "permissions": ["matter.artifacts.write", "matter.records.read"],
    }
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    return {
        "manifest": manifest,
        "public_key": base64.b64encode(
            private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        ).decode(),
        "signature": base64.b64encode(private.sign(canonical)).decode(),
    }


def test_twenty_addons_execute_meaningfully_through_canonical_api(
    matter: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _configure_fake_whisper(monkeypatch, tmp_path)
    original_ocr = "Fictlonal OCR text"
    with TestClient(enterprise_app) as client:
        assert client.get("/api/addons").status_code == 403
        summary = client.get("/api/addons", headers=HEADERS)
        assert summary.status_code == 200
        assert set(summary.json()["addon_ids"]) == set(ADDON_IDS)

        results = {}
        results["native_whisper_transcription"] = _post(client, "native_whisper_transcription", {
            "media_relative_path": "hearing.wav",
            "source_hash": hashlib.sha256((matter / "hearing.wav").read_bytes()).hexdigest(),
        })
        assert results["native_whisper_transcription"]["status"] == "completed_review_required"
        assert results["native_whisper_transcription"]["no_network"] is True

        results["ocr_correction_studio"] = _post(client, "ocr_correction_studio", {
            "page_id": "page_001", "source_hash": hashlib.sha256(original_ocr.encode()).hexdigest(),
            "original_text": original_ocr, "corrected_text": "Fictional OCR text",
        })
        assert results["ocr_correction_studio"]["original_preserved"] is True

        results["communications_importer"] = _post(client, "communications_importer", {"messages": [{
            "message_id": "message_001", "source_format": "sms_export", "timestamp": "2026-01-02T03:04:05Z",
            "sender_token": "person_alpha", "recipient_tokens": ["person_beta"],
            "text": "Fictional logistics message.", "attachment_ids": ["attachment_001"],
        }]})
        assert results["communications_importer"]["imported_count"] == 1

        results["evidence_relationship_graph"] = _post(client, "evidence_relationship_graph", {
            "nodes": [{"node_id": "record_001", "kind": "record", "label": "Fictional order"},
                      {"node_id": "event_001", "kind": "event", "label": "Fictional event"}],
            "edges": [{"edge_id": "edge_001", "source": "record_001", "target": "event_001",
                       "relationship": "supports", "source_ref": {"record_id": "record_001", "locator": "page 1"}}],
        })
        assert results["evidence_relationship_graph"]["edge_count"] == 1

        results["local_model_manager"] = _post(client, "local_model_manager", {
            "action": "register", "model_id": "local_model_001", "artifact_relative_path": "models/local-model.gguf",
            "artifact_sha256": hashlib.sha256((matter / "models" / "local-model.gguf").read_bytes()).hexdigest(), "format": "gguf",
        })
        benchmark = _post(client, "local_model_manager", {
            "action": "verify", "model_id": "local_model_001",
        })
        assert benchmark["integrity_verified"] is True
        assert benchmark["automatic_download"] is False
        blocked_model = client.post("/api/addons/local_model_manager/actions", json={
            "action": "select", "model_id": "local_model_001",
        }, headers=HEADERS)
        assert blocked_model.status_code == 409
        selected = _post(client, "local_model_manager", {
            "action": "select", "model_id": "local_model_001", "confirmed": True,
        })
        assert selected["selected"] is True

        results["court_form_autofill"] = _post(client, "court_form_autofill", {
            "form_id": "fm_004", "freshness": "fresh", "required_fields": ["party_name"],
            "values": {"party_name": "Fictional Person"},
        })
        assert results["court_form_autofill"]["filing_ready"] is False
        stale = _post(client, "court_form_autofill", {"form_id": "fm_004", "freshness": "stale"})
        assert stale["status"] == "blocked"

        results["advanced_table_extraction"] = _post(client, "advanced_table_extraction", {"cells": [
            {"row": 0, "column": 0, "value": "Date", "source_locator": "page 1, table 1, r1c1"},
            {"row": 1, "column": 0, "value": "2026-01-01", "source_locator": "page 1, table 1, r2c1"},
        ]})
        assert results["advanced_table_extraction"]["provenance_complete"] is True

        results["financial_document_intelligence"] = _post(client, "financial_document_intelligence", {
            "review_threshold": 1000, "transactions": [{"transaction_id": "transaction_001", "date": "2026-01-01",
            "amount": 1250, "category": "housing", "source_ref": {"record_id": "record_001", "locator": "page 2"}}],
        })
        assert results["financial_document_intelligence"]["legal_conclusion"] is False

        results["semantic_order_comparison"] = _post(client, "semantic_order_comparison", {
            "base_terms": [{"term_id": "term_001", "text": "Exchange at 5 PM", "source_ref": {"record_id": "order_a", "locator": "term 1"}}],
            "changed_terms": [{"term_id": "term_001", "text": "Exchange at 6 PM", "source_ref": {"record_id": "order_b", "locator": "term 1"}}],
        })
        assert results["semantic_order_comparison"]["comparisons"][0]["status"] == "modified_review_required"
        assert results["semantic_order_comparison"]["operative_order_decided"] is False

        results["authority_update_center"] = _post(client, "authority_update_center", {"manifest": {
            "build_id": "maine_2026_001", "sources": [{"source_id": "title_19a", "official_url": "https://legislature.maine.gov/",
            "sha256": HASH_A}],
        }})
        assert results["authority_update_center"]["network_used"] is False
        assert results["authority_update_center"]["activation_performed"] is False

        results["guided_research_builder"] = _post(client, "guided_research_builder", {
            "question": "What source governs this fictional issue?", "issues": ["parental rights"],
            "source_classes": ["statutes", "opinions"],
        })
        assert results["guided_research_builder"]["current_law_claimed"] is False

        results["evidence_annotation_studio"] = _post(client, "evidence_annotation_studio", {
            "record_id": "record_001", "source_hash": HASH_A, "annotations": [{
                "annotation_id": "annotation_001", "kind": "observation", "locator": "page 1, line 2",
                "exact_text": "Fictional exact text", "note": "Review this source span.",
            }],
        })
        assert results["evidence_annotation_studio"]["original_modified"] is False

        results["local_automation_scheduler"] = _post(client, "local_automation_scheduler", {
            "action": "schedule", "schedule_id": "schedule_001", "task": "matter_health",
            "interval_hours": 24, "enabled": True,
        })
        blocked_run = client.post("/api/addons/local_automation_scheduler/actions", json={
            "action": "run", "schedule_id": "schedule_001",
        }, headers=HEADERS)
        assert blocked_run.status_code == 409
        run = _post(client, "local_automation_scheduler", {
            "action": "run", "schedule_id": "schedule_001", "confirmed": True,
        })
        assert run["status"] == "completed_review_required"

        results["secure_reviewer_collaboration"] = _post(client, "secure_reviewer_collaboration", {
            "recipient_label": "Fictional reviewer", "artifact_refs": [results["ocr_correction_studio"]["artifact"]["artifact_id"]],
        })
        assert results["secure_reviewer_collaboration"]["encrypted"] is True
        assert results["secure_reviewer_collaboration"]["send_performed"] is False

        results["matter_template_library"] = _post(client, "matter_template_library", {
            "action": "create", "template_id": "review_template", "fields": ["issue_label", "next_step"],
        })
        assert results["matter_template_library"]["matter_data_in_template"] is False
        applied = _post(client, "matter_template_library", {
            "action": "apply", "template_id": "review_template",
            "values": {"issue_label": "Fictional issue", "next_step": "Verify exact source"},
        })
        assert applied["matter_data_in_template"] is True

        results["conflict_entity_resolver"] = _post(client, "conflict_entity_resolver", {"mentions": [
            {"mention_id": "mention_001", "display": "Fictional Person", "source_ref": {"record_id": "record_001", "locator": "page 1"}},
            {"mention_id": "mention_002", "display": "FICTIONAL-PERSON", "source_ref": {"record_id": "record_002", "locator": "page 2"}},
        ]})
        assert results["conflict_entity_resolver"]["automatic_merge"] is False
        assert results["conflict_entity_resolver"]["candidates"][0]["status"] == "review_required"

        results["desktop_notification_center"] = _post(client, "desktop_notification_center", {"events": [{
            "event_id": "event_001", "severity": "blocked", "title": "Citation requires review",
            "corrective_action": "Open the exact source.",
        }]})
        notice_id = results["desktop_notification_center"]["notifications"][0]["notification_id"]
        acknowledged = _post(client, "desktop_notification_center", {
            "action": "acknowledge", "notification_id": notice_id,
        })
        assert acknowledged["acknowledged"] is True

        results["courtroom_bundle_exporter"] = _post(client, "courtroom_bundle_exporter", {"cards": [{
            "card_id": "card_001", "title": "<script>Fictional title</script>",
            "display_text": "<img src=x onerror=alert(1)>Exact record excerpt.",
            "source_ref": {"record_id": "record_001", "locator": "page 1"},
        }]})
        bundle = results["courtroom_bundle_exporter"]
        bundle_response = client.get(
            f"/api/addons/courtroom_bundle_exporter/results/{bundle['result_id']}/artifacts/{bundle['artifact']['artifact_id']}",
            headers=HEADERS,
        )
        assert bundle_response.status_code == 200
        assert bundle_response.headers["x-content-sha256"] == bundle["artifact"]["content_sha256"]
        from io import BytesIO
        with zipfile.ZipFile(BytesIO(bundle_response.content)) as archive:
            index = archive.read("index.html").decode()
        assert "<script>" not in index and "&lt;script&gt;" in index
        assert results["courtroom_bundle_exporter"]["private_notes_included"] is False

        results["voice_drafting_commands"] = _post(client, "voice_drafting_commands", {
            "transcript_text": "Fictional heading new paragraph review source comma then cite period",
        })
        assert results["voice_drafting_commands"]["filing_ready"] is False
        assert results["voice_drafting_commands"]["commands_applied"] == 3

        results["extension_sdk_permission_center"] = _post(client, "extension_sdk_permission_center", _signed_extension_payload())
        assert results["extension_sdk_permission_center"]["status"] == "registered_disabled"
        assert results["extension_sdk_permission_center"]["enabled"] is False
        assert results["extension_sdk_permission_center"]["arbitrary_network_access"] is False

        assert set(results) == set(ADDON_IDS)
        for addon_id, value in results.items():
            drilldown = client.get(
                f"/api/addons/{addon_id}/results/{value['result_id']}", headers=HEADERS
            )
            assert drilldown.status_code == 200, (addon_id, drilldown.text)
            assert drilldown.json()["item"]["result_id"] == value["result_id"]
            review = client.post(
                f"/api/addons/{addon_id}/results/{value['result_id']}/review",
                json={"decision": "accepted", "note": "Fictional E2E review.", "confirmed": True, "result_hash": value["result_hash"]},
                headers=HEADERS,
            )
            assert review.status_code == 200, (addon_id, review.text)
            assert review.json()["review_state"] == "accepted"

        integrity = client.get("/api/addons/integrity", headers=HEADERS)
        assert integrity.status_code == 200
        assert integrity.json()["status"] == "pass", integrity.text

        wrong_tenant = client.get("/api/addons", headers={"X-User-Role": "reviewer", "X-Tenant-Id": "other-tenant"})
        assert wrong_tenant.status_code == 404

        final = client.get("/api/addons", headers=HEADERS).json()
        assert all(final["counts"][addon_id] >= 1 for addon_id in ADDON_IDS)
        assert len(final["history_tail"]) == 20


def test_addon_state_encryption_isolation_and_fail_closed_native_dependency(
    matter: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = AddonStudioStore(matter)
    result = store.execute("communications_importer", {"messages": [{
        "message_id": "message_private", "source_format": "sms", "timestamp": "2026-01-01",
        "sender_token": "person_alpha", "recipient_tokens": ["person_beta"],
        "text": "SECRET-FICTIONAL-COMMUNICATION", "attachment_ids": [],
    }]})
    assert result["review_required"] is True
    assert b"SECRET-FICTIONAL-COMMUNICATION" not in store.state_path.read_bytes()

    second = tmp_path / "second-matter"
    second.mkdir()
    shutil.copytree(store.root, second / store.root.name)
    with pytest.raises(AddonStudioError) as exc:
        AddonStudioStore(second).summary()
    assert exc.value.code == "cross_matter_access_denied"

    monkeypatch.delenv("MFL_WHISPER_COMMAND_JSON", raising=False)
    monkeypatch.delenv("MFL_WHISPER_TOOL_ROOT", raising=False)
    monkeypatch.setenv("MFL_WHISPER_DISABLE_BUILTIN", "1")
    blocked = store.execute("native_whisper_transcription", {"media_relative_path": "hearing.wav"})
    assert blocked["status"] == "blocked"
    assert blocked["blockers"] == ["approved_local_whisper_engine_unavailable"]
    assert blocked["no_automatic_download"] is True


@pytest.mark.skipif(
    not os.environ.get("MFL_WHISPER_E2E_WAV"),
    reason="set MFL_WHISPER_E2E_WAV to run the admitted native-engine E2E",
)
def test_real_native_whisper_engine_through_canonical_api(
    matter: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = Path(os.environ["MFL_WHISPER_E2E_WAV"])
    assert source.is_file()
    shutil.copy2(source, matter / "hearing.wav")
    monkeypatch.delenv("MFL_WHISPER_COMMAND_JSON", raising=False)
    monkeypatch.delenv("MFL_WHISPER_TOOL_ROOT", raising=False)
    monkeypatch.delenv("MFL_WHISPER_DISABLE_BUILTIN", raising=False)
    with TestClient(enterprise_app) as client:
        result = _post(
            client,
            "native_whisper_transcription",
            {
                "media_relative_path": "hearing.wav",
                "source_hash": hashlib.sha256(source.read_bytes()).hexdigest(),
            },
        )
        assert result["status"] == "completed_review_required"
        assert result["engine"] == "whisper.cpp"
        assert result["engine_version"] == "1.9.2"
        assert result["model_name"] == "ggml-tiny.en-q5_1.bin"
        assert result["segment_count"] >= 1
        artifact = client.get(
            f"/api/addons/native_whisper_transcription/results/{result['result_id']}/artifacts/{result['artifact']['artifact_id']}",
            headers=HEADERS,
        )
        assert artifact.status_code == 200
        assert "fictional" in artifact.content.decode("utf-8").casefold()


def test_addon_routes_are_registered_without_duplicates() -> None:
    pairs = []
    for route in production_app.routes:
        for method in getattr(route, "methods", None) or []:
            if route.path.startswith("/api/addons"):
                pairs.append((method, route.path))
    assert set(pairs) == {
        ("GET", "/api/addons"),
        ("POST", "/api/addons/{addon_id}/actions"),
        ("GET", "/api/addons/{addon_id}/results/{result_id}"),
        ("POST", "/api/addons/{addon_id}/results/{result_id}/review"),
        ("GET", "/api/addons/integrity"),
        ("GET", "/api/addons/{addon_id}/results/{result_id}/artifacts/{artifact_id}"),
    }
    assert len(pairs) == len(set(pairs))


def test_twenty_addons_have_a_shipped_accessible_ui_entry_and_command() -> None:
    html = read_workbench_asset("workbench.html")
    javascript = read_workbench_asset("workbench.js")
    css = read_workbench_asset("workbench.css")
    assert 'id="addon-studio-overlay"' in html
    assert 'role="dialog"' in html
    assert 'aria-live="polite"' in html
    assert 'id="addon-inspect"' in html
    assert 'id="addon-review"' in html
    assert 'id="addon-download"' in html
    assert 'id="addon-integrity"' in html
    assert "runAddonAction" in javascript
    assert "inspectAddonResult" in javascript
    assert "reviewAddonResult" in javascript
    assert "downloadAddonArtifact" in javascript
    assert "verifyAddonIntegrity" in javascript
    assert "/api/addons/${encodeURIComponent(activeAddonId)}/actions" in javascript
    for addon_id in ADDON_IDS:
        assert addon_id in javascript
    assert "open_addon_${addon.id}" in javascript
    expected_features = {f"capability_{number}_{name}" for number, name in enumerate((
        "native_whisper_transcription", "ocr_correction_studio", "universal_communications_importer",
        "evidence_relationship_graph", "local_model_manager", "court_form_autofill",
        "advanced_table_extraction", "financial_document_intelligence", "semantic_order_comparison",
        "authority_update_center", "guided_legal_research_builder", "evidence_annotation_studio",
        "local_automation_scheduler", "secure_reviewer_collaboration", "matter_template_library",
        "conflict_entity_resolver", "desktop_notification_center", "courtroom_bundle_exporter",
        "voice_drafting_commands", "extension_sdk_permission_center",
    ), start=55)}
    assert expected_features <= set(ACCEPTED_FEATURE_IDS)
    assert ".addon-tool-button[aria-current=\"true\"]" in css
    assert "@media (forced-colors: active)" in css
    manifest = production_ui_manifest()
    assert manifest["status"] == "pass"
    assert "workbench.js" in manifest["assets"]
