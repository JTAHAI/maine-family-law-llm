#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from legal.ops.release_pilot_hardening import ReleaseEvidenceAuditor


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit external v5.13 release-hardening evidence.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--evidence-root", required=True)
    parser.add_argument("--output")
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()
    report = ReleaseEvidenceAuditor(args.repo_root, args.evidence_root).audit()
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text, end="")
    return 1 if args.require_ready and report.get("status") != "pass" else 0


if __name__ == "__main__":
    raise SystemExit(main())
