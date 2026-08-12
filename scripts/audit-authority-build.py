#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.production import AuthorityBuildAuditor


def _human_report(report: dict[str, object]) -> str:
    lines = [
        f"Status: {report.get('status', 'unknown')}",
        f"Ready: {report.get('production_ready', False)}",
        f"Build: {report.get('build_id', '')}",
        f"Records: {report.get('total_records', 0)}",
        f"Parsed: {report.get('parsed_records', 0)}",
        f"Snapshot-only: {report.get('snapshot_only_records', 0)}",
    ]
    blockers = report.get("blockers") or []
    if isinstance(blockers, list) and blockers:
        lines.append("Blockers:")
        for blocker in blockers:
            lines.append(f"  - {blocker}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit external official-authority build readiness.")
    parser.add_argument("--data-root", type=Path, required=True, help="External data root.")
    parser.add_argument("--human-report", action="store_true", help="Emit a readable summary after the JSON report.")
    args = parser.parse_args()
    report = AuthorityBuildAuditor(project_root=ROOT, data_root=args.data_root).run().as_dict()
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.human_report:
        print(_human_report(report))
    return 0 if report.get("production_ready") else 2


if __name__ == "__main__":
    raise SystemExit(main())
