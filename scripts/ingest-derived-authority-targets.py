#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _load_catalog(path: Path) -> list[dict[str, Any]]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(loaded, dict):
        rows = loaded.get("targets", [])
    elif isinstance(loaded, list):
        rows = loaded
    else:
        raise SystemExit("Derived target catalog must be a JSON object with targets or a JSON array.")
    if not isinstance(rows, list):
        raise SystemExit("Derived target catalog targets must be a list.")
    return [row for row in rows if isinstance(row, dict) and row.get("target_id")]


def _manifest_target_ids(data_root: Path) -> set[str]:
    manifest = data_root / "official_authority_store" / "source_manifest.json"
    if not manifest.exists():
        return set()
    loaded = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(loaded, list):
        raise SystemExit("Existing source_manifest.json must be a JSON array before resumable ingest.")
    target_ids: set[str] = set()
    for row in loaded:
        if not isinstance(row, dict):
            continue
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        target_id = metadata.get("target_id")
        if target_id:
            target_ids.add(str(target_id))
    return target_ids


def _quarantine_path(data_root: Path) -> Path:
    return data_root / "official_authority_store" / "derived_authority_quarantine.json"


def _load_quarantined_target_ids(data_root: Path) -> set[str]:
    path = _quarantine_path(data_root)
    if not path.exists():
        return set()
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    failures = loaded.get("failures", []) if isinstance(loaded, dict) else []
    ids: set[str] = set()
    if isinstance(failures, list):
        for row in failures:
            if isinstance(row, dict) and row.get("target_id"):
                ids.add(str(row["target_id"]))
    return ids


