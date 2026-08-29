#!/usr/bin/env python3
"""Prepare a hash-bound isolated rollback rehearsal plan; never changes packages or data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from legal.release.rollback_preparation import build_rollback_preparation


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a non-destructive MSIX rollback rehearsal plan.")
    parser.add_argument("--candidate", required=True, help="Current candidate MSIX package")
    parser.add_argument("--rollback", required=True, help="Compatible fallback MSIX package")
    parser.add_argument("--backup-evidence", help="Hash-bound isolated fictional backup/restore evidence JSON")
    parser.add_argument("--output", required=True, help="Output JSON plan")
    args = parser.parse_args()
    plan = build_rollback_preparation(candidate_package=args.candidate, rollback_package=args.rollback, backup_evidence=args.backup_evidence)
    target = Path(args.output).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(plan, indent=2, sort_keys=True))
    return 0 if plan["status"] == "prepared_for_isolated_rollback_rehearsal" else 1


if __name__ == "__main__":
    raise SystemExit(main())
