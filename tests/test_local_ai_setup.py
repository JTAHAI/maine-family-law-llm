from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from legal.local_ai import LocalAiCatalog, LocalAiCatalogError, LocalAiSetupError, LocalAiSetupStore
from maine_family_law_llm import api


def _store(tmp_path: Path, audience: str = "tenant-a:" + "a" * 48) -> LocalAiSetupStore:
    return LocalAiSetupStore(root=tmp_path, audience=audience, encryption_key="fictional-test-key")


def _headers(*, tenant: str = "tenant-a", session: str = "a" * 48) -> dict[str, str]:
    return {
        "X-User-Role": "reviewer",
        "X-Tenant-Id": tenant,
        "X-MFLL-Client-Session": session,
    }


def test_setup_state_is_encrypted_partitioned_and_contains_no_matter_text(tmp_path: Path):
    store_a = _store(tmp_path)
    initial = store_a.status()
    assert initial["mode"] == "basic"
    assert initial["recommendation"]["installable_model_count"] == 0
    receipt = store_a.choose_basic_mode(expected_revision=0, user_confirmed=True, audit_event_id="audit-a")
    assert receipt["status"] == "basic_mode_selected"
    assert store_a.status()["revision"] == 1
    encrypted = store_a.path.read_text(encoding="utf-8")
    assert "audit-a" not in encrypted
    assert "matter" not in encrypted.casefold()
    assert store_a.path.parent.name != "tenant-a"
    assert _store(tmp_path, "tenant-b:" + "a" * 48).status()["revision"] == 0


def test_conversation_setup_uses_plain_choices_without_starting_or_downloading_a_model():
    result = LocalAiSetupStore._conversation_setup({
        "available_memory_bytes": 5 * 1024**3,
        "available_vram_bytes": 7 * 1024**3,
    })
    assert result["status"] == "options_available"
    assert [choice["eligible"] for choice in result["choices"]] == [True, True]
    assert result["model_presence_checked"] is False
    assert result["download_available_in_app"] is True
    assert result["network_used"] is False


def test_setup_requires_confirmation_revision_and_history_integrity(tmp_path: Path):
    store = _store(tmp_path)
    with pytest.raises(LocalAiSetupError, match="confirmation_required"):
        store.choose_basic_mode(expected_revision=0, user_confirmed=False)
    store.choose_basic_mode(expected_revision=0, user_confirmed=True)
    with pytest.raises(LocalAiSetupError, match="revision_conflict"):
        store.choose_basic_mode(expected_revision=0, user_confirmed=True)

    envelope = json.loads(store.path.read_text(encoding="utf-8"))
    envelope["ciphertext"] = "AAAA"
    store.path.write_text(json.dumps(envelope), encoding="utf-8")
    with pytest.raises(LocalAiSetupError, match="unavailable"):
        store.status()


