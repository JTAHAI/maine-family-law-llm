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


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit external official-authority build readiness.")
    parser.add_argument("--data-root", type=Path, required=True, help="External data root.")
    args = parser.parse_args()
    report = AuthorityBuildAuditor(project_root=ROOT, data_root=args.data_root).run()
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    return 0 if report.production_ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
