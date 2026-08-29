from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app as api_app
from maine_family_law_llm import api as api_module


def _headers(*, role: str = "reviewer") -> dict[str, str]:
    return {"X-User-Role": role, "X-Tenant-Id": "tenant-pass62"}


def _seed_transcript(client: TestClient) -> None:
    source_hash = hashlib.sha256(b"fictional-pass62-audio").hexdigest()
    assert client.post(
        "/api/hearing-media/import",
        json={"media": [{"media_id": "speaker-audio", "title": "Fictional speaker review", "filename": "speaker-audio.wav", "media_kind": "audio", "source_hash": source_hash}]},
        headers=_headers(),
    ).status_code == 200
    assert client.post(
        "/api/hearing-media/media/speaker-audio/transcribe",
        json={"transcript_text": "[00:00:04] Unknown: Fictional testimony.", "segments": [{"segment_id": "segment-0001", "text": "[00:00:04] Unknown: Fictional testimony.", "speaker_label": "unknown", "start_seconds": 4, "end_seconds": 9}]},
        headers=_headers(),
    ).status_code == 200


def test_pass62_requires_confirmation_and_records_human_label_with_source_binding(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "fictional-matter"
    case_root.mkdir()
    monkeypatch.setattr(api_module, "active_case_root", lambda: case_root)
    client = TestClient(api_app)
    _seed_transcript(client)

    unconfirmed = client.post(
        "/api/hearing-media/media/speaker-audio/speaker-review",
        json={"labels": [{"segment_id": "segment-0001", "speaker_label": "Witness A"}]},
        headers=_headers(),
    )
    assert unconfirmed.status_code == 400
    assert unconfirmed.json()["detail"]["error"] == "speaker_review_confirmation_required"

    response = client.post(
        "/api/hearing-media/media/speaker-audio/speaker-review",
        json={"confirmed": True, "labels": [{"segment_id": "segment-0001", "speaker_label": "Witness A"}]},
        headers=_headers(),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["review_required"] is True
    assert payload["speaker_identity_inference_blocked"] is True
    assert payload["no_biometric_identity_inference"] is True
    assert payload["changes"] == [{
        "segment_id": "segment-0001", "before": "unknown", "after": "Witness A", "start_seconds": 4,
        "end_seconds": 9, "text_sha256": payload["changes"][0]["text_sha256"], "speaker_label_source": "user_review",
        "speaker_identity_inference_blocked": True, "review_required": True,
    }]
    assert payload["source"]["media_id"] == "speaker-audio"
    assert payload["source"]["segments"][0]["segment_id"] == "segment-0001"
    assert payload["audit_event"]["audit_status"] == "emitted"

    summary = client.get("/api/hearing-media", headers=_headers())
    segment = summary.json()["transcripts"][-1]["segments"][0]
    assert segment["speaker_label"] == "Witness A"
    assert segment["speaker_label_source"] == "user_review"
    assert segment["speaker_label_confirmed"] is True


def test_pass62_rejects_unknown_source_segment_without_partial_label_change(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "fictional-matter"
    case_root.mkdir()
    monkeypatch.setattr(api_module, "active_case_root", lambda: case_root)
    client = TestClient(api_app)
    _seed_transcript(client)
    response = client.post(
        "/api/hearing-media/media/speaker-audio/speaker-review",
        json={"confirmed": True, "labels": [{"segment_id": "segment-0001", "speaker_label": "Witness A"}, {"segment_id": "missing", "speaker_label": "Witness B"}]},
        headers=_headers(),
    )
    assert response.status_code == 404
    summary = client.get("/api/hearing-media", headers=_headers())
    assert summary.json()["transcripts"][-1]["segments"][0]["speaker_label"] == "unknown"


def test_pass62_has_a_production_ui_control_and_mirrored_bundle() -> None:
    source = Path("src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    mirror = Path("maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    assert source == mirror
    assert "Speaker-label review" in source
    assert "/api/hearing-media/media/${encodeURIComponent(mediaId)}/speaker-review" in source
    assert "No biometric identity" in source
    assert "Inspect local media binding" in source
