#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.release.post_ga_review import PostGARepoReviewer  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run post-Pass-51 repo reality review and build-path audit.")
    parser.add_argument("--data-root", default="/mnt/data/maine-family-law-llm-data")
    parser.add_argument("--eval-root", default=None)
    parser.add_argument("--output", default="post_ga_repo_review_build_path.json")
    args = parser.parse_args()

    reviewer = PostGARepoReviewer(project_root=ROOT, data_root=args.data_root, eval_root=args.eval_root)
    report = reviewer.review(output_path=ROOT / args.output)
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    return 0 if report.status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
