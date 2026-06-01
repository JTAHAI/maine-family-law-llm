#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.authority_store import ParsedAuthorityStoreAuditor


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit parsed authority JSONL store.")
    parser.add_argument("--data-root", type=Path, required=True, help="External data root.")
    parser.add_argument(
        "--require-direct-authority",
        action="store_true",
        help="Require direct statute sections, forms, and Law Court opinions, not just first-wave indexes.",
    )
    args = parser.parse_args()
    report = ParsedAuthorityStoreAuditor(
        data_root=args.data_root,
        require_direct_authority=args.require_direct_authority,
    ).run()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
