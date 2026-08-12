#!/usr/bin/env python3
"""Operate and audit the external v5.17 limited real-matter pilot.

The utility records only opaque identifiers, hashes, and enumerated control
outcomes. It never validates consent or licensure and never marks Pass 49
complete.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.pilot.real_matter_operations import (  # noqa: E402
    LimitedRealMatterPilotError,
    LimitedRealMatterPilotOperationsStore,
)


def _store(args: argparse.Namespace) -> LimitedRealMatterPilotOperationsStore:
    return LimitedRealMatterPilotOperationsStore(args.repo_root, args.pilot_root)


def _csv(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _hash_map(path: Path) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("artifact_hash_file_must_be_object")
    return {str(key): str(value) for key, value in payload.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run fail-closed v5.17 real-matter pilot operations.")
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--pilot-root", type=Path, required=True, help="External limited-pilot root.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status")

    program = sub.add_parser("create-program")
    program.add_argument("--program-id", required=True)
    program.add_argument("--tenant-ids", required=True, help="Comma-separated opaque tenant IDs.")
    program.add_argument("--pass48-evidence-sha256", required=True)

    enroll = sub.add_parser("enroll-matter")
    enroll.add_argument("--matter-id", required=True)
    enroll.add_argument("--tenant-id", required=True)
    enroll.add_argument("--participant-id", required=True)
    enroll.add_argument("--consent-version", required=True)
    enroll.add_argument("--client-consent-sha256", required=True)
    enroll.add_argument("--privacy-notice-sha256", required=True)
    enroll.add_argument("--matter-store-sha256", required=True)
    enroll.add_argument("--isolation-evidence-sha256", required=True)
    enroll.add_argument("--encryption-evidence-sha256", required=True)
    enroll.add_argument("--retention-policy-version", required=True)

    work = sub.add_parser("record-work-product")
    work.add_argument("--matter-id", required=True)
    work.add_argument("--artifact-hashes-json", type=Path, required=True)

    review = sub.add_parser("record-daily-review")
    review.add_argument("--matter-id", required=True)
    review.add_argument("--participant-id", required=True)
    review.add_argument("--review-date", required=True)
    review.add_argument("--usefulness", choices=("useful", "partially_useful", "not_useful", "not_yet_determined"), required=True)
    review.add_argument("--review-evidence-sha256", required=True)
    review.add_argument("--blocker-codes", default="")

    signoff = sub.add_parser("record-signoff")
    signoff.add_argument("--matter-id", required=True)
    signoff.add_argument("--participant-id", required=True)
    signoff.add_argument("--usefulness", choices=("useful", "partially_useful", "not_useful"), required=True)
    signoff.add_argument("--signoff-evidence-sha256", required=True)
    signoff.add_argument("--blocker-codes", default="")
    signoff.add_argument("--complete", action="store_true")

    evidence = sub.add_parser("build-evidence")
    evidence.add_argument("--require-ready-for-external-gate", action="store_true")

    verify = sub.add_parser("verify-evidence")
    verify.add_argument("--generation-id", required=True)

    args = parser.parse_args()
    try:
        store = _store(args)
        if args.command == "status":
            result = store.status()
        elif args.command == "create-program":
            result = store.create_program(
                program_id=args.program_id,
                allowed_tenant_ids=_csv(args.tenant_ids),
                pass48_evidence_sha256=args.pass48_evidence_sha256,
                approved=True,
            )
        elif args.command == "enroll-matter":
            result = store.enroll_matter(
                matter_id=args.matter_id,
                tenant_id=args.tenant_id,
                participant_id=args.participant_id,
                consent_version=args.consent_version,
                client_consent_evidence_sha256=args.client_consent_sha256,
                privacy_notice_sha256=args.privacy_notice_sha256,
                matter_store_sha256=args.matter_store_sha256,
                tenant_isolation_evidence_sha256=args.isolation_evidence_sha256,
                encryption_evidence_sha256=args.encryption_evidence_sha256,
                retention_policy_version=args.retention_policy_version,
                explicit_real_matter_consent=True,
                training_use_allowed=False,
                export_restriction_acknowledged=True,
                human_review_required=True,
                approved=True,
            )
        elif args.command == "record-work-product":
            result = store.record_work_product(
                matter_id=args.matter_id,
                artifact_hashes=_hash_map(args.artifact_hashes_json),
                approved=True,
            )
        elif args.command == "record-daily-review":
            result = store.record_daily_review(
                matter_id=args.matter_id,
                participant_id=args.participant_id,
                review_date=args.review_date,
                usefulness=args.usefulness,
                human_review_completed=True,
                source_verification_completed=True,
                export_gate_checked=True,
                blocker_codes=_csv(args.blocker_codes),
                review_evidence_sha256=args.review_evidence_sha256,
                approved=True,
            )
        elif args.command == "record-signoff":
            result = store.record_signoff(
                matter_id=args.matter_id,
                participant_id=args.participant_id,
                usefulness=args.usefulness,
                attorney_signoff_complete=args.complete,
                blocker_codes=_csv(args.blocker_codes),
                signoff_evidence_sha256=args.signoff_evidence_sha256,
                approved=True,
            )
        elif args.command == "build-evidence":
            result = store.build_evidence_packet(approved=True)
            if args.require_ready_for_external_gate and store.status().get("status") != "ready_for_external_pass49_gate":
                print(json.dumps(result, indent=2, sort_keys=True))
                return 2
        elif args.command == "verify-evidence":
            result = store.verify_generation(args.generation_id)
        else:  # pragma: no cover
            parser.error("unsupported command")
            return 2
    except (LimitedRealMatterPilotError, OSError, ValueError, json.JSONDecodeError) as exc:
        code = getattr(exc, "code", str(exc))
        print(json.dumps({"status": "blocked", "blocker": code}, indent=2, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
