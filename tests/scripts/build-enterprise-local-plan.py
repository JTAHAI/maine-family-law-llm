#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.resources import EnterpriseResourcePlanBuilder


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a Windows-first local enterprise build plan.")
    parser.add_argument("--repo-root", type=Path, default=Path(r"C:\dev\ME_FM_LLM"))
    parser.add_argument("--data-root", type=Path, default=Path(r"C:\dev\ME_FM_LLM_data"))
    parser.add_argument("--output", type=Path, default=ROOT / "enterprise_local_build_plan.json")
    args = parser.parse_args()
    plan = EnterpriseResourcePlanBuilder(project_root=ROOT).build(
        repo_root=args.repo_root,
        data_root=args.data_root,
    )
    args.output.write_text(json.dumps(plan, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(plan, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
