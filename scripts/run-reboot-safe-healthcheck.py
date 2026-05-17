#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.ops.reboot_recovery import RebootRecoveryAuditor


def main() -> int:
    parser = argparse.ArgumentParser(description="Run reboot-safe local enterprise health checks.")
    parser.add_argument("--repo-root", default=str(ROOT), help="Source repository root. Defaults to this checkout.")
    parser.add_argument("--data-root", default=None, help="External data root, e.g. C:\\dev\\ME_FM_LLM_data.")
    parser.add_argument("--output", default="reboot_recovery_healthcheck.json", help="Output JSON path.")
    parser.add_argument("--no-create-dirs", action="store_true", help="Do not create external data-root directories.")
    parser.add_argument("--no-write-probe", action="store_true", help="Skip external data-root write probe.")
    args = parser.parse_args()

    auditor = RebootRecoveryAuditor(args.repo_root, args.data_root)
    report = auditor.write(
        args.output,
        create_external_dirs=not args.no_create_dirs,
        write_probe=not args.no_write_probe,
    )
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    return 0 if report.status == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
