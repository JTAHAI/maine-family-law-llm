#!/usr/bin/env python3
"""Operate and audit the external v5.16 attorney-only sandbox.

This utility never verifies attorney identity, accepts private matter data, or marks
Pass 48 complete. It writes only to an explicitly configured external pilot root.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legal.pilot.sandbox_operations import (  # noqa: E402
    AttorneySandboxOperationsError,
    AttorneySandboxOperationsStore,
)


def _store(args: argparse.Namespace) -> AttorneySandboxOperationsStore:
    return AttorneySandboxOperationsStore(args.repo_root, args.pilot_root)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run fail-closed v5.16 attorney sandbox operations.")
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--pilot-root", type=Path, required=True, help="External attorney-sandbox operations root.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status")

    program = sub.add_parser("create-program")
    program.add_argument("--program-id", required=True)
    program.add_argument("--max-questions", type=int, default=48)

    evidence = sub.add_parser("build-evidence")
    evidence.add_argument("--require-ready-for-external-gate", action="store_true")

    verify = sub.add_parser("verify-evidence")
    verify.add_argument("--generation-id", required=True)

    export = sub.add_parser("export-eval-candidates")
    export.add_argument("--eval-root", type=Path, required=True)

    attestation = sub.add_parser("record-attestation")
    attestation.add_argument("--type", choices=("identity_audit", "program_signoff"), required=True)
    attestation.add_argument("--evidence-sha256", required=True)

    args = parser.parse_args()
    try:
        store = _store(args)
        if args.command == "status":
            result = store.status()
        elif args.command == "create-program":
            result = store.create_program(
                program_id=args.program_id,
                max_questions=args.max_questions,
                approved=True,
            )
        elif args.command == "build-evidence":
            result = store.build_evidence_packet(approved=True)
            if args.require_ready_for_external_gate and store.status().get("status") != "ready_for_external_pass48_gate":
                print(json.dumps(result, indent=2, sort_keys=True))
                return 2
        elif args.command == "verify-evidence":
            result = store.verify_evidence_packet(args.generation_id)
        elif args.command == "export-eval-candidates":
            result = store.export_eval_candidates(args.eval_root, approved=True)
        elif args.command == "record-attestation":
            result = store.record_external_attestation(
                attestation_type=args.type,
                evidence_sha256=args.evidence_sha256,
                approved=True,
            )
        else:  # pragma: no cover
            parser.error("unsupported command")
            return 2
    except AttorneySandboxOperationsError as exc:
        print(json.dumps({"status": "blocked", "blocker": exc.code}, indent=2, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.command == "verify-evidence" and result.get("status") != "pass":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
