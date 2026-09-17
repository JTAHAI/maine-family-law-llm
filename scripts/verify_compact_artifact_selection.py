"""Rehash the existing selected files while native read locks are held; no copies.

No signer, admission, inference, native-closure qualification or installation.
The prior measured runtime inventory is hash-pinned, not regenerated from RECORD.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from legal.fast_interchange.compact_admission import CompactInventory  # noqa: E402
from legal.fast_interchange.compact_artifacts import _WindowsLocks  # noqa: E402
from legal.fast_interchange.compact_ranker_process import selected_runtime_site  # noqa: E402
from legal.fast_interchange.compact_span_reader import PINNED  # noqa: E402
from legal.security.strict_json import strict_json_loads  # noqa: E402
from scripts.qualify_compact_tokenizers_notice import DIRECTORY as NOTICE_DIRECTORY  # noqa: E402

OUT = ROOT / "dist/model-candidates/compact-fleet-20260908"
INVENTORY_SHA = "868bc6425f40923a4cfd60e0aca33e73532a7d6c35f5504b0d762fd711ceab12"


def run(run_id):
    if not run_id.isalnum() or not 1 <= len(run_id) <= 16:
        raise ValueError("invalid_run_id")
    target = OUT / f"compact-locked-files-{run_id}.json"
    if target.exists():
        raise ValueError("preserve_existing_report")
    started = time.monotonic()
    stack = None
    report = dict(
        schema_version="compact_existing_files_locked_proof_v1",
        run_id=run_id,
        timestamp=datetime.now(UTC).isoformat(),
        passed=False,
        signed_admission_tested=False,
        model_inference=False,
        model_quality_qualified=False,
        production_admitted=False,
        native_closure_qualified=False,
        runnable=False,
        new_model_copy_bytes=0,
        new_download_bytes=0,
        files_verified=0,
        bytes_verified=0,
        owned_handles_closed=False,
    )
    try:
        raw = (OUT / "ranker-runtime-files-notice-verified-01.jsonl").read_bytes()
        if hashlib.sha256(raw).hexdigest() != INVENTORY_SHA:
            raise ValueError("prior_inventory_hash_mismatch")
        rows = []
        for line in raw.splitlines():
            row = strict_json_loads(line, max_bytes=4096, require_object=True)
            name = Path(row["path"]).name.upper()
            rows.append(
                dict(
                    path=row["path"],
                    bytes=row["bytes"],
                    sha256=row["sha256"],
                    role="notice"
                    if name.startswith(("LICENSE", "COPYING", "NOTICE"))
                    else "runtime",
                )
            )
        runtime = CompactInventory.model_validate(
            dict(schema_version="compact_file_inventory_v1", kind="runtime", files=rows)
        )
        model = CompactInventory.model_validate(
            dict(
                schema_version="compact_file_inventory_v1",
                kind="model",
                files=[
                    dict(
                        path=name,
                        bytes=size,
                        sha256=sha,
                        role="weights"
                        if name == "model.safetensors"
                        else "notice"
                        if name == "README.md"
                        else "config"
                        if name == "config.json"
                        else "tokenizer",
                    )
                    for name, (size, sha) in PINNED.items()
                ],
            )
        )
        total = sum(r.bytes for r in (*model.files, *runtime.files))
        if total >= 1_500_000_000:
            raise ValueError("combined_size_limit")
        anchors = dict(
            package_runtime=selected_runtime_site().parents[1],
            python_runtime=Path(sys.base_prefix),
            supplemental_notices=NOTICE_DIRECTORY,
            model=OUT / "minilm-span-reader",
        )
        import psutil
        import win32file  # noqa: F401

        process = psutil.Process()
        before_handles = process.num_handles()
        with ExitStack() as stack:

            def check_deadline():
                if time.monotonic() - started > 600:
                    raise ValueError("compact_artifacts_time_budget_exceeded")

            locks = _WindowsLocks(stack, check_deadline)
            for kind, inventory in (("model", model), ("runtime", runtime)):
                for row in inventory.files:
                    report["last_selected_inventory_path"] = row.path
                    if kind == "model":
                        path = anchors["model"] / row.path
                    else:
                        label, relative = row.path.split("/", 1)
                        path = anchors[label] / relative
                    locks.verify_file(path, row)
                    report["files_verified"] += 1
                    report["bytes_verified"] += row.bytes
                    if report["files_verified"] % 2048 == 0:
                        print(
                            json.dumps(
                                dict(
                                    files_verified=report["files_verified"],
                                    total_files=len(model.files) + len(runtime.files),
                                )
                            ),
                            flush=True,
                        )
            report.update(
                passed=True,
                model_files=len(model.files),
                runtime_files=len(runtime.files),
                selected_bytes=total,
                native_handles_held=process.num_handles() - before_handles,
                directories_locked=len(locks.directories),
                peak_rss_bytes=process.memory_info().peak_wset,
                prior_inventory_sha256=INVENTORY_SHA,
            )
        report["owned_handles_closed"] = not stack._exit_callbacks
        report["handle_count_after_minus_before"] = process.num_handles() - before_handles
    except Exception as exc:
        report["failure_type"] = type(exc).__name__
        report["failure_os_code"] = getattr(exc, "winerror", None)
        # Never expose a local filename or arbitrary parser/OS exception text.
        report["failure_code"] = (
            str(exc) if str(exc).startswith("compact_artifacts_") else "locked_selection_failed"
        )
    if stack is not None:
        report["owned_handles_closed"] = not stack._exit_callbacks
    report["duration_seconds"] = round(time.monotonic() - started, 3)
    with target.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps(report), flush=True)
    return 0 if report["passed"] and report["owned_handles_closed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    raise SystemExit(run(parser.parse_args().run_id))
