#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.conversation.internal_passes import ConversationPilotReadinessAuditor


def main() -> int:
    output = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else ROOT / "docs" / "external-evidence" / "pass47a_47h_conversation_pilot_readiness_summary.json"
    )
    report = ConversationPilotReadinessAuditor(ROOT).write(output, run_tests=True)
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    return 0 if report.status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
