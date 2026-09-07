"""Validate the canonical feature truth ledger without claiming release readiness."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.release.feature_truth import FeatureTruthError, feature_truth_inventory  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "configs" / "release_feature_truth.json",
    )
    args = parser.parse_args()
    try:
        report = feature_truth_inventory(args.manifest)
    except FeatureTruthError as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps({"status": "pass", "report": report}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
