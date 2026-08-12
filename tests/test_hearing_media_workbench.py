from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.contracts import EndpointInventory
from app.api.main import app as api_app
from app.web.ui_contracts import UICompletionAuditor
from app.web.ui_inventory import UIViewInventory
from maine_family_law_llm import api as api_module


def _headers() -> dict[str, str]:
    return {"X-User-Role": "attorney", "X-Tenant-Id": "tenant-hearing-media"}


def _client(monkeypatch, case_root: Path) -> TestClient:
    monkeypatch.setattr(api_module, "active_case_root", lambda: case_root)
    return TestClient(api_app)


def _registered_routes(app) -> set[tuple[str, str]]:
    registered: set[tuple[str, str]] = set()
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", None) or set()
        for method in methods:
            if method in {"HEAD", "OPTIONS"}:
                continue
            registered.add((method, path))
    return registered


def _media_payload(audio_hash: str, video_hash: str) -> dict[str, object]:
    return {
        "media": [
            {
                "media_id": "hearing-audio",
                "title": "Synthetic hearing audio",
                "filename": "hearing-audio.wav",
                "media_kind": "audio",
                "source_hash": audio_hash,
                "duration_seconds": 42,
                "recorded_at": "2026-08-01T10:00:00-04:00",
                "confidentiality": "private_record",
            },
            {
                "media_id": "hearing-video",
                "title": "Synthetic hearing video",
                "filename": "hearing-video.mp4",
                "media_kind": "video",
                "source_hash": video_hash,
                "duration_seconds": 42,
                "recorded_at": "2026-08-01T10:00:00-04:00",
                "confidentiality": "private_record",
            },
        ]
    }


def _transcript_text() -> str:
    return "\n".join(
        [
            "[00:00:01] Court: Call the case to order.",
            "[00:00:05] Counsel A: Exhibit 1 is marked and admitted.",
            "[00:00:10] Witness: The parent email is parent@example.test and the phone is 207-555-1212.",
            "[00:00:15] Counsel B: Objection, hearsay.",
            "[00:00:20] Court: Overruled.",
        ]
    )


def _official_text() -> str:
    return "\n".join(
        [
            "[00:00:01] Court: Call the case to order.",
            "[00:00:05] Counsel A: Exhibit 1 is marked and admitted.",
            "[00:00:10] Witness: The parent email is parent@example.test and the phone is 207-555-1212.",
            "[00:00:15] Counsel B: Objection, hearsay.",
            "[00:00:20] Court: Sustained.",
        ]
    )


