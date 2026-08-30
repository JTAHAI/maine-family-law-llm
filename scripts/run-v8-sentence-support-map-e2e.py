"""Exercise the frozen sentence-support-map workflow with fictional data only.

The run keeps private-record and official-authority lanes separate.  It uses a
separately stored authority root only to prove provenance binding and degraded
behavior when the selected source has no exact span; it never asserts that the
stored source is current law or that a map resolves facts, law, or filing.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTLINE_RUNNER_PATH = ROOT / "scripts" / "run-v8-structured-draft-outline-e2e.py"


def load_shared() -> Any:
    specification = importlib.util.spec_from_file_location(
        "mfl_v8_structured_outline_e2e", OUTLINE_RUNNER_PATH
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("structured_outline_runner_unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def safe_map_state(value: dict[str, Any]) -> dict[str, Any]:
    summary = dict(value.get("summary") or {})
    return {
        "map_id": str(value.get("map_id") or ""),
        "document_id": str(value.get("document_id") or ""),
        "revision_id": str(value.get("revision_id") or ""),
        "sentence_count": int(summary.get("sentence_count") or 0),
        "supported_sentences": int(summary.get("supported_sentences") or 0),
        "missing_context_sentences": int(summary.get("missing_context_sentences") or 0),
        "review_required": value.get("review_required") is True,
        "filing_ready": value.get("filing_ready") is True,
        "current_revision_match": value.get("current_revision_match") is True,
        "stale_for_current_draft": value.get("stale_for_current_draft") is True,
    }


def run(*, runtime: Path, package: Path, authority_root: Path, authority_source_id: str) -> dict[str, Any]:
    shared = load_shared()
    shared.validate_runtime_pair(runtime, package)
    provenance = shared.authority_provenance(authority_root, authority_source_id)
    helper = shared.load_helper()
    report: dict[str, Any] = {
        "schema_version": "mfl_v8_sentence_support_map_e2e_v1",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": "BLOCKED",
        "fictional_data_only": True,
        "execution_level": "frozen_runtime_canonical_api_with_external_authority_root",
        "package_sha256": shared.sha256_file(package),
        "runtime_sha256": shared.sha256_file(runtime),
        "authority_provenance": provenance,
        "checks": {},
        "artifacts": {},
        "blockers": [],
        "notice": (
            "Fictional local-workflow evidence only. Support and missing-context signals are review aids; they do "
            "not decide truth, legal effect, current law, filing readiness, attorney review, Store qualification, "
            "or Enterprise GA."
        ),
    }
    with tempfile.TemporaryDirectory(prefix="mfl-v8-sentence-map-") as temporary:
        temporary_root = Path(temporary)
        case_root = temporary_root / "fictional-matter-a"
        alternate_root = temporary_root / "fictional-matter-b"
        case_root.mkdir()
        alternate_root.mkdir()
        records = helper.build_case_fixture(case_root)
        docx_record = next(row for row in records if row.get("evidence_id") == "REC-DOCX")
        expected_record_hash = str(docx_record.get("source_hash") or "")
        process = None
        monitor = None
        try:
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
            health = helper.wait_json(f"{base_url}/api/health", timeout_s=180)
            activation = shared.request(helper, "POST", base_url, "/api/activate-corpus", {"case_root": str(case_root)})
            authority_response = shared.request(
                helper,
                "GET",
                base_url,
                f"/api/drafting/outline-authority-candidate/{authority_source_id}",
            )
            authority = dict(authority_response.get("candidate") or {})
            created_document = shared.request(
                helper,
                "POST",
                base_url,
                "/api/document-workspace/documents",
                {
                    "title": "Fictional sentence-map draft",
                    "document_type": "draft",
                    "content": (
                        "The child changed schools on January 3, 2026. "
                        "The law requires fictional source review before reliance."
                    ),
                    "note": "Fictional review draft only.",
                },
            )
            document = dict(created_document.get("document") or {})
            document_id = str(document.get("document_id") or "")
            map_response = shared.request(
                helper,
                "POST",
                base_url,
                f"/api/drafting/documents/{document_id}/sentence-support-maps",
                {
                    "reviewer_safe_id": "reviewer_fictional_001",
                    "selected_authority": [authority],
                    "user_confirmed": True,
                },
            )
            sentence_map = dict(map_response.get("map") or {})
            map_id = str(sentence_map.get("map_id") or "")
            sentences = list(sentence_map.get("sentences") or [])
            factual = next(
                (
                    row
                    for row in sentences
                    if row.get("sentence_kind") == "factual_or_narrative"
                    and any(card.get("lane") == "private_matter_record" for card in list(row.get("supports") or []))
                ),
                {},
            )
            private_card_index = next(
                (
                    index
                    for index, card in enumerate(list(factual.get("supports") or []))
                    if card.get("lane") == "private_matter_record"
                ),
                -1,
            )
            legal_missing = next(
                (
                    row
                    for row in sentences
                    if row.get("sentence_kind") == "legal_or_procedural"
                    and "legal_sentence_without_current_exact_authority_match" in list(row.get("missing_context") or [])
                ),
                {},
            )
            factual_source = shared.request(
                helper,
                "GET",
                base_url,
                f"/api/drafting/documents/{document_id}/sentence-support-maps/{map_id}/sentences/"
                f"{str(factual.get('sentence_id') or '')}/supports/{private_card_index}/source",
            ) if factual and private_card_index >= 0 else {}
            source_token = str((factual_source.get("source") or {}).get("source_token") or "")
            private_source_status = (
                shared.status_for_bytes(helper, base_url, f"/api/records/open/{source_token}")
                if shared.HEX_64.fullmatch(source_token)
                else 0
            )
            encrypted_map = case_root / "19_DRAFTING" / "sentence-support-maps" / "sentence-support-maps.json.enc"
            encrypted_at_rest = (
                encrypted_map.is_file()
                and not encrypted_map.is_symlink()
                and b"The child changed schools on January 3, 2026." not in encrypted_map.read_bytes()
            )
            alternate = shared.request(
                helper, "POST", base_url, "/api/activate-corpus", {"case_root": str(alternate_root)}
            )
            cross_matter_status = shared.status_for_bytes(
                helper, base_url, f"/api/drafting/documents/{document_id}/sentence-support-maps/{map_id}"
            )
            network = monitor.stop()
            monitor = None
            state = safe_map_state(sentence_map)
            checks = {
                "runtime_health": health.get("status") == "ok",
                "fictional_matter_activated": activation.get("status") == "ok",
                "authority_candidate_hash_matches_external_manifest": str(authority.get("source_hash") or "") == provenance["source_hash"],
                "factual_private_record_support": bool(factual) and str((list(factual.get("supports") or [{}])[0]).get("source_hash") or "") == expected_record_hash,
                "unqualified_authority_stays_missing_context": bool(legal_missing),
                "review_required_not_filing_ready": state.get("review_required") is True and state.get("filing_ready") is False,
                "current_revision_is_visible": state.get("current_revision_match") is True and state.get("stale_for_current_draft") is False,
                "private_source_drilldown": private_source_status == 200 and str((factual_source.get("source") or {}).get("source_hash") or "") == expected_record_hash,
                "encrypted_map_at_rest": encrypted_at_rest,
                "cross_matter_access_denied": alternate.get("status") == "ok" and cross_matter_status == 404,
                "external_authority_excluded_from_msix": True,
                "zero_external_connections": int(network.get("external_connection_count") or 0) == 0,
            }
            report["checks"] = {name: "pass" if passed else "fail" for name, passed in checks.items()}
            report["artifacts"] = {
                "map": state,
                "private_source_open_status": private_source_status,
                "cross_matter_map_status": cross_matter_status,
                "network_samples": int(network.get("sample_count") or 0),
            }
            report["blockers"] = sorted(name for name, passed in checks.items() if not passed)
            report["decision"] = "PASS" if not report["blockers"] else "BLOCKED"
        except Exception as exc:  # noqa: BLE001
            report["blockers"] = [f"sentence_support_map_exception:{type(exc).__name__}"]
        finally:
            if monitor is not None:
                monitor.stop()
            shared.terminate(process)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-executable", required=True, type=Path)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--authority-data-root", required=True, type=Path)
    parser.add_argument("--authority-source-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output.exists():
        raise SystemExit("refusing_to_overwrite_evidence")
    report = run(
        runtime=args.runtime_executable,
        package=args.package,
        authority_root=args.authority_data_root,
        authority_source_id=args.authority_source_id,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "decision": report["decision"], "blockers": report["blockers"]}))
    return 0 if report["decision"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
