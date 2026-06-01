#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.ops import EnterprisePreflightRunner


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Windows-first enterprise local preflight.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--data-root", default=None)
    parser.add_argument("--output", default=str(ROOT / "docs" / "sample-evidence" / "enterprise_preflight_report.json"))
    parser.add_argument("--no-create", action="store_true", help="Do not create external data directories.")
    args = parser.parse_args()
    report = EnterprisePreflightRunner(repo_root=args.repo_root, data_root=args.data_root).write(
        args.output,
        create_external_dirs=not args.no_create,
    )
    print(report.as_dict())
    return 0 if report.status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
