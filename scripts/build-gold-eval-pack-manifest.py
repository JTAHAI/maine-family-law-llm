#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.evals import GoldEvalPackManifestBuilder


def main() -> int:
    parser = argparse.ArgumentParser(description="Build gold eval pack manifest from audited JSONL datasets.")
    parser.add_argument("--eval-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Exit non-zero unless the manifest shows production-ready attorney-reviewed gold data.",
    )
    args = parser.parse_args()
    manifest = GoldEvalPackManifestBuilder(project_root=ROOT).build(
        eval_root=args.eval_root,
        output_path=args.output,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    if args.require_ready and not manifest.get("production_ready"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
