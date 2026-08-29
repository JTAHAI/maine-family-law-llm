from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.contracts import EndpointInventory
from app.api.main import app as api_app
from maine_family_law_llm import api as api_module


def _headers(*, role: str = "attorney", tenant: str = "tenant-pass61") -> dict[str, str]:
    return {"X-User-Role": role, "X-Tenant-Id": tenant}


def _registered_routes() -> set[tuple[str, str]]:
    result: set[tuple[str, str]] = set()
    for route in api_app.routes:
        for method in getattr(route, "methods", None) or set():
            if method not in {"HEAD", "OPTIONS"}:
                result.add((method, getattr(route, "path", "")))
    return result


def _create_transcript(client: TestClient) -> None:
    media_hash = hashlib.sha256(b"fictional-pass61-audio").hexdigest()
    imported = client.post(
        "/api/hearing-media/import",
        json={"media": [{"media_id": "fictional-audio", "title": "Fictional audio", "filename": "fictional-audio.wav", "media_kind": "audio", "source_hash": media_hash, "confidentiality": "private_record"}]},
        headers=_headers(),
    )
    assert imported.status_code == 200
    transcript = client.post(
        "/api/hearing-media/media/fictional-audio/transcribe",
        json={
            "transcript_text": "[00:00:03] Speaker: Original fictional statement.",
            "segments": [{"segment_id": "segment-0001", "text": "[00:00:03] Speaker: Original fictional statement.", "speaker_label": "Speaker", "start_seconds": 3, "end_seconds": 7}],
        },
        headers=_headers(),
    )
    assert transcript.status_code == 200


def test_pass61_records_an_immutable_source_bound_transcript_correction(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "fictional-matter"
    case_root.mkdir()
    monkeypatch.setattr(api_module, "active_case_root", lambda: case_root)
    client = TestClient(api_app)
    _create_transcript(client)

    response = client.post(
        "/api/hearing-media/media/fictional-audio/transcript-corrections",
        json={"segment_id": "segment-0001", "corrected_text": "Corrected fictional statement.", "reviewer_notes": "Fictional human-review correction."},
        headers=_headers(),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["review_required"] is True
    assert payload["no_original_modified"] is True
    assert payload["correction"]["review_status"] == "review_required"
    assert payload["correction"]["segment_id"] == "segment-0001"
    assert payload["source"]["media_id"] == "fictional-audio"
    assert payload["source"]["start_seconds"] == 3
    assert payload["source"]["end_seconds"] == 7
    assert payload["audit_event"]["audit_status"] == "emitted"

    summary = client.get("/api/hearing-media", headers=_headers())
    transcript = summary.json()["transcripts"][-1]
    assert transcript["segments"][0]["text"] == "[00:00:03] Speaker: Original fictional statement."
    assert transcript["corrections"][0]["corrected_text"] == "Corrected fictional statement."
    assert transcript["correction_status"] == "review_required"

    encrypted_state = case_root / "23_HEARING_MEDIA_WORKBENCH" / "hearing-media-workbench.json.enc"
    assert encrypted_state.exists()
    assert "Corrected fictional statement." not in encrypted_state.read_text(encoding="utf-8")
    assert "Original fictional statement." not in encrypted_state.read_text(encoding="utf-8")


def test_pass61_rejects_wrong_role_unknown_segment_and_cross_matter(monkeypatch, tmp_path: Path) -> None:
    matter_a = tmp_path / "fictional-matter-a"
    matter_b = tmp_path / "fictional-matter-b"
    matter_a.mkdir(); matter_b.mkdir()
    current = {"root": matter_a}
    monkeypatch.setattr(api_module, "active_case_root", lambda: current["root"])
    client = TestClient(api_app)
    _create_transcript(client)

    denied = client.post(
        "/api/hearing-media/media/fictional-audio/transcript-corrections",
        json={"segment_id": "segment-0001", "corrected_text": "No role."},
        headers=_headers(role="viewer"),
    )
    assert denied.status_code == 403
    unknown = client.post(
        "/api/hearing-media/media/fictional-audio/transcript-corrections",
        json={"segment_id": "missing-segment", "corrected_text": "Unknown segment."},
        headers=_headers(),
    )
    assert unknown.status_code == 404

    current["root"] = matter_b
    isolated = client.post(
        "/api/hearing-media/media/fictional-audio/transcript-corrections",
        json={"segment_id": "segment-0001", "corrected_text": "Cross-matter attempt."},
        headers=_headers(),
    )
    assert isolated.status_code == 404


def test_pass61_registers_the_canonical_route_and_production_control() -> None:
    inventory = EndpointInventory().compare_to_registered(_registered_routes())
    assert inventory["status"] == "pass"
    source = Path("src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    mirror = Path("maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    assert source == mirror
    assert "Transcript correction" in source
    assert "/api/hearing-media/media/${encodeURIComponent(mediaId)}/transcript-corrections" in source
    assert "Inspect local media binding" in source
