#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.pilot import write_launch_evidence_starter_kit  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create fail-closed external evidence templates for Passes 48-51. Does not create signoff."
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("external_evidence_starter/pass48_51_launch"),
        help="Output directory outside the source repo in real use.",
    )
    args = parser.parse_args()
    manifest = write_launch_evidence_starter_kit(args.output_root)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