def test_hearing_media_workbench_records_transcripts_timeline_exhibits_privacy_and_export(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "case"
    case_root.mkdir()
    audio = case_root / "hearing-audio.wav"
    video = case_root / "hearing-video.mp4"
    audio.write_bytes(b"synthetic-audio-bytes")
    video.write_bytes(b"synthetic-audio-bytes")
    before_audio = audio.read_bytes()
    before_video = video.read_bytes()

    client = _client(monkeypatch, case_root)
    imported = client.post("/api/hearing-media/import", json=_media_payload(hashlib.sha256(before_audio).hexdigest(), hashlib.sha256(before_video).hexdigest()), headers=_headers())
    assert imported.status_code == 200
    payload = imported.json()
    assert payload["imported_count"] == 2
    assert payload["no_original_modified"] is True
    assert payload["duplicate_groups"] == [hashlib.sha256(before_audio).hexdigest()]

    blocked = client.post("/api/hearing-media/media/hearing-audio/transcribe", json={}, headers=_headers())
    assert blocked.status_code == 200
    blocked_payload = blocked.json()
    assert blocked_payload["status"] == "blocked"
    assert "no_admitted_transcription_engine" in blocked_payload["blockers"]
    assert blocked_payload["no_automatic_model_download"] is True

    transcript = client.post(
        "/api/hearing-media/media/hearing-audio/transcribe",
        json={
            "transcript_text": _transcript_text(),
            "segments": [
                {"text": "[00:00:01] Court: Call the case to order.", "speaker_label": "Court"},
                {"text": "[00:00:05] Counsel A: Exhibit 1 is marked and admitted.", "speaker_label": "Counsel A"},
                {"text": "[00:00:10] Witness: The parent email is parent@example.test and the phone is 207-555-1212.", "speaker_label": "Witness"},
                {"text": "[00:00:15] Counsel B: Objection, hearsay.", "speaker_label": "Counsel B"},
                {"text": "[00:00:20] Court: Overruled.", "speaker_label": "Court"},
            ],
        },
        headers=_headers(),
    )
    assert transcript.status_code == 200
    transcript_payload = transcript.json()
    transcript_id = transcript_payload["transcript"]["transcript_id"]
    transcript_sha = transcript_payload["transcript"]["transcript_sha256"]
    assert transcript_payload["transcript"]["segment_count"] == 5
    assert transcript_payload["no_original_modified"] is True
    transcript_dir = case_root / "23_HEARING_MEDIA_WORKBENCH" / "transcripts" / "hearing-audio" / transcript_id
    assert (transcript_dir / "transcript.txt").exists()
    assert (transcript_dir / "transcript.json").exists()
    assert (transcript_dir / "transcript-receipt.json").exists()
    assert audio.read_bytes() == before_audio
    assert video.read_bytes() == before_video

    speaker_review = client.post(
        "/api/hearing-media/media/hearing-audio/speaker-review",
        json={"labels": [{"segment_id": "segment-0001", "speaker_label": "Judge"}, {"segment_id": "segment-0002", "speaker_label": "Counsel"}]},
        headers=_headers(),
    )
    assert speaker_review.status_code == 200
    speaker_payload = speaker_review.json()
    assert speaker_payload["speaker_identity_inference_blocked"] is True
    assert speaker_payload["transcript"]["segments"][0]["speaker_label"] == "Judge"

    timeline = client.post("/api/hearing-media/media/hearing-audio/timeline/build", headers=_headers())
    assert timeline.status_code == 200
    timeline_payload = timeline.json()["timeline"]
    assert timeline_payload["event_count"] == 5
    assert timeline_payload["events"][0]["timestamp_start"] == "00:00:00"
    assert any(event["classification"]["kind"] == "exhibit_reference" for event in timeline_payload["events"])
    assert any(event["classification"]["kind"] == "objection" for event in timeline_payload["events"])
    assert any(event["classification"]["kind"] == "ruling" for event in timeline_payload["events"])

    comparison = client.post(
        "/api/hearing-media/media/hearing-audio/compare",
        json={"official_transcript_text": _official_text()},
        headers=_headers(),
    )
    assert comparison.status_code == 200
    comparison_rows = comparison.json()["comparison"]["rows"]
    assert any(row["status"] == "changed" for row in comparison_rows)

    exhibits = client.get("/api/hearing-media/media/hearing-audio/exhibits", headers=_headers())
    assert exhibits.status_code == 200
    exhibit_index = exhibits.json()["exhibit_index"]
    assert exhibit_index["exhibit_count"] == 1
    assert exhibit_index["exhibits"][0]["mention_does_not_prove_admission"] is True

    unresolved = client.post("/api/hearing-media/media/hearing-audio/citations", json={"citations": [{"label": "Unresolved cite"}]}, headers=_headers())
    assert unresolved.status_code == 200
    assert unresolved.json()["citation_review"]["status"] == "blocked"

    resolved = client.post(
        "/api/hearing-media/media/hearing-audio/citations",
        json={"citations": [{"label": "Transcript line 1", "source_span": {"start": 0, "end": 12}}]},
        headers=_headers(),
    )
    assert resolved.status_code == 200
    assert resolved.json()["citation_review"]["status"] == "pass"

    privacy = client.post("/api/hearing-media/media/hearing-audio/privacy-scan", headers=_headers())
    assert privacy.status_code == 200
    privacy_payload = privacy.json()["privacy_review"]["privacy_review"]
    assert privacy_payload["finding_counts"]["EMAIL_ADDRESS"] == 1
    assert privacy_payload["finding_counts"]["PHONE_NUMBER"] == 1

    redacted = client.post(
        "/api/hearing-media/media/hearing-audio/redacted-copy",
        json={"approved": True, "source_hash": transcript_sha},
        headers=_headers(),
    )
    assert redacted.status_code == 200
    redacted_payload = redacted.json()
    assert redacted_payload["no_original_modified"] is True
    redacted_dir = case_root / "23_HEARING_MEDIA_WORKBENCH" / "redactions" / "hearing-audio" / transcript_id
    redacted_text = (redacted_dir / "redacted-transcript.txt").read_text(encoding="utf-8")
    assert "parent@example.test" not in redacted_text
    assert "207-555-1212" not in redacted_text

    blocked_export = client.post("/api/hearing-media/exports", json={"export_kind": "hearing_media_review_bundle"}, headers=_headers())
    assert blocked_export.status_code == 200
    assert blocked_export.json()["status"] == "pass"
    export_payload = blocked_export.json()
    export_dir = case_root / "23_HEARING_MEDIA_WORKBENCH" / "exports" / export_payload["build_id"]
    assert (export_dir / "hearing-media-workbench-export.json").exists()
    assert (export_dir / "hearing-media-workbench-export.txt").exists()
    assert (export_dir / "hearing-media-workbench-receipt.json").exists()

    appellate = client.get("/api/hearing-media/media/hearing-audio/appellate-record", headers=_headers())
    assert appellate.status_code == 200
    checklist = appellate.json()["checklist"]
    assert all(item["status"] == "present" for item in checklist)

    summary = client.get("/api/hearing-media", headers=_headers())
    assert summary.status_code == 200
    summary_payload = summary.json()
    assert summary_payload["media_count"] == 2
    assert summary_payload["transcript_count"] >= 1
    assert summary_payload["privacy_review_count"] >= 1
    assert summary_payload["redaction_count"] >= 1

    history = client.get("/api/hearing-media/review-history", headers=_headers())
    assert history.status_code == 200
    assert history.json()["history"]


def test_hearing_media_workbench_cancellation_preserves_the_original_and_blocks_without_engine(monkeypatch, tmp_path: Path) -> None:
    case_root = tmp_path / "case"
    case_root.mkdir()
    media = case_root / "hearing-audio.wav"
    media.write_bytes(b"cancel-me")
    before = media.read_bytes()

    client = _client(monkeypatch, case_root)
    client.post(
        "/api/hearing-media/import",
        json={
            "media": [
                {
                    "media_id": "hearing-audio",
                    "title": "Cancel test",
                    "filename": "hearing-audio.wav",
                    "media_kind": "audio",
                    "source_hash": hashlib.sha256(before).hexdigest(),
                }
            ]
        },
        headers=_headers(),
    )

    blocked = client.post("/api/hearing-media/media/hearing-audio/transcribe", json={}, headers=_headers())
    assert blocked.status_code == 200
    assert blocked.json()["status"] == "blocked"

    cancellation = client.post("/api/hearing-media/media/hearing-audio/cancel", headers=_headers())
    assert cancellation.status_code == 200
    assert cancellation.json()["cancellation"]["status"] == "cancelled"
    assert media.read_bytes() == before

    media_record = client.get("/api/hearing-media/media/hearing-audio", headers=_headers())
    assert media_record.status_code == 200
    assert media_record.json()["media"]["transcription_status"] == "cancelled"


def test_hearing_media_ui_inventory_and_route_contracts_include_the_shipped_workbench() -> None:
    pages_dir = Path("app/web/pages")
    ui_inventory = UIViewInventory(pages_dir).validate()
    assert ui_inventory["status"] == "pass"
    assert "hearing-media-workbench.tsx" in {view["file"] for view in ui_inventory["views"]}

    ui_audit = UICompletionAuditor("app/web/pages").audit().as_dict()
    assert ui_audit["status"] == "pass"

    endpoint_inventory = EndpointInventory().compare_to_registered(_registered_routes(api_app))
    assert endpoint_inventory["status"] == "pass"
