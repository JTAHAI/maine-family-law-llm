#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.pilot import LaunchEvidenceGate


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit external launch/GA evidence for Passes 48-51 without fabricating signoff.")
    parser.add_argument("--pilot-root", type=Path, required=True)
    parser.add_argument("--release-root", type=Path)
    parser.add_argument("--output", type=Path, default=Path("docs/external-evidence/pass48_51_launch_evidence_gate_report.json"))
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()

    report = LaunchEvidenceGate().audit(pilot_root=args.pilot_root, release_root=args.release_root)
    payload = report.as_dict()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.require_ready and payload["status"] != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
