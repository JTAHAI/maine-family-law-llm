"""Temporarily host frozen authority-impact UI against fictional local data.

This QA-only harness creates a disposable fictional matter and two immutable
fictional authority generations outside the repository, then starts the exact
frozen runtime against them.  It exists solely to drive the production browser
UI.  It never opens the live authority root, downloads a source, or retains
matter data after the process exits.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal.documents.workspace import create_document
from legal.matter.calendar_review import CalendarReviewStore
from legal.review import commit_review_decision, prepare_review_request


ROOT = Path(__file__).resolve().parents[1]
OUTLINE_RUNNER = ROOT / "scripts" / "run-v8-structured-draft-outline-e2e.py"
LIFECYCLE_RUNNER = ROOT / "scripts" / "run-v8-authority-activation-rollback-e2e.py"


def _module(path: Path, name: str) -> Any:
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"module_unavailable:{name}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _reviewed_document(case_root: Path, build_id: str, source_hash: str) -> dict[str, Any]:
    """Create a reviewed fictional document with a hash-bound authority source."""

    document = create_document(
        case_root,
        title="Fictional source-change review",
        content="Fictional draft for a source-change revalidation exercise.",
        document_type="motion",
        source_refs=[{"source_id": "fictional-maine-authority-001", "hash": source_hash}],
    )
    authority_result = {
        "status": "review_required",
        "build_id": build_id,
        "sources": [
            {
                "source_id": "fictional-maine-authority-001",
                "source_class": "statute_title_index",
                "freshness_status": "fresh",
                "authority_status": "verified_official_maine",
            }
        ],
        "verification_report": {
            "citations": [],
            "quotes": [],
            "claims": [
                {
                    "claim_id": "fictional-claim-001",
                    "statement": "Fictional claim used only to test the review workflow.",
                    "support_status": "supported",
                    "claim_type": "legal",
                    "source_ids": ["fictional-maine-authority-001"],
                }
            ],
            "blockers": [],
        },
        "filing_gate": {
            "mandatory_checks": {
                "authority_verified": True,
                "citations_resolved": True,
                "quotes_found": True,
                "legal_claims_supported": True,
            },
            "blockers": [],
        },
        "review_required": True,
    }
    prepared = prepare_review_request(case_root, document["document_id"], authority_result=authority_result)
    commit_review_decision(
        case_root,
        document["document_id"],
        request_id=prepared["request_id"],
        confirmation_token=prepared["confirmation_token"],
        confirmed=True,
        decision="approve_review",
        reviewer_name="Fictional reviewer",
        reviewer_role="attorney",
        attested=True,
        claim_annotations=[{"claim_id": "fictional-claim-001", "status": "accepted"}],
    )
    return document


def _source_hash(authority_root: Path, build_id: str) -> str:
    manifest = authority_root / "authority_product" / "builds" / build_id / "authority_product_manifest.json"
    value = json.loads(manifest.read_text(encoding="utf-8"))
    snapshots = list(value.get("source_snapshots") or [])
    if len(snapshots) != 1 or not isinstance(snapshots[0], dict):
        raise RuntimeError("fictional_authority_snapshot_unavailable")
    source_hash = str(snapshots[0].get("sha256") or "")
    if len(source_hash) != 64:
        raise RuntimeError("fictional_authority_hash_invalid")
    return source_hash


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-executable", required=True, type=Path)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--hold-seconds", type=int, default=300)
    args = parser.parse_args(argv)
    if not 10 <= args.hold_seconds <= 600:
        parser.error("hold_seconds_must_be_between_10_and_600")

    outline = _module(OUTLINE_RUNNER, "mfl_v8_outline_e2e")
    lifecycle = _module(LIFECYCLE_RUNNER, "mfl_v8_authority_lifecycle")
    runtime = args.runtime_executable.resolve(strict=True)
    package = args.package.resolve(strict=True)
    outline.validate_runtime_pair(runtime, package)
    helper = outline.load_helper()

    with tempfile.TemporaryDirectory(prefix="mfl-v8-authority-impact-ui-") as temporary:
        temporary_root = Path(temporary)
        authority_root, base_build_id, target_build_id = lifecycle._publish_staged_pair(temporary_root)
        case_root = temporary_root / "fictional-matter"
        case_root.mkdir()
        source_hash = _source_hash(authority_root, base_build_id)
        document = _reviewed_document(case_root, base_build_id, source_hash)
        CalendarReviewStore(case_root).add_rules(
            {
                "rules": [
                    {
                        "rule_id": "fictional-calendar-rule-001",
                        "citation": "Fictional source reference",
                        "source_ref": {"record_id": "REC-FICTIONAL", "source_hash": source_hash},
                        "freshness": "fresh",
                        "triggering_event": "filing",
                        "unit": "days",
                        "count": 7,
                        "jurisdiction": "Maine",
                    }
                ]
            }
        )
        port = helper.free_port()
        base_url = f"http://127.0.0.1:{port}"
        process = helper.start_runtime(
            runtime,
            port,
            localappdata=temporary_root / "localappdata",
            authority_data_root=authority_root,
        )
        monitor = helper.RuntimeNetworkMonitor(process.pid)
        monitor.start()
        try:
            health = helper.wait_json(f"{base_url}/api/health", timeout_s=180)
            if health.get("status") != "ok":
                raise RuntimeError("frozen_runtime_health_failed")
            activated = outline.request(helper, "POST", base_url, "/api/activate-corpus", {"case_root": str(case_root)})
            if activated.get("status") != "ok":
                raise RuntimeError("fictional_matter_activation_failed")
            print(
                json.dumps(
                    {
                        "status": "ready",
                        "base_url": base_url,
                        "fictional_data_only": True,
                        "authority_root_external_to_repository_and_msix": True,
                        "base_build_id": base_build_id,
                        "target_build_id": target_build_id,
                        "document_id": str(document.get("document_id") or ""),
                        "started_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            time.sleep(args.hold_seconds)
        finally:
            network = monitor.stop()
            outline.terminate(process)
            print(
                json.dumps(
                    {
                        "status": "stopped",
                        "external_connection_count": int(network.get("external_connection_count") or 0),
                        "network_samples": int(network.get("sample_count") or 0),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
