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
from legal.data_boundaries import StoreName


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
        help="Limit ingestion to one or more target IDs from configs/maine_official_source_targets.json.",
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
        "--max-targets",
        type=int,
        default=None,
        help="Optional cap for smoke runs. Production builds should omit this.",
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

    targets = load_official_source_targets()
    if args.target_id:
        wanted = set(args.target_id)
        targets = [target for target in targets if target.target_id in wanted]
        missing = wanted - {target.target_id for target in targets}
        if missing:
            raise SystemExit(f"Unknown target IDs: {sorted(missing)}")
    if args.max_targets is not None:
        targets = targets[: max(0, args.max_targets)]

    official_store = data_root / StoreName.OFFICIAL_AUTHORITY.value
    fetcher = OfficialSourceFetcher(
        timeout_seconds=args.timeout,
        min_delay_seconds=args.delay,
        max_retries=args.max_retries,
        retry_backoff_seconds=args.retry_backoff,
        respect_robots_txt=not args.ignore_robots_txt,
    )
    ingestor = OfficialAuthorityIngestor(fetcher=fetcher, snapshot_base_dir=official_store)
    ingested = ingestor.ingest_all(targets, continue_on_error=not args.fail_fast)
    manifest_path = ingestor.write_manifest(ingested)
    failure_report_path = ingestor.write_failure_report()
    run_report_path = ingestor.write_ingest_run_report(ingested=ingested, manifest_path=manifest_path)

    result = {
        "status": "pass" if not ingestor.failed else "partial",
        "target_count": len(targets),
        "ingested_count": len(ingested),
        "failed_count": len(ingestor.failed),
        "manifest_path": str(manifest_path),
        "failure_report_path": str(failure_report_path),
        "run_report_path": str(run_report_path),
        "official_store": str(official_store),
        "sources": [item.to_dict() for item in ingested],
    }
    print(json.dumps(result, indent=2))
    return 0 if not ingestor.failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
