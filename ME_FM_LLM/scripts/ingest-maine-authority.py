#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.connectors import OfficialAuthorityIngestor, OfficialSourceFetcher, load_official_source_targets
from legal.connectors.official_source_catalog import load_source_targets_from_file
from legal.data_boundaries import StoreName


def _merge_manifest_records(existing: list[dict], incoming: list[dict]) -> list[dict]:
    """Merge authority manifest records while preserving first-seen order.

    Second-wave direct authority ingestion must not erase first-wave index
    snapshots.  Source IDs are stable per source URL/class, so newer records for
    the same source ID replace older records, while unique first-wave and
    follow-up records remain in one manifest for downstream parsing/indexing.
    """
    merged: dict[str, dict] = {}
    order: list[str] = []
    for index, record in enumerate(existing + incoming):
        if not isinstance(record, dict):
            continue
        key = str(
            record.get("source_id")
            or record.get("snapshot_path")
            or record.get("source_url_or_path")
            or f"manifest-row-{index}"
        )
        if key not in merged:
            order.append(key)
        merged[key] = record
    return [merged[key] for key in order]


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest official Maine authority snapshots.")
    parser.add_argument(
        "--data-root",
        type=Path,
        default=ROOT.parent / "maine-family-law-llm-data",
        help="External data root. Defaults outside the source repository.",
    )
    parser.add_argument(
        "--target-id",
        action="append",
        default=[],
        help="Limit ingestion to one or more target IDs from the selected source target catalog.",
    )
    parser.add_argument(
        "--target-catalog",
        type=Path,
        default=None,
        help="Optional JSON source-target catalog, for example official_authority_store/derived_authority_targets.json.",
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--retry-backoff", type=float, default=1.5)
    parser.add_argument(
        "--ignore-robots-txt",
        action="store_true",
        help="Do not check robots.txt. Intended only for controlled/internal mirrors.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Abort on first failed target instead of writing failed_sources.json and continuing.",
    )
    parser.add_argument(
        "--strict-content-type",
        action="store_true",
        help="Fail targets whose response content type/body does not match expected_content_type.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate target catalog and external data root without network fetches or snapshots.",
    )
    parser.add_argument(
        "--max-targets",
        type=int,
        default=None,
        help="Optional cap for smoke runs. Production builds should omit this.",
    )
    parser.add_argument(
        "--append-existing-manifest",
        action="store_true",
        help=(
            "Merge newly ingested sources into an existing official_authority_store/source_manifest.json "
            "instead of replacing it. Use for second-wave direct authority target ingests."
        ),
    )
    args = parser.parse_args()

    project_root = ROOT.resolve()
    data_root = args.data_root.resolve()
    try:
        data_root.relative_to(project_root)
    except ValueError:
        pass
    else:
        raise SystemExit(
            "Refusing to ingest official authority into the source repository. "
            "Use --data-root outside the repo."
        )

    targets = load_source_targets_from_file(args.target_catalog) if args.target_catalog else load_official_source_targets()
    if args.target_id:
        wanted = set(args.target_id)
        targets = [target for target in targets if target.target_id in wanted]
        missing = wanted - {target.target_id for target in targets}
        if missing:
            raise SystemExit(f"Unknown target IDs: {sorted(missing)}")
    if args.max_targets is not None:
        targets = targets[: max(0, args.max_targets)]

    target_problems = {target.target_id: target.validate() for target in targets if target.validate()}
    if args.dry_run:
        result = {
            "status": "pass" if not target_problems else "blocked",
            "mode": "dry_run",
            "target_count": len(targets),
            "target_ids": [target.target_id for target in targets],
            "target_problems": target_problems,
            "data_root": str(data_root),
            "official_store": str(data_root / StoreName.OFFICIAL_AUTHORITY.value),
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if not target_problems else 1
    if target_problems:
        raise SystemExit(f"Invalid source targets: {target_problems}")

    official_store = data_root / StoreName.OFFICIAL_AUTHORITY.value
    fetcher = OfficialSourceFetcher(
        timeout_seconds=args.timeout,
        min_delay_seconds=args.delay,
        max_retries=args.max_retries,
        retry_backoff_seconds=args.retry_backoff,
        respect_robots_txt=not args.ignore_robots_txt,
        strict_content_type=args.strict_content_type,
    )
    ingestor = OfficialAuthorityIngestor(fetcher=fetcher, snapshot_base_dir=official_store)
    ingested = ingestor.ingest_all(targets, continue_on_error=not args.fail_fast)
    manifest_records = [item.to_dict() for item in ingested]
    prior_manifest_count = 0
    if args.append_existing_manifest:
        manifest_path_candidate = official_store / "source_manifest.json"
        if manifest_path_candidate.exists():
            loaded = json.loads(manifest_path_candidate.read_text(encoding="utf-8"))
            if not isinstance(loaded, list):
                raise SystemExit("Existing source_manifest.json must be a JSON array before append.")
            prior_manifest_count = len(loaded)
            manifest_records = _merge_manifest_records(loaded, manifest_records)
    manifest_path = ingestor.write_manifest(manifest_records)
    failure_report_path = ingestor.write_failure_report()
    run_report_path = ingestor.write_ingest_run_report(ingested=ingested, manifest_path=manifest_path)

    result = {
        "status": "pass" if not ingestor.failed else "partial",
        "target_count": len(targets),
        "ingested_count": len(ingested),
        "failed_count": len(ingestor.failed),
        "manifest_path": str(manifest_path),
        "prior_manifest_count": prior_manifest_count,
        "manifest_record_count": len(manifest_records),
        "append_existing_manifest": bool(args.append_existing_manifest),
        "failure_report_path": str(failure_report_path),
        "run_report_path": str(run_report_path),
        "official_store": str(official_store),
        "sources": [item.to_dict() for item in ingested],
    }
    print(json.dumps(result, indent=2))
    return 0 if not ingestor.failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
