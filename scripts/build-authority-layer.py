#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.authority_store.authority_layer import ParsedAuthorityIndexBuilder


def main() -> int:
    parser = argparse.ArgumentParser(description="Build citation index, source cards, and authority graph from parsed Maine authority.")
    parser.add_argument("--data-root", required=True, help="External authority data root.")
    args = parser.parse_args()
    report = ParsedAuthorityIndexBuilder(data_root=args.data_root).build(write=True)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
