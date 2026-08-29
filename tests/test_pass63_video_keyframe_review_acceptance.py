from __future__ import annotations

import base64
import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.contracts import EndpointInventory
from app.api.main import app as api_app
from maine_family_law_llm import api as api_module


cv2 = pytest.importorskip("cv2")


def _headers(*, role: str = "attorney") -> dict[str, str]:
    return {"X-User-Role": role, "X-Tenant-Id": "tenant-pass63"}


def _registered_routes() -> set[tuple[str, str]]:
    return {
        (method, getattr(route, "path", ""))
        for route in api_app.routes
        for method in (getattr(route, "methods", None) or set())
        if method not in {"HEAD", "OPTIONS"}
    }


def _fictional_video(case_root: Path) -> tuple[Path, str]:
    evidence = case_root / "evidence"
    evidence.mkdir()
    path = evidence / "fictional-video.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 5.0, (32, 24))
    if not writer.isOpened():
        pytest.fail("OpenCV MJPG test encoder is unavailable; local keyframe path cannot be evaluated")
    for blue in (0, 80, 160, 240, 255):
        frame = __import__("numpy").full((24, 32, 3), (blue, 40, 20), dtype="uint8")
        writer.write(frame)
    writer.release()
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def _seed_video(client: TestClient, source_hash: str) -> None:
    response = client.post(
        "/api/hearing-media/import",
        json={"media": [{"media_id": "fictional-video", "title": "Fictional local video", "filename": "fictional-video.avi", "media_kind": "video", "source_hash": source_hash, "duration_seconds": 1, "confidentiality": "private_record"}]},
        headers=_headers(),
    )
    assert response.status_code == 200


def test_pass63_generates_encrypted_source_bound_keyframes_and_annotation(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "fictional-matter"
    case_root.mkdir()
    video, source_hash = _fictional_video(case_root)
    monkeypatch.setattr(api_module, "active_case_root", lambda: case_root)
    client = TestClient(api_app)
    _seed_video(client, source_hash)

    generated = client.post(
        "/api/hearing-media/media/fictional-video/keyframe-reviews",
        json={"source_file": "evidence/fictional-video.avi", "timestamps_seconds": [0]},
        headers=_headers(),
    )
    assert generated.status_code == 200
    payload = generated.json()
    review = payload["keyframe_review"]
    assert payload["review_required"] is True
    assert payload["no_original_modified"] is True
    assert review["media_hash"] == source_hash
    assert review["source_file_hash"] == source_hash
    assert review["frame_count"] == 1
    frame = review["frames"][0]
    assert frame["visual_sha256"]
    assert "source_file" not in review
    assert video.read_bytes()

    preview = client.get(
        f"/api/hearing-media/media/fictional-video/keyframe-reviews/{review['review_id']}/frames/{frame['frame_id']}",
        headers=_headers(),
    )
    assert preview.status_code == 200
    data_url = preview.json()["data_url"]
    assert data_url.startswith("data:image/png;base64,")
    png = base64.b64decode(data_url.split(",", 1)[1])
    assert hashlib.sha256(png).hexdigest() == frame["visual_sha256"]

    unconfirmed = client.post(
        f"/api/hearing-media/media/fictional-video/keyframe-reviews/{review['review_id']}/annotations",
        json={"frame_id": frame["frame_id"], "annotation_text": "Fictional visible marker."},
        headers=_headers(),
    )
    assert unconfirmed.status_code == 400
    annotated = client.post(
        f"/api/hearing-media/media/fictional-video/keyframe-reviews/{review['review_id']}/annotations",
        json={"confirmed": True, "frame_id": frame["frame_id"], "annotation_text": "Fictional visible marker."},
        headers=_headers(),
    )
    assert annotated.status_code == 200
    annotation = annotated.json()["annotation"]
    assert annotation["visual_sha256"] == frame["visual_sha256"]
    assert annotation["no_authenticity_determination"] is True
    assert annotated.json()["source"]["timestamp_seconds"] == 0.0

    encrypted_artifact = case_root / "23_HEARING_MEDIA_WORKBENCH" / "keyframes" / "fictional-video" / review["review_id"] / f"{frame['frame_id']}.png.enc"
    assert encrypted_artifact.exists()
    assert not encrypted_artifact.read_bytes().startswith(b"\x89PNG")
    encrypted_state = case_root / "23_HEARING_MEDIA_WORKBENCH" / "hearing-media-workbench.json.enc"
    assert "Fictional visible marker." not in encrypted_state.read_text(encoding="utf-8")


def test_pass63_rejects_path_escape_hash_mismatch_and_wrong_role(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "fictional-matter"
    case_root.mkdir()
    _video, source_hash = _fictional_video(case_root)
    monkeypatch.setattr(api_module, "active_case_root", lambda: case_root)
    client = TestClient(api_app)
    _seed_video(client, source_hash)
    denied = client.post(
        "/api/hearing-media/media/fictional-video/keyframe-reviews",
        json={"source_file": "evidence/fictional-video.avi", "timestamps_seconds": [0]},
        headers=_headers(role="viewer"),
    )
    assert denied.status_code == 403
    escaped = client.post(
        "/api/hearing-media/media/fictional-video/keyframe-reviews",
        json={"source_file": "../fictional-video.avi", "timestamps_seconds": [0]},
        headers=_headers(),
    )
    assert escaped.status_code == 400
    changed = case_root / "evidence" / "changed.avi"
    changed.write_bytes(b"not the imported video")
    mismatch = client.post(
        "/api/hearing-media/media/fictional-video/keyframe-reviews",
        json={"source_file": "evidence/changed.avi", "timestamps_seconds": [0]},
        headers=_headers(),
    )
    assert mismatch.status_code == 409


def test_pass63_registers_routes_and_production_keyframe_control() -> None:
    assert EndpointInventory().compare_to_registered(_registered_routes())["status"] == "pass"
    source = Path("src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    mirror = Path("maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    assert source == mirror
    assert "Video keyframe review" in source
    assert "/api/hearing-media/media/${encodeURIComponent(mediaId)}/keyframe-reviews" in source
    assert "Open encrypted keyframe" in source
