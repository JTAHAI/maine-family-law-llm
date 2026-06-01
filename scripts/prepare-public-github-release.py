#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.release import PublicRepoReadinessAuditor


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit source tree readiness for public GitHub staging.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--output", default=str(ROOT / "docs" / "sample-evidence" / "public_release_readiness.json"))
    args = parser.parse_args()
    report = PublicRepoReadinessAuditor(project_root=args.project_root).write(args.output)
    print(report.as_dict())
    return 0 if report.status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
