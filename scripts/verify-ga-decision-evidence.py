#!/usr/bin/env python3
"""Check release evidence without authorizing publication."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from legal.release.enterprise_ga_closure import EnterpriseDecisionPacket


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    result = EnterpriseDecisionPacket(project_root=root).assemble(evidence_root=args.evidence_root)
    print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    return 0 if result.as_dict()["ga_eligible"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
