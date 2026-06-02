#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.release.git_safe_push import run_git_safe_push, write_git_safe_push_report  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run source-hygiene gates, focused tests, and a no-op-safe git commit/push. Does not claim legal GA readiness."
    )
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--message", default="Run public-source pre-push gate")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    report = run_git_safe_push(
        args.repo_root,
        message=args.message,
        branch=args.branch,
        skip_tests=args.skip_tests,
        dry_run=args.dry_run,
    )
    payload = report.as_dict()
    if args.output is not None:
        write_git_safe_push_report(report, args.output)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
