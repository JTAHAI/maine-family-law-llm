#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.production.repo_ga_evidence import RepoGAEvidenceBuilder


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate repo-local evidence for repo-only true-GA passes 39 and 40.")
    parser.add_argument("--check", action="store_true", help="Do not write files; only report status.")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON summary output path.")
    args = parser.parse_args()
    result = RepoGAEvidenceBuilder(project_root=ROOT).build(write=not args.check)
    payload = result.as_dict()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if result.status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
