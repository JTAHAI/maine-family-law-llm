#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.evals import ReleaseMetricMeasurementTemplateBuilder


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an external task-specific release metric measurement template.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = ReleaseMetricMeasurementTemplateBuilder().write(args.output)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
