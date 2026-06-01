#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.production.retrieval_index_audit import RetrievalIndexAuditor


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit external Maine retrieval index artifacts.")
    parser.add_argument("--data-root", type=Path, required=True, help="External data root containing embedding_store.")
    parser.add_argument("--repo-root", type=Path, default=ROOT, help="Source repo root used to block in-repo index stores.")
    parser.add_argument(
        "--require-direct-lookups",
        action="store_true",
        help="Require non-empty exact citation, statute, form, and case lookup artifacts.",
    )
    args = parser.parse_args()
    report = RetrievalIndexAuditor(data_root=args.data_root, repo_root=args.repo_root).audit(
        require_direct_lookups=args.require_direct_lookups
    )
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    return 0 if report.status == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
