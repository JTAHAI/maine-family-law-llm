#!/usr/bin/env python3
"""Create a hash-bound isolated MSIX upgrade execution contract; never installs packages."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from legal.release.msix_upgrade_qualification import build_upgrade_execution_contract


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan an isolated MSIX upgrade qualification without installing anything.")
    parser.add_argument("--prior", required=True, help="Prior MSIX package path")
    parser.add_argument("--candidate", required=True, help="Candidate MSIX package path")
    parser.add_argument("--output", required=True, help="Output JSON contract path")
    args = parser.parse_args()
    contract = build_upgrade_execution_contract(args.prior, args.candidate)
    target = Path(args.output).resolve(); target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(contract, indent=2, sort_keys=True))
    return 0 if contract["status"] == "ready_for_isolated_execution" else 1


if __name__ == "__main__":
    raise SystemExit(main())
