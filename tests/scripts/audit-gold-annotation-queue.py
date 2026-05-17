#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.evals import GoldAnnotationQueueAuditor


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit an attorney annotation queue JSONL file.")
    parser.add_argument("--queue", type=Path, required=True)
    args = parser.parse_args()
    report = GoldAnnotationQueueAuditor().audit(args.queue)
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    return 0 if report.status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
