from __future__ import annotations

import hashlib
import wave
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app as api_app
from maine_family_law_llm import api as api_module


def _headers() -> dict[str, str]:
    return {"X-User-Role": "attorney", "X-Tenant-Id": "tenant-courtroom-media"}


def _write_fictional_wav(path: Path) -> bytes:
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(8000)
        stream.writeframes(b"\x00\x00" * 8000)
    return path.read_bytes()


def _setup_client(monkeypatch, root: Path) -> TestClient:
    monkeypatch.setattr(api_module, "active_case_root", lambda: root)
    return TestClient(api_app)


def _prepare_audio_session(client: TestClient, source_hash: str) -> None:
    imported = client.post(
        "/api/hearing-media/import",
        json={
            "media": [
                {
                    "media_id": "hearing_audio",
                    "title": "Fictional hearing audio",
                    "filename": "hearing.wav",
                    "media_kind": "audio",
                    "source_hash": source_hash,
                    "duration_seconds": 10,
                    "confidentiality": "private_record",
                }
            ]
        },
        headers=_headers(),
    )
    assert imported.status_code == 200
    transcript = client.post(
        "/api/hearing-media/media/hearing_audio/transcribe",
        json={
            "transcript_text": "Fictional speaker: This is a fictional review transcript.",
            "segments": [
                {
                    "segment_id": "segment_001",
                    "start_seconds": 0,
                    "end_seconds": 5,
                    "speaker_label": "Fictional speaker",
                    "text": "Fictional speaker: This is a fictional review transcript.",
                }
            ],
        },
        headers=_headers(),
    )
    assert transcript.status_code == 200


def test_pass70_offline_player_sync_source_and_private_notes_are_separate(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "fictional-matter"
    root.mkdir()
    audio = _write_fictional_wav(root / "hearing.wav")
    client = _setup_client(monkeypatch, root)
    _prepare_audio_session(client, hashlib.sha256(audio).hexdigest())
    created = client.post(
        "/api/hearing-media/media/hearing_audio/courtroom-sessions",
        json={
            "session_id": "courtroom_001",
            "source_file": "hearing.wav",
            "clip_start_seconds": 0,
            "clip_end_seconds": 5,
            "confirmed": True,
        },
        headers=_headers(),
    )
    assert created.status_code == 200
    assert created.json()["session"]["private_notes_separate"] is True
    source = client.get("/api/hearing-media/courtroom-sessions/courtroom_001/source", headers=_headers())
    assert source.status_code == 200
    assert source.json()["source"]["media_hash"] == hashlib.sha256(audio).hexdigest()
    playback = client.get("/api/hearing-media/courtroom-sessions/courtroom_001/playback", headers=_headers())
    assert playback.status_code == 200
    assert playback.json()["data_url"].startswith("data:audio/wav;base64,")
    assert playback.json()["keyboard_controls"]["space"] == "play_pause"
    sync = client.post(
        "/api/hearing-media/courtroom-sessions/courtroom_001/sync",
        json={"position_seconds": 2},
        headers=_headers(),
    )
    assert sync.status_code == 200
    assert sync.json()["segments"][0]["text"].startswith("Fictional speaker")
    note_text = "Fictional private courtroom review note."
    note = client.post(
        "/api/hearing-media/courtroom-sessions/courtroom_001/private-notes",
        json={"reviewer_safe_id": "reviewer_001", "note_text": note_text, "confirmed": True},
        headers=_headers(),
    )
    assert note.status_code == 200 and note.json()["not_in_session_or_export"] is True
    summary = client.get("/api/hearing-media", headers=_headers()).json()
    assert summary["courtroom_sessions"][0]["private_notes_separate"] is True
    assert note_text not in str(summary)
    encrypted_note = next((root / "23_HEARING_MEDIA_WORKBENCH" / "courtroom-notes").glob("*.json.enc"))
    assert note_text not in encrypted_note.read_text(encoding="utf-8")
    notes = client.get("/api/hearing-media/courtroom-sessions/courtroom_001/private-notes", headers=_headers())
    assert notes.status_code == 200 and notes.json()["notes"][0]["note_text"] == note_text


def test_pass70_fails_closed_on_confirmation_hash_scope_and_clip_errors(monkeypatch, tmp_path: Path) -> None:
    root_a = tmp_path / "fictional-matter-a"
    root_b = tmp_path / "fictional-matter-b"
    root_a.mkdir()
    root_b.mkdir()
    audio = _write_fictional_wav(root_a / "hearing.wav")
    active = {"root": root_a}
    monkeypatch.setattr(api_module, "active_case_root", lambda: active["root"])
    client = TestClient(api_app)
    _prepare_audio_session(client, hashlib.sha256(audio).hexdigest())
    unconfirmed = client.post(
        "/api/hearing-media/media/hearing_audio/courtroom-sessions",
        json={"session_id": "courtroom_001", "source_file": "hearing.wav", "clip_end_seconds": 5},
        headers=_headers(),
    )
    assert unconfirmed.status_code == 400
    bad_clip = client.post(
        "/api/hearing-media/media/hearing_audio/courtroom-sessions",
        json={"session_id": "courtroom_001", "source_file": "hearing.wav", "clip_start_seconds": 5, "clip_end_seconds": 4, "confirmed": True},
        headers=_headers(),
    )
    assert bad_clip.status_code == 400
    created = client.post(
        "/api/hearing-media/media/hearing_audio/courtroom-sessions",
        json={"session_id": "courtroom_001", "source_file": "hearing.wav", "clip_start_seconds": 0, "clip_end_seconds": 5, "confirmed": True},
        headers=_headers(),
    )
    assert created.status_code == 200
    assert client.get("/api/hearing-media/courtroom-sessions/courtroom_001/source").status_code == 403
    active["root"] = root_b
    assert client.get("/api/hearing-media/courtroom-sessions/courtroom_001/source", headers=_headers()).status_code == 404


def test_pass70_ships_mirrored_courtroom_player_controls() -> None:
    src = Path("src/maine_family_law_llm/ui/workbench.js")
    mirror = Path("maine_family_law_llm/ui/workbench.js")
    assert src.read_bytes() == mirror.read_bytes()
    text = src.read_text(encoding="utf-8")
    assert "Courtroom media player" in text
    assert "/api/hearing-media/courtroom-sessions/" in text
    assert "aria-keyshortcuts" in text
    assert "Private notes are encrypted separately" in text
