#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.evals import FullReleaseEvalRunner
from legal.security import LegalRedTeamRunner


def main() -> int:
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "smoke_evidence_pass46_pass47_release_eval_red_team.json"
    release_eval = FullReleaseEvalRunner(project_root=ROOT, eval_root=ROOT / "eval_data").run(
        output_path=ROOT / "smoke_evidence_pass46_full_release_eval.json"
    )
    red_team = LegalRedTeamRunner(project_root=ROOT).run(
        output_path=ROOT / "smoke_evidence_pass47_legal_red_team.json"
    )
    evidence = {
        "stage": "enterprise_pass_46_47_full_release_eval_and_legal_red_team",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "checks": {
            "pass46_full_release_eval": release_eval.as_dict(),
            "pass47_legal_red_team": red_team.as_dict(),
        },
        "completed_passes": [46, 47],
        "status": "pass" if release_eval.status == "pass" and red_team.status == "pass" else "fail",
        "ship_decision": release_eval.ship_decision,
        "legal_readiness": (
            "Pass 46 produces a real ship/no-ship gate report; current repo evidence remains no_ship until live official-source freshness, attorney-reviewed gold minimums, and production metric thresholds are supplied. "
            "Pass 47 legal red-team suites pass the deterministic fail-safe harness and block filing-ready bypass attempts."
        ),
    }
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if evidence["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
