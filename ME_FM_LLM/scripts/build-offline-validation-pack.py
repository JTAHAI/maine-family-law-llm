#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.resources import OfflineValidationPackBuilder


def main() -> int:
    parser = argparse.ArgumentParser(description="Build external offline validation fixture pack.")
    parser.add_argument("--data-root", required=True)
    parser.add_argument("--output", default=str(ROOT / "docs" / "sample-evidence" / "offline_validation_pack_report.json"))
    args = parser.parse_args()
    report = OfflineValidationPackBuilder(data_root=args.data_root).write(args.output)
    print(report.as_dict())
    return 0 if report.status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
