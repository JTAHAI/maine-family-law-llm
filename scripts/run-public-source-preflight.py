#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.release.pre_push_gate import write_pre_push_gate  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run fail-closed public-source pre-push checks without claiming GA legal readiness.")
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=Path("docs/external-evidence/public_source_pre_push_gate_v193.json"))
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()

    report = write_pre_push_gate(args.repo_root, args.output)
    payload = report.as_dict()
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.require_ready and payload["status"] != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
