#!/usr/bin/env python3
"""Audit installed project dependencies against offline security floors."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT, ROOT / "src"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from legal.security.dependency_floor import audit_dependency_floors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-api", action="store_true", help="Skip optional API packages")
    parser.add_argument("--include-build", action="store_true", help="Check Store build packages")
    parser.add_argument(
        "--strict-optional",
        action="store_true",
        help="Fail when an optional package is not installed",
    )
    args = parser.parse_args(argv)
    report = audit_dependency_floors(
        include_api=not args.no_api,
        include_build=args.include_build,
        strict_optional=args.strict_optional,
    )
    print(json.dumps(report.to_dict(), indent=2))
    return 0 if report.status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