def test_setup_routes_require_role_tenant_and_session_and_emit_review_response(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MFL_LOCAL_AI_STATE_ROOT", str(tmp_path / "state"))
    client = TestClient(api.app)
    assert client.get("/api/local-ai/setup/status").status_code == 403
    status = client.get("/api/local-ai/setup/status", headers=_headers())
    assert status.status_code == 200, status.text
    body = status.json()
    assert body["recommendation"]["installable_models"] == []
    assert body["conversation_setup"]["model_presence_checked"] is False
    assert body["conversation_setup"]["download_available_in_app"] is True
    assert body["review_required"] is True
    assert body["rbac"]["enforced"] is True
    selected = client.post(
        "/api/local-ai/setup/basic-mode",
        headers=_headers(),
        json={"expected_revision": body["revision"], "user_confirmed": True},
    )
    assert selected.status_code == 200, selected.text
    assert selected.json()["receipt"]["audit_event_id"]
    other = client.get("/api/local-ai/setup/status", headers=_headers(tenant="tenant-b"))
    assert other.status_code == 200
    assert other.json()["revision"] == 0


def test_empty_catalog_is_an_explicit_no_install_state_and_rejects_draft_profiles(tmp_path: Path):
    catalog_file = tmp_path / "local_ai_catalog.json"
    catalog_file.write_text(
        json.dumps({
            "schema_version": "mfl_local_ai_catalog_v1", "catalog_revision": 0,
            "publication_status": "unconfigured", "network_refresh_enabled": False,
            "review_required": True, "profiles": [],
        }),
        encoding="utf-8",
    )
    catalog = LocalAiCatalog(catalog_file)
    status = catalog.status()
    assert status["status"] == "no_installable_model_catalog"
    assert status["profiles"] == []
    with pytest.raises(LocalAiCatalogError, match="profile_unavailable"):
        catalog.profile("evidence-review")

    catalog_file.write_text(
        json.dumps({
            "schema_version": "mfl_local_ai_catalog_v1", "catalog_revision": 1,
            "publication_status": "released", "network_refresh_enabled": False,
            "review_required": True,
            "profiles": [{"profile_id": "draft-profile"}],
        }),
        encoding="utf-8",
    )
    rejected = catalog.status()
    assert rejected["profile_count"] == 0
    assert rejected["rejected_profile_count"] == 1


def test_catalog_assesses_measured_4b_and_8b_profiles_without_starting_a_model(tmp_path: Path):
    catalog_file = tmp_path / "local_ai_catalog.json"

    def profile(profile_id: str, model_class: str, memory_gib: int, disk_gib: int) -> dict:
        return {
            "profile_id": profile_id,
            "display_name": f"Fictional {model_class} reasoning",
            "engine_id": "fictional_local_engine",
            "artifact_sha256": "a" * 64,
            "artifact_bytes": disk_gib * 1024**3,
            "license_notice_id": "apache2_notice",
            "task_capabilities": ["source_assisted_chat"],
            "quality_evidence_id": "fictional_quality_v1",
            "admission_status": "production_admitted",
            "review_required": True,
            "download_origin_ids": ["fictional_official_origin"],
            "model_class": model_class,
            "resource_profiles": [{
                "resource_profile_id": f"{profile_id}_cpu_q4",
                "backend": "llama_cpp",
                "context_tokens": 2048,
                "min_available_memory_bytes": memory_gib * 1024**3,
                "min_disk_free_bytes": disk_gib * 1024**3,
                "estimated_peak_memory_bytes": (memory_gib + 1) * 1024**3,
                "expected_download_bytes": disk_gib * 1024**3,
                "expected_installed_bytes": disk_gib * 1024**3,
                "temporary_install_bytes": 1 * 1024**3,
                "hardware_baseline": "Measured fictional CPU baseline.",
            }],
        }

    catalog_file.write_text(json.dumps({
        "schema_version": "mfl_local_ai_catalog_v1", "catalog_revision": 1,
        "publication_status": "released", "network_refresh_enabled": False,
        "review_required": True,
        "profiles": [
            profile("reasoning_4b", "reasoning_4b", 8, 6),
            profile("reasoning_8b", "reasoning_8b", 14, 10),
        ],
    }), encoding="utf-8")
    catalog = LocalAiCatalog(catalog_file)
    hardware = {"available_memory_bytes": 10 * 1024**3, "disk_free_bytes": 12 * 1024**3}
    four = catalog.assess(catalog.profile("reasoning_4b"), hardware)
    eight = catalog.assess(catalog.profile("reasoning_8b"), hardware)
    assert four["status"] == "eligible_for_install_review"
    assert four["selected_resource_profile"]["context_tokens"] == 2048
    assert eight["status"] == "hardware_or_storage_review_required"
    assert "insufficient_available_memory" in eight["resource_options"][0]["blockers"]
    assert eight["network_used"] is False


def test_catalog_api_never_refreshes_or_offers_an_install_plan_without_a_qualified_profile(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MFL_LOCAL_AI_STATE_ROOT", str(tmp_path / "state"))
    client = TestClient(api.app, headers=_headers())
    catalog = client.get("/api/local-ai/setup/catalog")
    assert catalog.status_code == 200, catalog.text
    assert catalog.json()["catalog_refresh_supported"] is False
    assert catalog.json()["network_used"] is False
    assessed = client.post("/api/local-ai/setup/assess", json={})
    assert assessed.status_code == 200, assessed.text
    assert assessed.json()["catalog"]["profile_count"] == 0
    plan = client.post("/api/local-ai/setup/plans", json={"profile_id": "evidence-review"})
    assert plan.status_code == 404


def test_production_and_packaged_api_mirrors_stay_identical():
    root = Path(__file__).resolve().parents[1]
    assert (root / "maine_family_law_llm" / "api.py").read_bytes() == (
        root / "src" / "maine_family_law_llm" / "api.py"
    ).read_bytes()
    assert (root / "maine_family_law_llm" / "ui" / "workbench.html").read_bytes() == (
        root / "src" / "maine_family_law_llm" / "ui" / "workbench.html"
    ).read_bytes()
    assert (root / "maine_family_law_llm" / "ui" / "workbench.js").read_bytes() == (
        root / "src" / "maine_family_law_llm" / "ui" / "workbench.js"
    ).read_bytes()


def test_production_setup_ui_shows_hardware_path_without_promising_downloads():
    root = Path(__file__).resolve().parents[1]
    html = (root / "src" / "maine_family_law_llm" / "ui" / "workbench.html").read_text(encoding="utf-8")
    javascript = (root / "src" / "maine_family_law_llm" / "ui" / "workbench.js").read_text(encoding="utf-8")
    assert 'id="local-ai-setup-title"' in html
    assert 'id="local-ai-setup-refresh"' in html
    assert "No optional model is offered until its exact files, license, integrity record" in html
    assert "/api/local-ai/setup/status" in javascript
    assert "/api/local-ai/setup/basic-mode" in javascript
    assert "No optional model can be downloaded from this build yet" in javascript
    assert "applyLocalAgentProviderState" in javascript
    assert 'id="local-ai-chat-setup"' in html
    assert "Check this PC" in javascript
    assert "Questions you may have" in javascript
    assert "isLocalAiSetupQuestion" in javascript
    assert "/api/local-ai/setup/status" in javascript
