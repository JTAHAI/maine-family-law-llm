#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.resources import EnterpriseResourceAuditor


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit external enterprise resource collection outputs.")
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path(r"C:\dev\ME_FM_LLM_data") if sys.platform.startswith("win") else ROOT.parent / "ME_FM_LLM_data",
    )
    args = parser.parse_args()
    report = EnterpriseResourceAuditor(project_root=ROOT, data_root=args.data_root).audit()
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    return 0 if report.production_ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
