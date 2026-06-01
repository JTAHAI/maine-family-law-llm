#!/usr/bin/env python3
"""Audit release-tree artifacts before packaging."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.production.release_artifact_audit import ReleaseArtifactAudit


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit generated artifacts and external-data leaks in the repo tree.")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--require-ready", action="store_true", help="Exit non-zero when the release tree is not package-clean.")
    args = parser.parse_args()
    report = ReleaseArtifactAudit(Path(args.repo_root)).audit()
    print(json.dumps(report, indent=2))
    if args.require_ready and report["status"] != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
