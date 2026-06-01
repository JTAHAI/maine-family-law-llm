#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.release import (  # noqa: E402
    GAShipmentAuditor,
    ReleaseBlocker,
    ReleaseCandidateAuditor,
    build_approved_signoff_fixture,
    build_ga_control_fixture,
    build_release_artifact_fixture,
)


def build_evidence(output_path: Path) -> dict:
    version = "1.18.0-pass50-pass51-ga-release-controls"
    rc_artifacts, ga_artifacts = build_release_artifact_fixture(version)
    signoffs = build_approved_signoff_fixture()

    release_candidate = ReleaseCandidateAuditor(project_root=ROOT).audit(
        version=version,
        artifacts=rc_artifacts,
        signoffs=signoffs,
        blockers=[],
        audit_enterprise_readiness_status="pass",
        output_path=ROOT / "docs" / "sample-evidence" / "smoke_evidence_pass50_release_candidate.json",
    )
    ga_shipment = GAShipmentAuditor().audit(
        version=version,
        release_candidate_report=release_candidate,
        artifacts=ga_artifacts,
        controls=build_ga_control_fixture(),
        output_path=ROOT / "docs" / "sample-evidence" / "smoke_evidence_pass51_ga_shipment.json",
    )

    blocked_candidate = ReleaseCandidateAuditor(project_root=ROOT).audit(
        version=version,
        artifacts=rc_artifacts[:-1],
        signoffs=signoffs[:-1],
        blockers=[
            ReleaseBlocker(
                blocker_id="P1-live-official-corpus-not-attached",
                severity="P1",
                status="open",
                description="Demonstrates that missing final artifacts/signoffs/open blockers stop a release candidate.",
            )
        ],
        audit_enterprise_readiness_status="blocked",
    )
    blocked_ga = GAShipmentAuditor().audit(
        version=version,
        release_candidate_report=blocked_candidate,
        artifacts=ga_artifacts,
        controls={**build_ga_control_fixture(), "uses_real_official_maine_authority": False},
    )

    evidence = {
        "stage": "pass_50_pass_51_ga_release_candidate_and_shipment_controls",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "release_candidate_fixture": release_candidate.as_dict(),
        "ga_shipment_fixture": ga_shipment.as_dict(),
        "blocked_release_candidate_fixture": blocked_candidate.as_dict(),
        "blocked_ga_fixture": blocked_ga.as_dict(),
        "status": "pass"
        if release_candidate.status == "pass"
        and release_candidate.release_candidate_frozen
        and ga_shipment.status == "pass"
        and ga_shipment.ga_shipped
        and blocked_candidate.status == "blocked"
        and blocked_ga.status == "blocked"
        else "fail",
        "readiness_note": (
            "Pass 50-51 release controls are implemented. Fixture evidence proves the gates can pass with explicit versioned artifacts/signoffs "
            "and block without them. Production GA still requires real external manifests, attorney-reviewed evals, live official authority, pilot evidence, and owner signoffs."
        ),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Pass 50-51 GA release evidence.")
    parser.add_argument("output", nargs="?", default=str(ROOT / "docs" / "sample-evidence" / "smoke_evidence_pass50_pass51_ga_release.json"))
    args = parser.parse_args()
    evidence = build_evidence(ROOT / args.output)
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if evidence["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
