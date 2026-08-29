"""Exercise the packaged offline courtroom-media review path with fictional audio.

The runner creates a one-second silent WAV inside a disposable fictional matter,
then proves the canonical media import, transcript, confirmed review session,
source drill-down, local playback payload, transcript sync, separate encrypted
note, and zero-network boundary.  Its report contains hashes and statuses only.
It never treats media review as authentication, identity, admissibility, or a
legal conclusion.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import sys
import tempfile
import urllib.request
import wave
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
QUALIFICATION_HELPER_PATH = ROOT / "scripts" / "run-installed-offline-qualification.py"
HEADERS = {"X-User-Role": "attorney", "X-Tenant-Id": "tenant-fictional-media"}


def load_helper() -> Any:
    specification = importlib.util.spec_from_file_location("mfl_installed_offline_qualification", QUALIFICATION_HELPER_PATH)
    if specification is None or specification.loader is None:
        raise RuntimeError("installed_offline_qualification_helper_unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_runtime_pair(runtime: Path, package: Path) -> None:
    expected_runtime = package.parent.parent / "runtime" / "MaineFamilyLawLLM.exe"
    if runtime.resolve() != expected_runtime.resolve():
        raise ValueError("runtime_is_not_paired_with_supplied_msix")


def request_json(method: str, base_url: str, route: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json", **HEADERS}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(f"{base_url}{route}", data=data, headers=headers, method=method.upper())
    with urllib.request.urlopen(request, timeout=120) as response:
        body = response.read().decode("utf-8")
    return json.loads(body) if body else {}


def terminate(process: Any) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=30)
    except Exception:  # noqa: BLE001
        process.kill()
        process.wait(timeout=30)


def write_fictional_wav(path: Path) -> str:
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(8_000)
        output.writeframes(b"\x00\x00" * 8_000)
    return sha256_file(path)


def safe_session(session: dict[str, Any]) -> dict[str, Any]:
    return {
        "session_id": str(session.get("session_id") or ""),
        "media_id": str(session.get("media_id") or ""),
        "clip_start_seconds": session.get("clip_start_seconds"),
        "clip_end_seconds": session.get("clip_end_seconds"),
        "review_required": session.get("review_required") is True,
        "private_notes_separate": session.get("private_notes_separate") is True,
        "source_hash": str(session.get("source_hash") or session.get("media_hash") or ""),
    }


def run(*, runtime: Path, package: Path) -> dict[str, Any]:
    validate_runtime_pair(runtime, package)
    helper = load_helper()
    report: dict[str, Any] = {
        "schema_version": "mfl_v8_courtroom_media_e2e_v1",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "BLOCKED",
        "fictional_data_only": True,
        "package_sha256": sha256_file(package),
        "runtime_sha256": sha256_file(runtime),
        "checks": {},
        "artifacts": {},
        "blockers": [],
        "notice": (
            "Fictional local-workflow evidence only. This path prepares a review-required media session and separately encrypted note; "
            "it does not authenticate media, identify anyone, establish completeness, admissibility, legal authority, attorney review, Store qualification, or Enterprise GA."
        ),
    }
    with tempfile.TemporaryDirectory(prefix="mfl-v8-courtroom-media-") as temporary:
        temporary_root = Path(temporary)
        case_root = temporary_root / "fictional-matter"
        case_root.mkdir()
        helper.build_case_fixture(case_root)
        audio_path = case_root / "fictional_hearing.wav"
        source_hash = write_fictional_wav(audio_path)
        localappdata = temporary_root / "localappdata"
        process = None
        monitor = None
        try:
            port = helper.free_port()
            base_url = f"http://127.0.0.1:{port}"
            process = helper.start_runtime(runtime, port, localappdata=localappdata)
            monitor = helper.RuntimeNetworkMonitor(process.pid)
            monitor.start()
            health = helper.wait_json(f"{base_url}/api/health", timeout_s=180)
            activation = helper.request_json("POST", f"{base_url}/api/activate-corpus", {"case_root": str(case_root)})
            imported = request_json(
                "POST",
                base_url,
                "/api/hearing-media/import",
                {
                    "media": [
                        {
                            "media_id": "fictional_hearing_audio",
                            "title": "Fictional hearing audio",
                            "filename": audio_path.name,
                            "media_kind": "audio",
                            "source_hash": source_hash,
                            "duration_seconds": 1,
                            "confidentiality": "private_record",
                        }
                    ]
                },
            )
            transcript = request_json(
                "POST",
                base_url,
                "/api/hearing-media/media/fictional_hearing_audio/transcribe",
                {
                    "transcript_text": "Fictional transcript segment for software qualification.",
                    "segments": [
                        {
                            "segment_id": "fictional_segment_001",
                            "start_seconds": 0,
                            "end_seconds": 1,
                            "speaker_label": "Fictional speaker",
                            "text": "Fictional transcript segment for software qualification.",
                        }
                    ],
                },
            )
            created = request_json(
                "POST",
                base_url,
                "/api/hearing-media/media/fictional_hearing_audio/courtroom-sessions",
                {
                    "session_id": "fictional_courtroom_001",
                    "source_file": audio_path.name,
                    "clip_start_seconds": 0,
                    "clip_end_seconds": 1,
                    "confirmed": True,
                },
            )
            source = request_json("GET", base_url, "/api/hearing-media/courtroom-sessions/fictional_courtroom_001/source")
            playback = request_json("GET", base_url, "/api/hearing-media/courtroom-sessions/fictional_courtroom_001/playback")
            sync = request_json(
                "POST",
                base_url,
                "/api/hearing-media/courtroom-sessions/fictional_courtroom_001/sync",
                {"position_seconds": 0.5},
            )
            note = request_json(
                "POST",
                base_url,
                "/api/hearing-media/courtroom-sessions/fictional_courtroom_001/private-notes",
                {
                    "reviewer_safe_id": "fictional_reviewer_001",
                    "note_text": "Fictional separate private review note.",
                    "confirmed": True,
                },
            )
            inventory = request_json("GET", base_url, "/api/hearing-media")
            network = monitor.stop()
            monitor = None

            session = dict(created.get("session") or {})
            state = safe_session(session)
            playback_payload = str(playback.get("data_url") or "")
            checks = {
                "runtime_health": health.get("status") == "ok",
                "fictional_matter_activated": activation.get("status") == "ok",
                "media_imported_review_required": imported.get("review_required") is True,
                "transcript_review_required": transcript.get("review_required") is True,
                "confirmed_session_review_required": state["review_required"],
                "session_source_hash_bound": source.get("source", {}).get("media_hash") == source_hash,
                "offline_playback_payload": playback_payload.startswith("data:audio/wav;base64,") and bool(base64.b64decode(playback_payload.split(",", 1)[1])),
                "keyboard_controls_present": playback.get("keyboard_controls", {}).get("space") == "play_pause",
                "transcript_sync_present": bool(sync.get("segments")),
                "private_note_separate": note.get("not_in_session_or_export") is True and state["private_notes_separate"],
                "inventory_excludes_private_note": "Fictional separate private review note." not in json.dumps(inventory, sort_keys=True),
                "zero_external_connections": int(network.get("external_connection_count") or 0) == 0,
            }
            report["checks"] = {name: "pass" if passed else "fail" for name, passed in checks.items()}
            report["artifacts"] = {
                "session": state,
                "source_hash": source_hash,
                "transcript_segment_count": len(list(sync.get("segments") or [])),
                "network_samples": int(network.get("sample_count") or 0),
            }
            failed = sorted(name for name, passed in checks.items() if not passed)
            report["blockers"] = failed
            report["decision"] = "PASS" if not failed else "BLOCKED"
        except Exception as exc:  # noqa: BLE001
            report["blockers"] = [f"courtroom_media_exception:{type(exc).__name__}"]
        finally:
            if monitor is not None:
                monitor.stop()
            terminate(process)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-executable", required=True, type=Path)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "dist" / "ga_today" / "evidence" / "08_v8_courtroom_media_e2e.json",
    )
    args = parser.parse_args(argv)
    runtime = args.runtime_executable.resolve(strict=True)
    package = args.package.resolve(strict=True)
    try:
        report = run(runtime=runtime, package=package)
    except ValueError as exc:
        print(f"Courtroom-media qualification blocked: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "decision": report["decision"], "blockers": report["blockers"]}, indent=2))
    return 0 if report["decision"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
