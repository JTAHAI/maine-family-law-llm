#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.production.followup_targets import AuthorityFollowupTargetBuilder


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Derive second-wave official authority targets from parsed Maine index snapshots."
    )
    parser.add_argument("--data-root", type=Path, required=True, help="External data root containing parsed_authority_store.")
    parser.add_argument("--max-targets", type=int, default=None, help="Optional cap for smoke/debug target catalogs.")
    parser.add_argument("--no-write", action="store_true", help="Print report only; do not write derived_authority_targets.json.")
    args = parser.parse_args()

    report = AuthorityFollowupTargetBuilder(data_root=args.data_root).build(
        write=not args.no_write,
        max_targets=args.max_targets,
    )
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    return 0 if report.status == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
