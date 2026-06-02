#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.pilot import write_attorney_sandbox_review_kit  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a fail-closed attorney sandbox review kit for Pass 48. Does not create signoff."
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("external_evidence_starter/pass48_attorney_sandbox_review"),
        help="Output directory outside the source repo in real use.",
    )
    parser.add_argument(
        "--max-questions",
        type=int,
        default=48,
        help="Maximum public/synthetic chat-library questions to queue for attorney review.",
    )
    args = parser.parse_args()
    manifest = write_attorney_sandbox_review_kit(args.output_root, max_questions=args.max_questions)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
