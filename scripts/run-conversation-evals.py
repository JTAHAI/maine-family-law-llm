#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.evals.conversation_eval import ConversationEvalRunner


def main() -> int:
    output = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else ROOT / "docs" / "external-evidence" / "pass47e_conversation_eval_report.json"
    )
    report = ConversationEvalRunner(project_root=ROOT).run(output_path=output)
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    return 0 if report.status == "pass" and all(report.hard_safety_checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
