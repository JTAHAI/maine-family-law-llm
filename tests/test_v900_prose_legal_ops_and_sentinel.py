from __future__ import annotations


def test_personal_and_public_edition_shells_are_explicit() -> None:
    from maine_family_law_llm.local_workbench_ui import (
        render_local_workbench_html,
        render_public_workbench_html,
    )

    personal = render_local_workbench_html()
    public = render_public_workbench_html()

    assert 'data-edition="personal"' in personal
    assert "Personal edition" in personal
    assert 'data-edition="public"' in public
    assert "Public edition" in public
    from maine_family_law_llm.version import VERSION

    assert f"Public edition version {VERSION}" in public
    assert "ProSe-SENTINEL AI" in personal
    assert "{{WORKBENCH_EDITION" not in personal
    assert "{{WORKBENCH_EDITION" not in public


def test_sentinel_training_admission_is_source_anchor_only() -> None:
    from maine_family_law_llm.prose_sentinel import prepare_training_admission, sentinel_status

    status = sentinel_status()
    assert status["local_only"] is True
    assert status["model_training_execution"] is False
    assert status["external_execution"] is False

    packet = prepare_training_admission(
        model_id="family-model-9",
        source_cards=[
            {
                "source_id": "maine-rule-001",
                "snippet": "A source excerpt that is never returned in the admission packet.",
                "metadata": {"source_lane": "legal_authority", "authority_status": "official"},
            }
        ],
    )

    assert packet["admission_status"] == "review_required"
    assert packet["human_review_required"] is True
    assert packet["model_training_execution"] is False
    assert packet["source_anchor_count"] == 1
    assert "snippet" not in str(packet)
    assert len(packet["source_anchors"][0]["source_sha256"]) == 64


def test_sentinel_blocks_an_admission_without_reviewable_sources() -> None:
    from maine_family_law_llm.prose_sentinel import prepare_training_admission

    packet = prepare_training_admission(model_id="family-model-9", source_cards=[])

    assert packet["admission_status"] == "blocked"
    assert "no_source_anchors_available" in packet["blockers"]
    assert packet["canonical_writeback"] is False


def test_api_exposes_public_shell_and_nonexecuting_sentinel_boundary() -> None:
    import pytest

    pytest.importorskip("fastapi")
    from maine_family_law_llm import api

    assert "Public edition" in api.public_workbench()
    assert api.sentinel_local_status()["human_review_required"] is True
    packet = api.sentinel_training_admission(
        api.SentinelTrainingAdmissionRequest(
            model_id="family-model-9",
            source_cards=[{"source_id": "source-1", "snippet": "reviewable excerpt"}],
        )
    )
    assert packet["model_training_execution"] is False


def test_model_management_api_exposes_the_same_sentinel_admission_boundary() -> None:
    import pytest

    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from app.api.main import app

    response = TestClient(app).post(
        "/api/models/family-model-9/sentinel-admission",
        headers={"X-User-Role": "admin", "X-Tenant-Id": "sentinel-test"},
        json={"source_cards": [{"source_id": "source-1", "snippet": "reviewable excerpt"}]},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["model_training_execution"] is False
    assert payload["source_anchor_count"] == 1
    assert "reviewable excerpt" not in response.text
