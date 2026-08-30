"""Host the exact frozen workbench with tiny fictional local-media fixtures.

The holder creates a disposable active matter containing one WAV, one MJPG AVI,
and one JPEG with synthetic EXIF metadata.  It imports those three local items
through the frozen canonical API, seeds one fictional transcript segment, and
keeps the production UI available for browser-driven acceptance.  It never
reads a user matter, downloads a model, or persists the temporary matter.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import tempfile
import time
import urllib.request
import wave
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2
import numpy
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OUTLINE_RUNNER = ROOT / "scripts" / "run-v8-structured-draft-outline-e2e.py"
HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "X-User-Role": "attorney",
    "X-Tenant-Id": "tenant-fictional-media-ui",
}


def _module(path: Path, name: str) -> Any:
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"module_unavailable:{name}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_wav(path: Path) -> str:
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(8_000)
        writer.writeframes(b"\x10\x00" * 8_000)
    return _sha256(path)


def _write_video(path: Path) -> str:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 5.0, (32, 24))
    if not writer.isOpened():
        raise RuntimeError("fictional_mjpg_encoder_unavailable")
    checker = numpy.indices((24, 32)).sum(axis=0) % 2 * 255
    frame = numpy.stack((checker, numpy.roll(checker, 2, axis=1), checker), axis=2).astype("uint8")
    for _ in range(5):
        writer.write(frame)
    writer.release()
    if not path.is_file() or not path.stat().st_size:
        raise RuntimeError("fictional_video_not_created")
    return _sha256(path)


def _write_image(path: Path) -> str:
    image = Image.new("RGB", (12, 8), (20, 40, 60))
    exif = Image.Exif()
    exif[306] = "2026:01:02 03:04:05"
    exif[271] = "FictionalMake"
    exif[272] = "FictionalModel"
    image.save(path, exif=exif)
    return _sha256(path)


def _request(base_url: str, route: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{base_url}{route}",
        data=json.dumps(payload).encode("utf-8"),
        headers=HEADERS,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        body = response.read().decode("utf-8")
    return json.loads(body) if body else {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-executable", required=True, type=Path)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--hold-seconds", type=int, default=480)
    parser.add_argument("--synthetic-speech-fixture", type=Path, help="Optional locally generated fictional PCM WAV for native transcription UI proof; never use a private recording.")
    args = parser.parse_args(argv)
    if not 30 <= args.hold_seconds <= 900:
        parser.error("hold_seconds_must_be_between_30_and_900")

    outline = _module(OUTLINE_RUNNER, "mfl_v8_media_ui_outline")
    runtime = args.runtime_executable.resolve(strict=True)
    package = args.package.resolve(strict=True)
    outline.validate_runtime_pair(runtime, package)
    helper = outline.load_helper()

    with tempfile.TemporaryDirectory(prefix="mfl-v8-media-review-ui-") as temporary:
        temporary_root = Path(temporary)
        case_root = temporary_root / "fictional-matter"
        case_root.mkdir()
        helper.build_case_fixture(case_root)
        media_root = case_root / "evidence"
        media_root.mkdir()
        audio_path = media_root / "fictional-audio.wav"
        video_path = media_root / "fictional-video.avi"
        image_path = media_root / "fictional-image.jpg"
        audio_duration = 1.0
        if args.synthetic_speech_fixture:
            speech_fixture = args.synthetic_speech_fixture.resolve(strict=True)
            if speech_fixture.stat().st_size > 2_000_000:
                parser.error("synthetic_speech_fixture_must_be_under_two_megabytes")
            with wave.open(str(speech_fixture), "rb") as speech:
                audio_duration = speech.getnframes() / speech.getframerate()
                if speech.getnchannels() != 1 or speech.getsampwidth() != 2 or not 0 < audio_duration <= 30:
                    parser.error("synthetic_speech_fixture_requires_mono_16bit_pcm_up_to_30_seconds")
            shutil.copyfile(speech_fixture, audio_path)
            audio_hash = _sha256(audio_path)
        else:
            audio_hash = _write_wav(audio_path)
        video_hash = _write_video(video_path)
        image_hash = _write_image(image_path)

        port = helper.free_port()
        base_url = f"http://127.0.0.1:{port}"
        process = helper.start_runtime(runtime, port, localappdata=temporary_root / "localappdata")
        monitor = helper.RuntimeNetworkMonitor(process.pid)
        monitor.start()
        try:
            health = helper.wait_json(f"{base_url}/api/health", timeout_s=180)
            if health.get("status") != "ok":
                raise RuntimeError("frozen_runtime_health_failed")
            activation = outline.request(helper, "POST", base_url, "/api/activate-corpus", {"case_root": str(case_root)})
            if activation.get("status") != "ok":
                raise RuntimeError("fictional_matter_activation_failed")
            imported = _request(
                base_url,
                "/api/hearing-media/import",
                {
                    "media": [
                        {"media_id": "fictional-audio", "title": "Fictional audio", "filename": audio_path.name, "media_kind": "audio", "source_hash": audio_hash, "duration_seconds": audio_duration, "confidentiality": "private_record"},
                        {"media_id": "fictional-video", "title": "Fictional video", "filename": video_path.name, "media_kind": "video", "source_hash": video_hash, "duration_seconds": 1, "confidentiality": "private_record"},
                        {"media_id": "fictional-image", "title": "Fictional image", "filename": image_path.name, "media_kind": "image", "source_hash": image_hash, "confidentiality": "private_record"},
                    ]
                },
            )
            if imported.get("review_required") is not True:
                raise RuntimeError("fictional_media_import_failed")
            transcript = _request(
                base_url,
                "/api/hearing-media/media/fictional-audio/transcribe",
                {
                    "transcript_text": "Fictional transcript for local UI review.",
                    "segments": [
                        {
                            "segment_id": "segment-0001",
                            "start_seconds": 0,
                            "end_seconds": 1,
                            "speaker_label": "Unknown",
                            "text": "Fictional transcript for local UI review.",
                        }
                    ],
                },
            )
            if transcript.get("review_required") is not True:
                raise RuntimeError("fictional_transcript_seed_failed")
            print(
                json.dumps(
                    {
                        "status": "ready",
                        "base_url": base_url,
                        "fictional_data_only": True,
                        "media": {
                            "audio": {"media_id": "fictional-audio", "source_file": "evidence/fictional-audio.wav", "source_hash": audio_hash, "duration_seconds": audio_duration, "synthetic_speech_supplied": bool(args.synthetic_speech_fixture)},
                            "video": {"media_id": "fictional-video", "source_file": "evidence/fictional-video.avi"},
                            "image": {"media_id": "fictional-image", "source_file": "evidence/fictional-image.jpg"},
                        },
                        "started_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            time.sleep(args.hold_seconds)
        finally:
            network = monitor.stop()
            outline.terminate(process)
            print(
                json.dumps(
                    {
                        "status": "stopped",
                        "external_connection_count": int(network.get("external_connection_count") or 0),
                        "network_samples": int(network.get("sample_count") or 0),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
