#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.resources import EnterpriseResourceCollector


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect Maine family-law enterprise research/legal resources into an external data root."
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path(r"C:\dev\ME_FM_LLM_data") if sys.platform.startswith("win") else ROOT.parent / "ME_FM_LLM_data",
        help="External local data root. Default is C:\\dev\\ME_FM_LLM_data on Windows or ../ME_FM_LLM_data elsewhere.",
    )
    parser.add_argument("--resource-id", action="append", default=[], help="Collect only selected resource IDs.")
    parser.add_argument("--source-class", action="append", default=[], help="Collect only selected source classes.")
    parser.add_argument("--max-resources", type=int, default=None, help="Optional smoke-run cap.")
    parser.add_argument("--timeout", type=float, default=None)
    parser.add_argument("--delay", type=float, default=None)
    parser.add_argument("--max-retries", type=int, default=None)
    parser.add_argument("--ignore-robots-txt", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Write planned manifest without downloading.")
    parser.add_argument("--fail-fast", action="store_true", help="Stop after the first failed resource.")
    args = parser.parse_args()

    collector = EnterpriseResourceCollector(
        project_root=ROOT,
        data_root=args.data_root,
        timeout_seconds=args.timeout,
        delay_seconds=args.delay,
        max_retries=args.max_retries,
        respect_robots_txt=not args.ignore_robots_txt,
    )
    report = collector.collect(
        resource_ids=args.resource_id,
        source_classes=args.source_class,
        max_resources=args.max_resources,
        dry_run=args.dry_run,
        continue_on_error=not args.fail_fast,
    )
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    return 0 if report.status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
