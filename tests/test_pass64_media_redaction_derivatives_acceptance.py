from __future__ import annotations

import base64
import hashlib
import io
import wave
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.contracts import EndpointInventory
from app.api.main import app as api_app
from maine_family_law_llm import api as api_module


cv2 = pytest.importorskip("cv2")
numpy = pytest.importorskip("numpy")


def _headers(*, role: str = "attorney") -> dict[str, str]:
    return {"X-User-Role": role, "X-Tenant-Id": "tenant-pass64"}


def _routes() -> set[tuple[str, str]]:
    return {(method, getattr(route, "path", "")) for route in api_app.routes for method in (getattr(route, "methods", None) or set()) if method not in {"HEAD", "OPTIONS"}}


def _write_fictional_wav(path: Path) -> str:
    samples = b"\x10\x00" * 8_000
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(1); writer.setsampwidth(2); writer.setframerate(8_000); writer.writeframes(samples)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_fictional_video(path: Path) -> str:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 5.0, (32, 24))
    if not writer.isOpened():
        pytest.fail("OpenCV MJPG test encoder is unavailable; local video-redaction path cannot be evaluated")
    checker = numpy.indices((24, 32)).sum(axis=0) % 2 * 255
    frame = numpy.stack((checker, numpy.roll(checker, 2, axis=1), checker), axis=2).astype("uint8")
    for _ in range(5): writer.write(frame)
    writer.release()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _seed(client: TestClient, audio_hash: str, video_hash: str) -> None:
    response = client.post(
        "/api/hearing-media/import",
        json={"media": [
            {"media_id": "fictional-audio", "title": "Fictional audio", "filename": "fictional.wav", "media_kind": "audio", "source_hash": audio_hash, "duration_seconds": 1},
            {"media_id": "fictional-video", "title": "Fictional video", "filename": "fictional.avi", "media_kind": "video", "source_hash": video_hash, "duration_seconds": 1},
        ]},
        headers=_headers(),
    )
    assert response.status_code == 200


def test_pass64_creates_encrypted_wav_mute_and_video_blur_derivatives(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "fictional-matter"; case_root.mkdir()
    evidence = case_root / "evidence"; evidence.mkdir()
    audio = evidence / "fictional.wav"; video = evidence / "fictional.avi"
    audio_hash, video_hash = _write_fictional_wav(audio), _write_fictional_video(video)
    original_audio, original_video = audio.read_bytes(), video.read_bytes()
    monkeypatch.setattr(api_module, "active_case_root", lambda: case_root)
    client = TestClient(api_app); _seed(client, audio_hash, video_hash)

    unconfirmed = client.post("/api/hearing-media/media/fictional-audio/redaction-derivatives", json={"source_file": "evidence/fictional.wav", "mute_intervals": [{"start_seconds": 0.1, "end_seconds": 0.4}]}, headers=_headers())
    assert unconfirmed.status_code == 400
    muted = client.post("/api/hearing-media/media/fictional-audio/redaction-derivatives", json={"confirmed": True, "source_file": "evidence/fictional.wav", "mute_intervals": [{"start_seconds": 0.1, "end_seconds": 0.4}]}, headers=_headers())
    assert muted.status_code == 200
    muted_derivative = muted.json()["derivative"]
    assert muted_derivative["redaction_kind"] == "audio_mute"
    assert muted_derivative["media_hash"] == audio_hash
    assert muted.json()["no_original_modified"] is True
    muted_preview = client.get(f"/api/hearing-media/media/fictional-audio/redaction-derivatives/{muted_derivative['derivative_id']}", headers=_headers())
    assert muted_preview.status_code == 200
    wav_bytes = base64.b64decode(muted_preview.json()["data_url"].split(",", 1)[1])
    with wave.open(io.BytesIO(wav_bytes), "rb") as reader:
        frames = reader.readframes(reader.getnframes())
    assert frames[800 * 2 : 3_200 * 2] == b"\x00" * (2_400 * 2)
    assert frames[:800 * 2] == b"\x10\x00" * 800

    blurred = client.post("/api/hearing-media/media/fictional-video/redaction-derivatives", json={"confirmed": True, "source_file": "evidence/fictional.avi", "blur_intervals": [{"start_seconds": 0, "end_seconds": 0.8}], "blur_regions": [{"x": 0, "y": 0, "width": 0.5, "height": 0.5}]}, headers=_headers())
    assert blurred.status_code == 200
    blurred_derivative = blurred.json()["derivative"]
    assert blurred_derivative["redaction_kind"] == "video_blur"
    preview = client.get(f"/api/hearing-media/media/fictional-video/redaction-derivatives/{blurred_derivative['derivative_id']}", headers=_headers())
    assert preview.status_code == 200
    redacted_path = tmp_path / "redacted.avi"; redacted_path.write_bytes(base64.b64decode(preview.json()["data_url"].split(",", 1)[1]))
    original_cap, redacted_cap = cv2.VideoCapture(str(video)), cv2.VideoCapture(str(redacted_path))
    original_ok, original_frame = original_cap.read(); redacted_ok, redacted_frame = redacted_cap.read(); original_cap.release(); redacted_cap.release()
    assert original_ok and redacted_ok
    assert not numpy.array_equal(original_frame[:12, :16], redacted_frame[:12, :16])
    assert audio.read_bytes() == original_audio
    assert video.read_bytes() == original_video

    encrypted_audio = case_root / "23_HEARING_MEDIA_WORKBENCH" / "media-redactions" / "fictional-audio" / f"{muted_derivative['derivative_id']}.wav.enc"
    assert encrypted_audio.exists()
    assert not encrypted_audio.read_bytes().startswith(b"RIFF")


def test_pass64_refuses_wrong_role_path_escape_and_hash_changed_source(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "fictional-matter"; case_root.mkdir(); evidence = case_root / "evidence"; evidence.mkdir()
    audio = evidence / "fictional.wav"; audio_hash = _write_fictional_wav(audio)
    video = evidence / "fictional.avi"; video_hash = _write_fictional_video(video)
    monkeypatch.setattr(api_module, "active_case_root", lambda: case_root)
    client = TestClient(api_app); _seed(client, audio_hash, video_hash)
    denied = client.post("/api/hearing-media/media/fictional-audio/redaction-derivatives", json={"confirmed": True, "source_file": "evidence/fictional.wav", "mute_intervals": [{"start_seconds": 0, "end_seconds": 0.5}]}, headers=_headers(role="viewer"))
    assert denied.status_code == 403
    escaped = client.post("/api/hearing-media/media/fictional-audio/redaction-derivatives", json={"confirmed": True, "source_file": "../fictional.wav", "mute_intervals": [{"start_seconds": 0, "end_seconds": 0.5}]}, headers=_headers())
    assert escaped.status_code == 400
    changed = evidence / "changed.wav"; changed.write_bytes(b"not matching imported audio")
    mismatch = client.post("/api/hearing-media/media/fictional-audio/redaction-derivatives", json={"confirmed": True, "source_file": "evidence/changed.wav", "mute_intervals": [{"start_seconds": 0, "end_seconds": 0.5}]}, headers=_headers())
    assert mismatch.status_code == 409


def test_pass64_routes_and_production_control_are_registered() -> None:
    assert EndpointInventory().compare_to_registered(_routes())["status"] == "pass"
    source = Path("src/maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    mirror = Path("maine_family_law_llm/ui/workbench.js").read_text(encoding="utf-8")
    assert source == mirror
    assert "Media redaction derivative" in source
    assert "/api/hearing-media/media/${encodeURIComponent(mediaId)}/redaction-derivatives" in source
    assert "Open encrypted derivative" in source
