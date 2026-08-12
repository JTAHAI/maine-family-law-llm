#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from legal.ops.release_pilot_hardening import MatterBackupRestoreDrill


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an isolated matter backup/restore rehearsal.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--case-root", required=True)
    parser.add_argument("--backup-root", required=True)
    parser.add_argument("--release-evidence-root")
    parser.add_argument("--approved", action="store_true")
    args = parser.parse_args()
    report = MatterBackupRestoreDrill(
        args.case_root,
        repo_root=args.repo_root,
        backup_root=args.backup_root,
        release_evidence_root=args.release_evidence_root,
    ).run(approved=args.approved)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
