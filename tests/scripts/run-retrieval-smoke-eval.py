#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.evals.retrieval_smoke import RetrievalSmokeEvalRunner


def main() -> int:
    parser = argparse.ArgumentParser(description="Run measured retrieval smoke eval over indexed Maine authority.")
    parser.add_argument("--data-root", required=True, help="External data root with embedding_store indexes.")
    parser.add_argument("--eval-root", default=None, help="External eval root. Defaults to <data-root>/eval_store.")
    args = parser.parse_args()
    report = RetrievalSmokeEvalRunner(data_root=args.data_root, eval_root=args.eval_root).run(write_report=True)
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    return 0 if report.status == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
