#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.ops import OperatorHandoffBundleBuilder


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a single local-operator handoff JSON bundle.")
    parser.add_argument("--data-root", default=None, help="External data root. Defaults to policy Windows data root.")
    parser.add_argument("--output", default=str(ROOT / "operator_handoff_bundle.json"))
    args = parser.parse_args()
    report = OperatorHandoffBundleBuilder(ROOT, args.data_root).write(args.output)
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    return 0 if report.status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
