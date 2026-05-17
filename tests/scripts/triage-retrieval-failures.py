#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.production.retrieval_failure_triage import RetrievalFailureTriage


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify retrieval smoke/gold failures and emit fix tickets.")
    parser.add_argument("--data-root", required=True, help="External data root with embedding_store indexes.")
    parser.add_argument("--eval-root", default=None, help="External eval root. Defaults to <data-root>/eval_store.")
    parser.add_argument("--smoke-report", default=None, help="Optional path to retrieval_smoke_eval.json.")
    args = parser.parse_args()
    report = RetrievalFailureTriage(data_root=args.data_root, eval_root=args.eval_root).run(
        smoke_report_path=args.smoke_report,
        write_report=True,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