def _chunks(items: list[str], size: int) -> list[list[str]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def _tail(value: str, limit: int = 4000) -> str:
    return value[-limit:] if value else ""


def _failure_report_path(parsed: Any) -> Path | None:
    if not isinstance(parsed, dict):
        return None
    value = parsed.get("failure_report_path")
    if not value:
        return None
    return Path(str(value))


def _read_failure_report(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    failures = loaded.get("failures", []) if isinstance(loaded, dict) else []
    return [row for row in failures if isinstance(row, dict)]


def _merge_quarantine(existing: list[dict[str, Any]], new_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for row in existing + new_rows:
        target_id = str(row.get("target_id") or "")
        if not target_id:
            continue
        merged[target_id] = row
    return [merged[key] for key in sorted(merged)]


def _write_quarantine(data_root: Path, new_failures: list[dict[str, Any]]) -> Path:
    path = _quarantine_path(data_root)
    existing: list[dict[str, Any]] = []
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            prior = loaded.get("failures", []) if isinstance(loaded, dict) else []
            existing = [row for row in prior if isinstance(row, dict)]
        except json.JSONDecodeError:
            existing = []
    failures = _merge_quarantine(existing, new_failures)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "status": "quarantined" if failures else "pass",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "failure_count": len(failures),
                "failures": failures,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path


def _failure_summary(row: dict[str, Any], *, batch_number: int) -> dict[str, Any]:
    attempts = row.get("attempts") if isinstance(row.get("attempts"), list) else []
    last_attempt = attempts[-1] if attempts and isinstance(attempts[-1], dict) else {}
    return {
        "batch_number": batch_number,
        "target_id": str(row.get("target_id") or ""),
        "source_class": str(row.get("source_class") or ""),
        "parser_name": str(row.get("parser_name") or ""),
        "url": str(row.get("url") or ""),
        "failure_code": str(row.get("failure_code") or ""),
        "message": str(row.get("message") or last_attempt.get("message") or ""),
        "status_code": row.get("status_code", last_attempt.get("status_code")),
        "failed_at": str(row.get("failed_at") or ""),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingest derived official authority targets in resumable chunks so large second-wave runs do not time out."
    )
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--target-catalog", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--retry-backoff", type=float, default=1.5)
    parser.add_argument("--strict-content-type", action="store_true")
    parser.add_argument("--max-targets", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=75)
    parser.add_argument("--batch-timeout", type=int, default=600)
    parser.add_argument("--append-existing-manifest", action="store_true", default=True)
    parser.add_argument("--no-resume", action="store_true", help="Do not skip target IDs already present in source_manifest.json.")
    parser.add_argument(
        "--quarantine-failed-targets",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Persist failed derived targets and continue when failures stay within bounded tolerance.",
    )
    parser.add_argument("--retry-quarantined", action="store_true", help="Retry previously quarantined derived targets.")
    parser.add_argument("--max-quarantined-targets", type=int, default=25)
    parser.add_argument("--max-quarantine-rate", type=float, default=0.02)
    args = parser.parse_args()

    data_root = args.data_root.expanduser().resolve()
    catalog = args.target_catalog.expanduser().resolve()
    rows = _load_catalog(catalog)
    all_ids = [str(row["target_id"]) for row in rows]
    if args.max_targets is not None:
        all_ids = all_ids[: max(0, args.max_targets)]
    already = set() if args.no_resume else _manifest_target_ids(data_root)
    previously_quarantined = set() if args.retry_quarantined else _load_quarantined_target_ids(data_root)
    excluded = already.union(previously_quarantined)
    pending = [target_id for target_id in all_ids if target_id not in excluded]
    batches = _chunks(pending, max(1, args.batch_size))

    batch_reports: list[dict[str, Any]] = []
    total_ingested = 0
    total_failed = 0
    quarantined_failures: list[dict[str, Any]] = []
    hard_blocked = False
    hard_block_reasons: list[str] = []
    for batch_number, batch_ids in enumerate(batches, start=1):
        cmd = [
            sys.executable,
            str(ROOT / "scripts" / "ingest-maine-authority.py"),
            "--data-root",
            str(data_root),
            "--target-catalog",
            str(catalog),
            "--timeout",
            str(args.timeout),
            "--delay",
            str(args.delay),
            "--max-retries",
            str(args.max_retries),
            "--retry-backoff",
            str(args.retry_backoff),
            "--append-existing-manifest",
        ]
        if args.strict_content_type:
            cmd.append("--strict-content-type")
        for target_id in batch_ids:
            cmd.extend(["--target-id", target_id])
        try:
            completed = subprocess.run(
                cmd,
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=args.batch_timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            batch_reports.append(
                {
                    "batch_number": batch_number,
                    "status": "blocked",
                    "error": f"timeout after {args.batch_timeout}s",
                    "target_count": len(batch_ids),
                    "target_ids": batch_ids,
                    "stdout_tail": _tail(exc.stdout or ""),
                    "stderr_tail": _tail(exc.stderr or ""),
                }
            )
            hard_blocked = True
            hard_block_reasons.append(f"batch {batch_number} timed out")
            break
        parsed: Any | None = None
        try:
            parsed = json.loads(completed.stdout) if completed.stdout.strip() else None
        except json.JSONDecodeError:
            parsed = None
        batch_ingested = int(parsed.get("ingested_count") or 0) if isinstance(parsed, dict) else 0
        batch_failed = int(parsed.get("failed_count") or 0) if isinstance(parsed, dict) else 0
        total_ingested += batch_ingested
        total_failed += batch_failed
        failed_rows = [_failure_summary(row, batch_number=batch_number) for row in _read_failure_report(_failure_report_path(parsed))]
        failed_rows = [row for row in failed_rows if row.get("target_id")]
        if completed.returncode == 0:
            status = "pass"
        elif args.quarantine_failed_targets and batch_failed > 0:
            status = "partial_quarantined"
            quarantined_failures.extend(failed_rows)
        else:
            status = "blocked"
            hard_blocked = True
            hard_block_reasons.append(f"batch {batch_number} returned {completed.returncode}")
        batch_reports.append(
            {
                "batch_number": batch_number,
                "status": status,
                "returncode": completed.returncode,
                "target_count": len(batch_ids),
                "target_ids": batch_ids,
                "parsed_stdout": parsed,
                "quarantined_target_ids": [row["target_id"] for row in failed_rows] if status == "partial_quarantined" else [],
                "stdout_tail": _tail(completed.stdout),
                "stderr_tail": _tail(completed.stderr),
            }
        )
        if hard_blocked:
            break

    quarantine_path: Path | None = None
    if quarantined_failures:
        quarantine_path = _write_quarantine(data_root, quarantined_failures)

    total_quarantined_ids = previously_quarantined.union({row["target_id"] for row in quarantined_failures if row.get("target_id")})
    selected_count = max(1, len(all_ids))
    quarantine_rate = len(total_quarantined_ids.intersection(set(all_ids))) / selected_count
    quarantine_limited = (
        len(total_quarantined_ids.intersection(set(all_ids))) > args.max_quarantined_targets
        or quarantine_rate > args.max_quarantine_rate
    )
    if quarantine_limited:
        hard_blocked = True
        hard_block_reasons.append("quarantine limits exceeded")

    blocked_batches = [item for item in batch_reports if item.get("status") == "blocked"]
    result = {
        "status": "blocked" if hard_blocked else "pass",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_root": str(data_root),
        "target_catalog": str(catalog),
        "catalog_target_count": len(rows),
        "selected_target_count": len(all_ids),
        "already_ingested_count": len(already.intersection(set(all_ids))),
        "previously_quarantined_count": len(previously_quarantined.intersection(set(all_ids))),
        "pending_target_count": len(pending),
        "batch_size": max(1, args.batch_size),
        "batch_timeout": args.batch_timeout,
        "batch_count": len(batches),
        "completed_batch_count": sum(1 for item in batch_reports if item.get("status") in {"pass", "partial_quarantined"}),
        "ingested_count": total_ingested,
        "failed_count": total_failed,
        "quarantined_count": len({row["target_id"] for row in quarantined_failures if row.get("target_id")}),
        "total_quarantined_count": len(total_quarantined_ids.intersection(set(all_ids))),
        "quarantine_rate": quarantine_rate,
        "quarantine_path": str(quarantine_path) if quarantine_path else str(_quarantine_path(data_root)),
        "block_reasons": hard_block_reasons,
        "blocked_batches": blocked_batches,
        "batches": batch_reports,
    }
    report_path = data_root / "official_authority_store" / "derived_authority_ingest_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    result["run_report_path"] = str(report_path)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
