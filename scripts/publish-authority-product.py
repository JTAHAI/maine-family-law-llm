#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.production.authority_product import AuthorityProductPublisher
from maine_family_law_llm.version import VERSION


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish an immutable verified external Maine authority generation.")
    parser.add_argument("--data-root", required=True)
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--product-version", default=VERSION)
    parser.add_argument("--no-activate", action="store_true")
    args = parser.parse_args()
    report = AuthorityProductPublisher(data_root=args.data_root, repo_root=args.repo_root).publish(
        product_version=args.product_version,
        activate=not args.no_activate,
    )
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    return 0 if report.status == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
