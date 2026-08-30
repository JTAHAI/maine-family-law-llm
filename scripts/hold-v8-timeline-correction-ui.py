"""Temporarily host frozen timeline-correction UI with a fictional matter.

This QA harness creates only a disposable synthetic matter, binds one timeline
event to a hash-verified local record, and hosts the exact frozen runtime long
enough to exercise its production Evidence drawer.  It never reads a user
matter, contacts a network service, or persists fixture data after exit.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import tempfile
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTLINE_RUNNER = ROOT / "scripts" / "run-v8-structured-draft-outline-e2e.py"


def _module(path: Path, name: str) -> Any:
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"module_unavailable:{name}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _inject_post_checkpoint_record(helper: Any, case_root: Path, delay_seconds: int) -> None:
    """Add one fictional, index-backed record after a UI checkpoint can be saved.

    This belongs only to the disposable QA matter.  The index is replaced
    atomically so the frozen runtime either sees the prior fixture or the
    complete new record; it never reads a partially-written manifest.
    """
    time.sleep(delay_seconds)
    data = b"FICTIONAL QA POST-CHECKPOINT RECORD. Review this source without deciding any fact.\n"
    record = helper.stage_record(
        case_root,
        evidence_id="REC-POST-CHECKPOINT",
        filename="post-checkpoint-record.txt",
        data=data,
        title="Fictional post-checkpoint record",
        text_excerpt="Fictional QA post-checkpoint record.",
        text_content="Fictional QA post-checkpoint record. Review required.",
        issue_lanes=["review"],
    )
    index_path = case_root / "04_INDEXES" / "private_search_index.json"
    rows = json.loads(index_path.read_text(encoding="utf-8"))
    rows.append(record)
    temporary_index = index_path.with_suffix(".json.pending")
    temporary_index.write_text(json.dumps(rows, indent=2, sort_keys=True), encoding="utf-8")
    temporary_index.replace(index_path)
    print(
        json.dumps(
            {
                "status": "post_checkpoint_record_injected",
                "record_id": "REC-POST-CHECKPOINT",
                "delay_seconds": delay_seconds,
            },
            sort_keys=True,
        ),
        flush=True,
    )


def _mark_synthetic_scan_pending_local_ocr(records: list[dict[str, Any]], case_root: Path) -> None:
    """Make the disposable image-only fixture match production OCR semantics.

    The installed-qualification helper includes an image-only PDF so its
    record-level OCR route can be exercised.  Its human-readable fixture text
    is useful for that route, but would incorrectly make the Corpus OCR choice
    path believe the scan already has searchable text.  This holder is for the
    UI workflow, so mark only that fictional row as an actual pending OCR
    candidate and atomically rewrite the private index before activation.
    """
    candidate = next((row for row in records if row.get("evidence_id") == "REC-OCR"), None)
    if not isinstance(candidate, dict):
        raise RuntimeError("fictional_ocr_record_missing")
    candidate.update(
        {
            # Canonical ingestion keeps a validated local source path along
            # with the relative private-copy locator.  The qualification
            # fixture normally calls record-level OCR directly and therefore
            # does not need this field; the batch workflow does.
            "source_path": str((case_root / "02_PRIVATE_FORENSIC_MASTER" / "files" / "scan.pdf").resolve()),
            "parser_status": "image_only_page",
            "text_status": "not_available",
            "ocr_status": "ocr_not_run",
            "text_excerpt": "",
            "text_content": "",
            "parser_metadata": {"image_only_pages": 1, "ocr_required": True},
        }
    )
    index_path = case_root / "04_INDEXES" / "private_search_index.json"
    temporary_index = index_path.with_suffix(".json.pending")
    temporary_index.write_text(json.dumps(records, indent=2, sort_keys=True), encoding="utf-8")
    temporary_index.replace(index_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-executable", required=True, type=Path)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--hold-seconds", type=int, default=300)
    parser.add_argument("--post-checkpoint-record-after-ready-seconds", type=int, default=0)
    args = parser.parse_args(argv)
    if not 10 <= args.hold_seconds <= 600:
        parser.error("hold_seconds_must_be_between_10_and_600")
    if not 0 <= args.post_checkpoint_record_after_ready_seconds < args.hold_seconds:
        parser.error("post_checkpoint_record_delay_must_be_zero_or_less_than_hold_seconds")

    outline = _module(OUTLINE_RUNNER, "mfl_v8_outline_e2e")
    runtime = args.runtime_executable.resolve(strict=True)
    package = args.package.resolve(strict=True)
    outline.validate_runtime_pair(runtime, package)
    helper = outline.load_helper()

    with tempfile.TemporaryDirectory(prefix="mfl-v8-timeline-correction-ui-") as temporary:
        temporary_root = Path(temporary)
        case_root = temporary_root / "fictional-matter"
        case_root.mkdir()
        records = helper.build_case_fixture(case_root)
        _mark_synthetic_scan_pending_local_ocr(records, case_root)
        original = next(row for row in records if row.get("evidence_id") == "REC-DOCX")
        replacement = next(row for row in records if row.get("evidence_id") == "REC-PDF")
        port = helper.free_port()
        base_url = f"http://127.0.0.1:{port}"
        process = helper.start_runtime(runtime, port, localappdata=temporary_root / "localappdata")
        monitor = helper.RuntimeNetworkMonitor(process.pid)
        monitor.start()
        injection_thread: threading.Thread | None = None
        try:
            health = helper.wait_json(f"{base_url}/api/health", timeout_s=180)
            if health.get("status") != "ok":
                raise RuntimeError("frozen_runtime_health_failed")
            activation = outline.request(helper, "POST", base_url, "/api/activate-corpus", {"case_root": str(case_root)})
            if activation.get("status") != "ok":
                raise RuntimeError("fictional_matter_activation_failed")
            created = outline.request(
                helper,
                "POST",
                base_url,
                "/api/timeline/events",
                {
                    "event_label": "Fictional schedule note",
                    "classification": "observed",
                    "date_value": "2026-01-03",
                    "date_type": "source date",
                    "source_record_id": str(original["evidence_id"]),
                    "source_hash": str(original["source_hash"]),
                    "issue_tags": ["school"],
                    "child_impact_tags": ["routine"],
                },
            )
            event = dict(created.get("event") or {})
            event_id = str(event.get("event_id") or "")
            if not event_id:
                raise RuntimeError("fictional_timeline_event_creation_failed")
            print(
                json.dumps(
                    {
                        "status": "ready",
                        "base_url": base_url,
                        "fictional_data_only": True,
                        "event_id": event_id,
                        "original_record_id": str(original["evidence_id"]),
                        "replacement_record_id": str(replacement["evidence_id"]),
                        "started_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            if args.post_checkpoint_record_after_ready_seconds:
                injection_thread = threading.Thread(
                    target=_inject_post_checkpoint_record,
                    args=(helper, case_root, args.post_checkpoint_record_after_ready_seconds),
                    name="fictional-post-checkpoint-record",
                    daemon=False,
                )
                injection_thread.start()
            time.sleep(args.hold_seconds)
        finally:
            if injection_thread is not None:
                injection_thread.join(timeout=5)
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
